import logging
import random
from collections import defaultdict
from data_structures import Profession, SkillLevel, DAILY_WAGES, SILVER_PER_GOLD

class Person:
    def __init__(
        self, person_id, name, profession, skill_level,
        silver=0.0, gold=0.0,
        training_target=None, months_training_remaining=0,
        cows=0, pigs=0, sheep=0
    ):
        self.person_id = person_id
        self.name = name
        self.profession = profession
        self.skill_level = skill_level
        self.silver = silver
        self.gold = gold
        self.training_target = training_target
        self.months_training_remaining = months_training_remaining

        # personal inventory
        self.inventory = defaultdict(float)

        # Basic consumption
        self.food_need_daily = 2.0
        self.drink_need_daily = 1.0
        self.housing_cost_weekly = 5.0
        self.clothing_maintenance_monthly = 3.0

        # Livestock
        self.cows = cows
        self.pigs = pigs
        self.sheep = sheep

    def total_silver_equivalent(self):
        return self.silver + self.gold * SILVER_PER_GOLD

    def pay_in_silver(self, amount):
        if amount <= 0:
            return 0.0
        paid = 0.0
        if self.silver >= amount:
            self.silver -= amount
            return amount
        else:
            needed = amount - self.silver
            paid += self.silver
            self.silver = 0
            gold_in_silver = self.gold * SILVER_PER_GOLD
            if gold_in_silver >= needed:
                gold_needed = needed / SILVER_PER_GOLD
                self.gold -= gold_needed
                return amount
            else:
                paid += gold_in_silver
                self.gold = 0
                return paid

    def receive_silver(self, amount):
        self.silver += amount

    def receive_gold(self, amount):
        self.gold += amount

    def daily_wage(self):
        return DAILY_WAGES.get(self.skill_level, 0)

    def is_in_training(self):
        return (
            self.profession == Profession.UNEMPLOYED
            and (self.training_target is not None)
        )

    def train_one_month(self):
        if self.is_in_training():
            self.months_training_remaining -= 1
            if self.months_training_remaining <= 0:
                self.profession = self.training_target
                self.skill_level = SkillLevel.LOW
                self.training_target = None
                self.months_training_remaining = 0


class Guild:
    def __init__(self, guild_id, guild_name, profession):
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.profession = profession
        self.employees = []
        self.silver = 0.0
        self.gold = 50.0
        self.loan_balance = 0.0

        self.warehouse = defaultdict(float)  # local items, e.g. before transport
        self.did_produce_today = False
        self.num_wagons = 0
        self.num_horses = 0
        self.num_wagons_in_use = 0
        self.num_horses_in_use = 0

    def add_employee(self, person):
        self.employees.append(person)

    def pay_in_silver(self, amount):
        if amount <= 0:
            return 0.0
        paid = 0.0
        if self.silver >= amount:
            self.silver -= amount
            return amount
        else:
            needed = amount - self.silver
            paid += self.silver
            self.silver = 0
            gold_in_silver = self.gold * SILVER_PER_GOLD
            if gold_in_silver >= needed:
                gold_needed = needed / SILVER_PER_GOLD
                self.gold -= gold_needed
                return amount
            else:
                paid += gold_in_silver
                self.gold = 0
                return paid

    def receive_silver(self, amount):
        self.silver += amount

    def pay_wages(self):
        pay_factor = 1.0 if self.did_produce_today else 0.6
        total_paid = 0.0
        for emp in self.employees:
            # Pay full if they're relevant, partial if not
            if emp.profession in [self.profession, Profession.HAULER]:
                weekly = emp.daily_wage() * 5 * pay_factor
                paid = self.pay_in_silver(weekly)
                emp.receive_silver(paid)
                total_paid += paid
        self.did_produce_today = False
        return total_paid


class Treasury:
    def __init__(self):
        self.silver = 0.0
        self.gold = 1000.0

    def collect_tax(self, amount):
        self.silver += amount

    def pay_tournament_prizes(self, gladiators, distribution_map, logger):
        import random
        total_gold_coins = 100
        random.shuffle(gladiators)
        for rank in range(1, 31):
            if rank <= len(gladiators):
                g = gladiators[rank - 1]
                pct = distribution_map.get(rank, 0)
                payout = total_gold_coins * (pct / 100)
                g.receive_gold(payout)
                logger.debug(f"Treasury pays {payout:.2f} gold to {g.name} (Rank {rank}).")

    def mint_coins_from_ore(self, gold_ore_amount, silver_ore_amount):
        self.gold += gold_ore_amount * 100
        self.silver += silver_ore_amount * 100
