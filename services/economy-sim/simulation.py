"""
simulation.py – core game loop

High‑level flow
───────────────
    • create population  → create guilds → initialise market
    • for every day:
        1. update reference prices & demand
        2. let guilds buy missing raw materials
        3. production (Mon–Fri only)
        4. schedule & execute outbound transports  (+ auto‑ASKs)
        5. people:
              a. pick up items already owned in the market
              b. bid to top‑up their 7‑day food / drink buffer
              c. consume daily → hunger stats
        6. intra‑day order‑matching / price‑adjust
        7. gladiator luxury spending
        8. final order‑matching
        9. schedule & execute inbound transports
       10. regrow forest
       11. pay wages (Fri only)
       12. monthly events (taxes, tournament, upkeep, training)
       13. write order‑book CSV & telemetry
"""

from __future__ import annotations

import csv
import logging
import random
from collections import defaultdict
from typing import List

# ── local modules ────────────────────────────────────────────────────────────
from data_structures import (
    Profession,
    SkillLevel,
    GLADIATOR_PRIZE_DISTRIBUTION,
    SEASONAL_FARM_YIELD,
)
from entities import Person, Guild, Treasury
from market import MarketWarehouse
from economy import (
    produce_raw_resources,
    farmer_produce_daily,
    parse_recipes_and_produce,
    guild_buy_raw_materials,
    INDUSTRY_CONFIG,
)
from settings import (
    MEAL_ITEMS,
    DRINK_ITEMS,
    PERSON_FOOD_NEED_DAILY,
    PERSON_DRINK_NEED_DAILY,
    FOREST_MAX_CAPACITY,
    FOREST_REGROWTH_PER_DAY,
    DEFAULT_KEEP_STOCK,
    TRANSPORT_CAPACITY,
)

class TransportJob:
    """A single logistics task (direction = 'outbound' | 'inbound')."""

    def __init__(self, guild: Guild, item: str, quantity: float, *, direction: str):
        self.guild = guild
        self.item = item
        self.quantity = quantity
        self.quantity_remaining = quantity
        self.delivered_amount = 0.0
        self.direction = direction  # 'outbound' | 'inbound'


def _pick_vehicle(guild: Guild) -> str:
    """Deterministically pick the most‑capable free vehicle."""
    if guild.num_wagons_in_use < guild.num_wagons:
        return "wagon"
    if guild.num_horses_in_use < guild.num_horses:
        return "horse_cart"
    return "hand"


def _use_vehicle(guild: Guild, method: str, delta: int) -> None:
    """Increment (+1) or decrement (‑1) the in‑use counter for the vehicle."""
    if method == "wagon":
        guild.num_wagons_in_use += delta
    elif method == "horse_cart":
        guild.num_horses_in_use += delta


def _one_outbound_trip(
    hauler: Person, job: TransportJob, sim: "Simulation"
) -> float:
    """Move goods *to* the market, return the moved quantity."""
    g = job.guild
    method = _pick_vehicle(g)
    _use_vehicle(g, method, +1)
    try:
        cap = TRANSPORT_CAPACITY[method]
        to_load = min(cap, job.quantity_remaining, g.warehouse[job.item])
        if to_load <= 0:
            logging.warning(
                "Stalled haul: %s planned %s but local stock =0 (remain %.2f)",
                g.guild_name,
                job.item,
                job.quantity_remaining,
            )
            return 0.0

        g.warehouse[job.item] -= to_load
        job.quantity_remaining -= to_load
        job.delivered_amount += to_load

        sim.marketWarehouse.deposit(g, job.item, to_load, for_sale=True)

        logging.debug(
            "%s hauled %.2f %s -> market with %s (remain %.2f)",
            hauler.name,
            to_load,
            job.item,
            method,
            job.quantity_remaining,
        )
        return to_load
    finally:
        _use_vehicle(g, method, -1)


def _one_inbound_trip(
    hauler: Person, job: TransportJob, sim: "Simulation"
) -> float:
    """Bring goods back *from* the market, return the moved quantity."""
    g = job.guild
    method = _pick_vehicle(g)
    _use_vehicle(g, method, +1)
    try:
        cap = TRANSPORT_CAPACITY[method]
        own_in_market = sim.marketWarehouse.owner_map[job.item].get(g, 0.0)
        to_load = min(cap, job.quantity_remaining, own_in_market)
        if to_load <= 0:
            return 0.0

        moved = sim.marketWarehouse.withdraw(g, job.item, to_load)
        g.warehouse[job.item] += moved
        job.quantity_remaining -= moved
        job.delivered_amount += moved

        logging.debug(
            "%s hauled %.2f %s <- market with %s (remain %.2f)",
            hauler.name,
            moved,
            job.item,
            method,
            job.quantity_remaining,
        )
        return moved
    finally:
        _use_vehicle(g, method, -1)


def handle_transport_jobs(sim: "Simulation") -> None:
    """
    Execute *outbound* jobs and auto‑place a single ASK when done.
    """
    for g in sim.guilds:
        haulers = [p for p in g.employees if p.profession == Profession.HAULER]
        if not haulers:
            continue

        for job in [j for j in sim.transport_jobs if j.guild == g]:
            while job.quantity_remaining > 0:
                for h in haulers:
                    _one_outbound_trip(h, job, sim)
                    if job.quantity_remaining <= 0:
                        break
            if job.delivered_amount > 0:  # finished
                ref_p = sim.marketWarehouse.goods[job.item]["price"]
                sim.marketWarehouse.place_ask(
                    owner=g,
                    item=job.item,
                    quantity=job.delivered_amount,
                    ask_price=round(ref_p * 0.98, 2),
                    current_day=sim.current_day,
                )
        # prune finished
    sim.transport_jobs = [j for j in sim.transport_jobs if j.quantity_remaining > 0]


def handle_inbound_jobs(sim: "Simulation") -> None:
    """Execute *inbound* jobs until all are done for the day."""
    for g in sim.guilds:
        haulers = [p for p in g.employees if p.profession == Profession.HAULER]
        if not haulers:
            continue

        for job in [j for j in sim.inbound_transport_jobs if j.guild == g]:
            while job.quantity_remaining > 0:
                for h in haulers:
                    _one_inbound_trip(h, job, sim)
                    if job.quantity_remaining <= 0:
                        break
    sim.inbound_transport_jobs = [
        j for j in sim.inbound_transport_jobs if j.quantity_remaining > 1e-6
    ]


# ============================================================================
#                              FOREST & MISC
# ============================================================================


def regrow_forest(cur: int) -> int:
    return min(FOREST_MAX_CAPACITY, cur + FOREST_REGROWTH_PER_DAY)



# ============================================================================
#                               SIMULATION CLASS
# ============================================================================


class Simulation:
    # ------------------------------------------------------------------ init
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger()
        self.people: List[Person] = []
        self.guilds: List[Guild] = []
        self.treasury = Treasury()

        self.INDUSTRY_CONFIG = INDUSTRY_CONFIG
        self.marketWarehouse = MarketWarehouse()

        self.forest_capacity = FOREST_MAX_CAPACITY
        self.current_day = 1
        self.tax_rate_percent = 10.0

        # telemetry
        self.day_list: List[int] = []
        self.forest_capacity_list: List[int] = []
        self.hungry_list: List[int] = []
        self.total_silver_list: List[float] = []
        self.total_gold_list: List[float] = []

        # dynamic queues
        self.transport_jobs: List[TransportJob] = []
        self.inbound_transport_jobs: List[TransportJob] = []

    # ─────────────────────────────────────────────────────────── logistics
    def _get_keep_amount(self, guild: Guild, item: str) -> float:
        cfg = self.INDUSTRY_CONFIG.get(guild.profession)
        base = (cfg or {}).get("min_stocks", {}).get(item, DEFAULT_KEEP_STOCK)
        return max(base, DEFAULT_KEEP_STOCK)

    def generate_transport_jobs(self) -> None:
        self.transport_jobs.clear()
        for g in self.guilds:
            for item, qty in g.warehouse.items():
                if not isinstance(item, str):
                    continue
                keep = 0 if item.startswith("meal_") else self._get_keep_amount(g, item)
                if qty > keep:
                    self.transport_jobs.append(
                        TransportJob(g, item, qty - keep, direction="outbound")
                    )

    def generate_inbound_transport_jobs(self) -> None:
        self.inbound_transport_jobs.clear()
        for g in self.guilds:
            for item, owners in self.marketWarehouse.owner_map.items():
                owned = owners.get(g, 0.0)
                if owned <= 1e-6:
                    continue
                for_sale = self.marketWarehouse.for_sale_map[item].get(g, 0.0)
                to_haul = owned - for_sale
                if to_haul > 1e-6:
                    self.inbound_transport_jobs.append(
                        TransportJob(g, item, to_haul, direction="inbound")
                    )

    # ─────────────────────────────────────────────────────────── people helpers
    @staticmethod
    def _eat_or_drink(person: Person) -> bool:
        # eat
        for m in MEAL_ITEMS:
            if person.inventory[m] >= PERSON_FOOD_NEED_DAILY:
                person.inventory[m] -= PERSON_FOOD_NEED_DAILY
                return True
        # drink
        for d in DRINK_ITEMS:
            if person.inventory[d] >= PERSON_DRINK_NEED_DAILY:
                person.inventory[d] -= PERSON_DRINK_NEED_DAILY
                return True
        return False

    def move_purchases_to_inventory(self) -> None:
        for item, owners in list(self.marketWarehouse.owner_map.items()):
            for owner, qty in list(owners.items()):
                if qty <= 1e-6 or not hasattr(owner, "inventory"):
                    continue
                picked = self.marketWarehouse.withdraw(owner, item, qty)
                owner.inventory[item] += picked

    # ►►►  buying food/drink --------------------------------------------------
    def people_buy_food_stockpile(self) -> None:
        for p in self.people:
            if p.total_silver_equivalent() < 1.0:
                continue

            # -------- food
            need = 7 * p.food_need_daily
            have = sum(p.inventory[m] for m in MEAL_ITEMS)
            short = need - have
            if short > 0.1:
                cheapest, price = self._cheapest_ask(MEAL_ITEMS)
                if cheapest:
                    self.marketWarehouse.place_bid(
                        owner=p,
                        item=cheapest,
                        quantity=int(short + 1),
                        bid_price=round(price * 1.10, 2),
                        current_day=self.current_day,
                    )

            # -------- drink
            need = 7 * p.drink_need_daily
            have = sum(p.inventory[d] for d in DRINK_ITEMS)
            short = need - have
            if short > 0.1:
                cheapest, price = self._cheapest_ask(DRINK_ITEMS)
                if cheapest:
                    self.marketWarehouse.place_bid(
                        owner=p,
                        item=cheapest,
                        quantity=int(short + 1),
                        bid_price=round(price * 1.10, 2),
                        current_day=self.current_day,
                    )

    def _cheapest_ask(self, items: List[str]) -> tuple[str | None, float | None]:
        cheapest, best_price = None, None
        for it in items:
            asks = self.marketWarehouse.asks.get(it, [])
            if not asks:
                continue
            p = asks[0].price  # sorted ascending
            if best_price is None or p < best_price:
                cheapest, best_price = it, p
        return cheapest, best_price

    # ►►►  gladiator luxury spending -----------------------------------------
    def _gladiator_luxury_spending(self) -> None:
        lux_items = ["beer", "meal_meat", "furniture", "clothing", "weapon_basic", "armor_basic"]

        for gl in (x for x in self.people if x.profession == Profession.GLADIATOR):
            total_eq  = gl.total_silver_equivalent()
            if total_eq < 100:
                continue

            budget = min(total_eq * 0.5, 500.0)
            spent  = 0.0
            random.shuffle(lux_items)

            for item in lux_items:
                # estimated cost of this purchase
                ref_p     = self.marketWarehouse.goods[item]["price"]
                est_cost  = 3 * ref_p

                # stop if this buy would bust either the personal budget or the gladiator’s cash
                if spent + est_cost > budget or spent + est_cost > total_eq:
                    continue

                # place BID
                self.marketWarehouse.place_bid(
                    owner      = gl,
                    item       = item,
                    quantity   = 3,
                    bid_price  = round(ref_p * 1.10, 2),
                    current_day= self.current_day,
                )

                # immediate pickup (simplified)
                owned = self.marketWarehouse.owner_map[item].get(gl, 0.0)
                if owned:
                    picked = self.marketWarehouse.withdraw(gl, item, owned)
                    gl.inventory[item] += picked
                    spent += picked * ref_p

   
    # ───────────────────────────────────────────────────── population & guilds
    def create_initial_population(self):
        next_id = 1
        people = []
        # 100 gladiators
        for _ in range(100):
            p = Person(next_id, f"Gladiator_{next_id}", Profession.GLADIATOR, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 20 miners
        for _ in range(20):
            p = Person(next_id, f"Miner_{next_id}", Profession.MINER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 15 lumberjacks
        for _ in range(15):
            p = Person(next_id, f"Lumberjack_{next_id}", Profession.LUMBERJACK, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 30 farmers
        for _ in range(40):
            cows = random.randint(0, 2)
            pigs = random.randint(0, 4)
            sheep = random.randint(0, 5)
            p = Person(next_id, f"Farmer_{next_id}", Profession.FARMER, SkillLevel.LOW, silver=1000,
                       cows=cows, pigs=pigs, sheep=sheep)
            people.append(p)
            next_id += 1
        # 40 fishers
        for _ in range(40):
            p = Person(next_id, f"Fisher_{next_id}", Profession.FISHER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 4 carpenters
        for _ in range(4):
            p = Person(next_id, f"Carpenter_{next_id}", Profession.CARPENTER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 8 blacksmiths
        for _ in range(4):
            p = Person(next_id, f"Blacksmith_{next_id}", Profession.BLACKSMITH, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 4 jewelers
        for _ in range(4):
            p = Person(next_id, f"Jeweler_{next_id}", Profession.JEWELER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 4 bakers
        for _ in range(4):
            p = Person(next_id, f"Baker_{next_id}", Profession.BAKER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 4 brewers
        for _ in range(3):
            p = Person(next_id, f"Brewer_{next_id}", Profession.BREWER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 6 cooks
        for _ in range(6):
            p = Person(next_id, f"Cook_{next_id}", Profession.COOK, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 5 tailors
        for _ in range(5):
            p = Person(next_id, f"Tailor_{next_id}", Profession.TAILOR, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 5 treasury officers
        for _ in range(5):
            p = Person(next_id, f"TreasuryOfficer_{next_id}", Profession.TREASURY_OFFICER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # 22 haulers
        for _ in range(22):
            p = Person(next_id, f"Hauler_{next_id}", Profession.HAULER, SkillLevel.LOW, silver=1000)
            people.append(p)
            next_id += 1
        # fill up to 400 unemployed
        while len(people) < 400:
            p = Person(next_id, f"Unemployed_{next_id}", Profession.UNEMPLOYED, SkillLevel.NONE)
            people.append(p)
            next_id += 1
        self.people = people

    def create_guilds(self):
        from collections import defaultdict
        prof_map = defaultdict(list)
        for p in self.people:
            prof_map[p.profession].append(p)

        # pick some main professions
        wanted = [
            Profession.MINER, Profession.LUMBERJACK, Profession.FARMER,
            Profession.FISHER, Profession.CARPENTER, Profession.BLACKSMITH,
            Profession.JEWELER, Profession.BAKER, Profession.BREWER,
            Profession.COOK, Profession.TAILOR
        ]
        gid = 1
        guilds = []
        for prof in wanted:
            g = Guild(gid, f"{prof.value.capitalize()}_Guild", prof)
            # add all matching employees
            for x in prof_map[prof]:
                g.add_employee(x)
            guilds.append(g)
            gid += 1

        # also add some haulers
        for g in guilds:
            for _ in range(2):
                new_id = max(p.person_id for p in self.people) + 1
                h = Person(new_id, f"Hauler_{new_id}", Profession.HAULER, SkillLevel.LOW, 30)
                self.people.append(h)
                g.add_employee(h)

        self.guilds = guilds

    # ────────────────────────────────────────────────────────────── helpers
    def find_guild_for_person(self, person: Person) -> Guild | None:
        return next((g for g in self.guilds if person in g.employees), None)
    
    def find_guild_by_id(self, guild_id: int) -> Guild | None:
        """Return the Guild with the given id, or None."""
        return next((g for g in self.guilds if g.guild_id == guild_id), None)

    # ───────────────────────────────────────────────────────────── main loop
    def step_day(self) -> None:
        dow = (self.current_day - 1) % 7        # 0=Mon
        dom = (self.current_day - 1) % 30 + 1
        season_factor = SEASONAL_FARM_YIELD[self.get_season(self.current_day)]

        # 1) refresh demand curves / ref‑prices
        self.marketWarehouse.update_supply_demand()

        # 2) guild procurement
        for g in self.guilds:
            guild_buy_raw_materials(g, self)

        # 3) production (Mon‑Fri)
        if dow < 5:
            for p in self.people:
                g = self.find_guild_for_person(p)
                if not g:
                    continue
                if p.profession in (
                    Profession.MINER,
                    Profession.LUMBERJACK,
                    Profession.FISHER,
                ):
                    self.forest_capacity = produce_raw_resources(
                        p, g, self.forest_capacity
                    )
                elif p.profession == Profession.FARMER:
                    farmer_produce_daily(p, g, season_factor)
                elif p.profession == g.profession and p.profession != Profession.UNEMPLOYED:
                    parse_recipes_and_produce(p, g, self)

        # 4) outbound logistics
        self.generate_transport_jobs()
        handle_transport_jobs(self)
        for g in self.guilds:
            self._update_guild_vehicles(g)

        # 5a) pick‑up earlier buys
        self.move_purchases_to_inventory()
        # 5b) restock food & drinks
        self.people_buy_food_stockpile()
        # 5c) consume daily
        hungry_today = sum(not self._eat_or_drink(p) for p in self.people)

        # 6) intra‑day match
        self.marketWarehouse.do_dynamic_price_adjustment()
        self.marketWarehouse.match_orders_for_day(self.current_day, simulation=self)

        # 7) gladiator luxury
        self._gladiator_luxury_spending()

        # 8) final match
        self.marketWarehouse.do_dynamic_price_adjustment()
        self.marketWarehouse.match_orders_for_day(self.current_day, simulation=self)

        # 9) inbound logistics
        self.generate_inbound_transport_jobs()
        handle_inbound_jobs(self)

        # 10) forest regrowth
        self.forest_capacity = regrow_forest(self.forest_capacity)

        # 11) wages
        if dow == 4:
            for g in self.guilds:
                g.pay_wages()

        # 12) monthly events
        if dom == 3:
            self.do_monthly_events()

        # 13) telemetry
        self.marketWarehouse.write_order_book_to_csv(self.current_day)
        total_silver = sum(p.silver for p in self.people)
        total_gold = sum(p.gold for p in self.people)
        self.day_list.append(self.current_day)
        self.forest_capacity_list.append(self.forest_capacity)
        self.hungry_list.append(hungry_today)
        self.total_silver_list.append(total_silver)
        self.total_gold_list.append(total_gold)

        logging.info(
            "Day %d │ hungry=%d │ forest=%d │ silver=%.2f │ gold=%.2f",
            self.current_day,
            hungry_today,
            self.forest_capacity,
            total_silver,
            total_gold,
        )
        self.current_day += 1

    # --------------------------------------------------------- misc helpers
    def _update_guild_vehicles(self, g: Guild) -> None:
        for equip in ("wagon", "horse_cart"):
            qty = int(g.warehouse[equip])
            if qty:
                if equip == "wagon":
                    g.num_wagons += qty
                else:
                    g.num_horses += qty
                g.warehouse[equip] = 0
    

    def run_days(self, n=1):
        for _ in range(n):
            self.step_day()
    
        # ---------------------------------------------------------------- init hook
    def initialize_sim(self) -> None:
        """
        Public hook kept for GUI backwards‑compatibility.
        Sets up population, guilds and any other one‑off bootstrapping.
        """
        self.create_initial_population()
        self.create_guilds()

        # If you eventually add more one‑time prep (seed prices, pre‑stock
        # warehouses, etc.) put it here so the GUI call stays valid.
        logging.info("Simulation initialised: %d people, %d guilds",
                     len(self.people), len(self.guilds))



    def do_gladiator_spending(self):
        # Example approach: each gladiator places a small BID for a meal_meat or beer, etc.
        # Not fully implemented here — just a placeholder
        pass

    def do_monthly_events(self):
        # pay taxes
        for p in self.people:
            self.pay_taxes_monthly(p)
        # tournament
        glads = [x for x in self.people if x.profession == Profession.GLADIATOR]
        self.treasury.pay_tournament_prizes(glads, GLADIATOR_PRIZE_DISTRIBUTION, logging)
        # clothing
        for p in self.people:
            self.consume_monthly(p)
        # training
        for p in self.people:
            p.train_one_month()

        # treasury buys ore from the warehouse if you wish, etc. (omitted here for brevity)

    def pay_taxes_monthly(self, person):
        daily = person.daily_wage()
        monthly_wage = daily * 5 * 4
        tax_amount = monthly_wage * (self.tax_rate_percent / 100.0)
        paid = person.pay_in_silver(tax_amount)
        self.treasury.collect_tax(paid)

    def consume_monthly(self, person):
        """
        Person pays clothing maintenance monthly, tries to pay to a Tailor guild if possible.
        """
        cost = person.clothing_maintenance_monthly
        if cost <= 0:
            return

        tailor_guild = None
        for g in self.guilds:
            if g.profession == Profession.TAILOR:
                tailor_guild = g
                break

        paid = person.pay_in_silver(cost)
        if tailor_guild:
            tailor_guild.receive_silver(paid)
            if paid < cost:
                logging.debug(
                    f"{person.name} couldn't afford full clothing upkeep (paid={paid:.2f}/{cost:.2f})."
                )
            else:
                logging.debug(
                    f"{person.name} paid {paid:.2f} to {tailor_guild.guild_name} for clothing upkeep."
                )
        else:
            # fallback: deposit into treasury or just vanish
            self.treasury.collect_tax(paid)
            if paid < cost:
                logging.debug(
                    f"{person.name} lacked full clothing payment. Paid {paid:.2f}/{cost:.2f}."
                )
            else:
                logging.debug(
                    f"{person.name} paid {paid:.2f} for clothing upkeep (no tailor guild)."
                )

    def get_season(self, day):
        day_of_year = day % 360
        if day_of_year < 90:
            return "spring"
        elif day_of_year < 180:
            return "summer"
        elif day_of_year < 270:
            return "fall"
        else:
            return "winter"

    def summarize(self):
        total_silver = 0
        total_gold = 0
        for p in self.people:
            total_silver += p.silver
            total_gold += p.gold
        return f"End of Day {self.current_day-1}: total_silver={total_silver:.2f}, total_gold={total_gold:.2f}, treasury= {self.treasury.silver:.2f} silver / {self.treasury.gold:.2f} gold."
