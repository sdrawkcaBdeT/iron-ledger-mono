"""
market.py
~~~~~~~~~

Unifies

* the physical warehouse (ownership & “for‑sale” flags)
* an order book (bids / asks)
* matching logic with partial fills
* dynamic reference pricing
* CSV export of the order book
"""

from __future__ import annotations

import csv
import logging
import time
from collections import defaultdict
from typing import Dict, List, Any

from resource_loader import CATALOG

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────
class MarketOrder:
    """One bid or ask in the order book."""

    def __init__(
        self,
        owner: Any,                 # a Person or Guild – just needs .pay_in_silver()
        item: str,
        quantity: float,
        price: float,
        is_bid: bool,
        timestamp: float,
        current_day: int,
        valid_days: int = 3,
    ) -> None:
        self.owner = owner
        self.item = item
        self.quantity = float(quantity)
        self.price = float(price)
        self.is_bid = is_bid
        self.timestamp = timestamp

        self.order_id: int | None = None
        self.posted_day = current_day
        self.valid_until_day = current_day + valid_days


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _compute_relist_price(item: str, old_price: float, simulation) -> float:
    """
    Simple heuristic: average of (current reference price, recent‑trade average),
    nudged down 2 %, capped within ±5 % of the reference price.
    """
    market_price = simulation.marketWarehouse.goods[item]["price"]
    cutoff_day = simulation.current_day - 2
    recent = [
        t for t in simulation.marketWarehouse.trades
        if t["item"] == item and t["sim_day"] >= cutoff_day
    ]
    avg_trade = (
        sum(t["price"] for t in recent) / len(recent)
        if recent else market_price
    )
    candidate = ((market_price + avg_trade) / 2.0) * 0.95   # 5 % below mid‑point
    candidate = min(candidate, old_price * 0.90)            # ↘   max 10 % drop
    candidate = max(candidate, 0.01)                               # hard floor
    return min(candidate, market_price * 1.05)                     # soft cap


# ──────────────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────────────
class MarketWarehouse:
    """
    Central marketplace & warehouse.

    Physical stock lives in ``owner_map[item][owner]``.
    Anything flagged for sale also appears in ``for_sale_map``.
    """

    def __init__(self) -> None:
        # physical ownership
        self.owner_map: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        # subset of owner_map that is listed for sale
        self.for_sale_map: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))

        # order book
        self.bids: Dict[str, List[MarketOrder]] = defaultdict(list)
        self.asks: Dict[str, List[MarketOrder]] = defaultdict(list)

        # IDs
        self.next_order_id: int = 1
        self.trade_id_counter: int = 1

        # trade history
        self.trades: List[dict] = []

        # dynamic reference price & rolling supply/demand tallies
        self.goods: Dict[str, Dict[str, float]] = {
            name: {"price": g.base_price, "supply": 0.0, "demand": 0.0}
            for name, g in CATALOG.goods.items()
        }

    # ──────────────────────────────────────────────────────────────
    # 1) Physical stock helpers
    # ──────────────────────────────────────────────────────────────
    def deposit(self, owner: Any, item: str, quantity: float, *, for_sale: bool = False) -> None:
        """Move goods *into* the market warehouse."""
        if quantity <= 0:
            return
        self.owner_map[item][owner] += quantity
        if for_sale:
            self.for_sale_map[item][owner] += quantity

    def withdraw(self, owner: Any, item: str, qty: float) -> float:
        """Remove up to *qty* units if the owner has them on site; returns actual withdrawn."""
        if qty <= 0:
            return 0.0
        have = self.owner_map[item].get(owner, 0.0)
        take = min(qty, have)
        if take:
            self.owner_map[item][owner] -= take
            if self.owner_map[item][owner] <= 1e-6:
                del self.owner_map[item][owner]
            # keep "for sale" flag accurate
            self._decrease_for_sale(owner, item, take)
        return take
    
    def pick_up_item(self, owner: Any, item: str, qty: float) -> float:
        """Exactly the same as withdraw(); kept for legacy code."""
        return self.withdraw(owner, item, qty)

    # ------------------------------------------------------------------ #
    # internal: keep for_sale_map consistent after a sale or cancelation #
    # ------------------------------------------------------------------ #
    def _decrease_for_sale(self, seller: Any, item: str, qty_sold: float) -> None:
        """Decrease seller's for‑sale flag when a sale closes."""
        fs = self.for_sale_map[item].get(seller, 0.0)
        if not fs:
            return
        remaining = fs - qty_sold
        if remaining <= 1e-6:
            del self.for_sale_map[item][seller]
        else:
            self.for_sale_map[item][seller] = remaining

    # ──────────────────────────────────────────────────────────────
    # 2) Placing orders
    # ──────────────────────────────────────────────────────────────
    def place_bid(self, owner: Any, item: str, quantity: float, bid_price: float,
                  *, current_day: int, valid_days: int = 3) -> int | None:
        if quantity <= 0:
            return None
        o = MarketOrder(owner, item, quantity, bid_price, True, time.time(),
                        current_day, valid_days)
        o.order_id = self.next_order_id
        self.next_order_id += 1
        self.bids[item].append(o)
        self.bids[item].sort(key=lambda x: (-x.price, x.timestamp))
        return o.order_id

    def place_ask(self, owner: Any, item: str, quantity: float, ask_price: float,
                  *, current_day: int, valid_days: int = 3) -> int | None:
        # owner must physically have the goods
        have = self.owner_map[item].get(owner, 0.0)
        quantity = min(quantity, have)
        if quantity <= 0:
            return None
        o = MarketOrder(owner, item, quantity, ask_price, False, time.time(),
                        current_day, valid_days)
        o.order_id = self.next_order_id
        self.next_order_id += 1
        self.asks[item].append(o)
        self.asks[item].sort(key=lambda x: (x.price, x.timestamp))
        # flag those units as “for sale”
        self.for_sale_map[item][owner] += quantity
        return o.order_id

    # ──────────────────────────────────────────────────────────────
    # 3) Matching engine
    # ──────────────────────────────────────────────────────────────
    def match_orders_for_day(self, current_day: int, *, simulation=None) -> None:
        """Public entry point – first purge expirations, then match per item."""
        self._remove_expired_orders(current_day, simulation)
        for itm in set(self.bids) | set(self.asks):
            self._match_item(itm, current_day)

    # -- internal -------------------------------------------------- #
    def _match_item(self, item: str, sim_day: int) -> None:
        bids, asks = self.bids[item], self.asks[item]
        i = j = 0
        while i < len(bids) and j < len(asks):
            best_bid = bids[i]
            best_ask = asks[j]

            if best_bid.price < best_ask.price:
                break  # no more matches today

            trade_price = best_bid.price if best_bid.timestamp < best_ask.timestamp else best_ask.price
            trade_qty = min(best_bid.quantity, best_ask.quantity)

            # ensure buyer can actually pay
            cost = trade_qty * trade_price
            paid = best_bid.owner.pay_in_silver(cost)
            if paid < cost:
                trade_qty = paid / trade_price
                cost = paid
            if trade_qty <= 1e-6:
                best_bid.quantity = 0
                i += 1
                continue

            self._fill_order(best_bid, best_ask, trade_qty, trade_price, cost, sim_day)

            if best_bid.quantity <= 1e-6:
                i += 1
            if best_ask.quantity <= 1e-6:
                j += 1

        # prune empty orders
        self.bids[item] = [b for b in bids if b.quantity > 1e-6]
        self.asks[item] = [a for a in asks if a.quantity > 1e-6]

    def _fill_order(self, bid: MarketOrder, ask: MarketOrder,
                    qty: float, price: float, cost: float, sim_day: int) -> None:
        """Execute the trade & book‑keep everything."""
        item = ask.item

        # pay seller
        ask.owner.receive_silver(cost)

        # update physical ownership
        self.owner_map[item][ask.owner] -= qty
        if self.owner_map[item][ask.owner] <= 1e-6:
            del self.owner_map[item][ask.owner]
        self.owner_map[item][bid.owner] += qty

        # fix for_sale_map –––––––––––––––––––––––––––––––––––––––––
        self._decrease_for_sale(ask.owner, item, qty)

        # shrink open order quantities
        ask.quantity -= qty
        bid.quantity -= qty

        # record trade
        trade_id = self.trade_id_counter
        self.trade_id_counter += 1
        self.trades.append({
            "id": trade_id,
            "time": time.time(),
            "sim_day": sim_day,
            "item": item,
            "quantity": qty,
            "price": price,
            "cost": cost,
            "buyer": getattr(bid.owner, "guild_name", getattr(bid.owner, "name", "???")),
            "seller": getattr(ask.owner, "guild_name", getattr(ask.owner, "name", "???")),
        })
        logger.debug(f"[Trade #{trade_id}] {qty:.2f} {item} @ {price:.2f} (day {sim_day})")

    # ──────────────────────────────────────────────────────────────
    # 3b) order expiry / relist
    # ──────────────────────────────────────────────────────────────
    def _remove_expired_orders(self, today: int, simulation=None) -> None:
        # bids
        for itm in list(self.bids):
            self.bids[itm] = [o for o in self.bids[itm] if o.valid_until_day >= today]

        # asks – collect those that expired so we can optionally relist
        expired: List[MarketOrder] = []
        for itm in list(self.asks):
            keep: List[MarketOrder] = []
            for o in self.asks[itm]:
                if o.valid_until_day >= today:
                    keep.append(o)
                else:
                    expired.append(o)
            self.asks[itm] = keep

        if simulation and expired:
            self._relist_expired_asks(expired, simulation)

    def _relist_expired_asks(self, expired_asks: List[MarketOrder], simulation) -> None:
        for ask in expired_asks:
            if ask.quantity <= 1e-6:
                continue
            new_price = _compute_relist_price(ask.item, ask.price, simulation)
            self.place_ask(
                owner=ask.owner,
                item=ask.item,
                quantity=ask.quantity,
                ask_price=new_price,
                current_day=simulation.current_day,
            )
            logger.debug(f"{ask.owner} relisted {ask.quantity:.2f} {ask.item} @ {new_price:.2f}")

    # ──────────────────────────────────────────────────────────────
    # 4) Dynamic reference price
    # ──────────────────────────────────────────────────────────────
    def update_supply_demand(self) -> None:
        # reset tallies
        for rec in self.goods.values():
            rec["supply"] = rec["demand"] = 0.0
        for itm, lst in self.asks.items():
            self.goods[itm]["supply"] += sum(a.quantity for a in lst)
        for itm, lst in self.bids.items():
            self.goods[itm]["demand"] += sum(b.quantity for b in lst)

    def do_dynamic_price_adjustment(self) -> None:
        CAP = 5  # ×base_price
        for itm, rec in self.goods.items():
            sup, dem, p = rec["supply"], rec["demand"], rec["price"]
            if sup < 1e-4 and dem > 0:
                new_p = p * 1.02
            else:
                ratio = dem / sup if sup > 0 else float("inf")
                if ratio > 1:
                    new_p = p * (1 + min(0.02, ratio - 1))
                elif 0 < ratio < 1:
                    new_p = p * (1 - min(0.02, 1 - ratio))
                else:
                    new_p = p
            base = CATALOG.goods[itm].base_price
            rec["price"] = max(0.01, min(new_p, base * CAP))

    # ──────────────────────────────────────────────────────────────
    # 5) CSV dump (debug / viz)
    # ──────────────────────────────────────────────────────────────
    def write_order_book_to_csv(self, day: int | None = None) -> None:
        day_str = "NA" if day is None else str(day)
        fname = f"order_book_day_{day_str}.csv"
        with open(fname, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Item", "Type", "Price", "Quantity", "Owner"])
            for itm, lst in self.bids.items():
                for b in lst:
                    w.writerow([itm, "BID", f"{b.price:.2f}", f"{b.quantity:.2f}",
                                getattr(b.owner, 'guild_name', getattr(b.owner, 'name', '?'))])
            for itm, lst in self.asks.items():
                for a in lst:
                    w.writerow([itm, "ASK", f"{a.price:.2f}", f"{a.quantity:.2f}",
                                getattr(a.owner, 'guild_name', getattr(a.owner, 'name', '?'))])
        logger.debug("Wrote order book to %s", fname)
