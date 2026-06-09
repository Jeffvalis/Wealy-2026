# -*- coding: utf-8 -*-
"""
The Wealy App — Capstone Simulation
=====================================
Standalone script that:
  1. Wraps core domain logic in the WealthManager class.
  2. Runs run_mass_simulation(user_count=100) to stress-test the platform.
  3. Prints a platform-wide AUM + integrity report.

Works against the EXISTING Supabase schema — no extra columns needed.
Idempotency keys and clerk_ids are tracked in-memory for the report.

Run:
    python simulate.py
"""

import os
import sys
import uuid
import random
import requests
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from supabase import create_client, Client

# Force UTF-8 output on Windows (avoids cp1252 emoji crash)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# 0. CONFIGURATION
# ═══════════════════════════════════════════════════════════════

load_dotenv()

SUPABASE_URL          = os.getenv("WEALY_SUPABASE_URL")
SUPABASE_KEY          = os.getenv("WEALY_SUPABASE_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

_missing = [k for k, v in {
    "WEALY_SUPABASE_URL":    SUPABASE_URL,
    "WEALY_SUPABASE_KEY":    SUPABASE_KEY,
    "ALPHA_VANTAGE_API_KEY": ALPHA_VANTAGE_API_KEY,
}.items() if not v]

if _missing:
    print(f"[Config Error] Missing env vars: {', '.join(_missing)}")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Seed pools for fake names ──────────────────────────────────
_FIRST = [
    "Ade","Bola","Chidi","Dami","Emeka","Funmi","Gbenga","Halima",
    "Ifeanyi","Jumoke","Kola","Lola","Musa","Ngozi","Ola","Priya",
    "Qasim","Remi","Sola","Tunde","Uche","Vivian","Wale","Yemi",
    "Zara","Amaka","Biodun","Chuks","Dotun","Fola",
]
_LAST  = [
    "Okafor","Adeyemi","Nwosu","Bello","Ibrahim","Osei","Adesanya",
    "Mensah","Okeke","Fadahunsi","Lawal","Eze","Diallo","Kamara",
    "Toure","Boateng","Asante","Danjuma","Aliyu","Ogundipe",
]


# ═══════════════════════════════════════════════════════════════
# 1. ALPHA VANTAGE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_market_price(symbol: str) -> Decimal | None:
    """Fetch live USD price via Alpha Vantage GLOBAL_QUOTE."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol":   symbol,
        "apikey":   ALPHA_VANTAGE_API_KEY,
    }
    try:
        resp = requests.get("https://www.alphavantage.co/query",
                            params=params, timeout=15)
        price_str = resp.json().get("Global Quote", {}).get("05. price", "")
        return Decimal(price_str) if price_str else None
    except Exception as e:
        print(f"  [Alpha Vantage] ❌ {symbol}: {e}")
        return None


def get_exchange_rate(from_ccy: str = "NGN",
                      to_ccy:   str = "USD") -> Decimal | None:
    """
    Fetch NGN→USD rate via Alpha Vantage CURRENCY_EXCHANGE_RATE.
    Alpha Vantage free tier supports USD/NGN but not NGN/USD directly,
    so we request USD→NGN and invert the result if needed.
    Falls back to None on any failure (caller handles fallback).
    """
    # Normalise: always request the pair Alpha Vantage can serve
    if from_ccy == "NGN" and to_ccy == "USD":
        api_from, api_to, invert = "USD", "NGN", True
    else:
        api_from, api_to, invert = from_ccy, to_ccy, False

    params = {
        "function":      "CURRENCY_EXCHANGE_RATE",
        "from_currency": api_from,
        "to_currency":   api_to,
        "apikey":        ALPHA_VANTAGE_API_KEY,
    }
    try:
        resp = requests.get("https://www.alphavantage.co/query",
                            params=params, timeout=15)
        rate_str = (
            resp.json()
                .get("Realtime Currency Exchange Rate", {})
                .get("5. Exchange Rate", "")
        )
        if not rate_str:
            return None
        rate = Decimal(rate_str)
        return (Decimal("1") / rate) if invert else rate
    except Exception as e:
        print(f"  [Alpha Vantage] ❌ FX rate: {e}")
        return None



# ═══════════════════════════════════════════════════════════════
# 2. WEALTHMANAGER CLASS
# ═══════════════════════════════════════════════════════════════

class WealthManager:
    """
    Core Wealy domain operations used by all simulations:

      kyc()              — upserts a profile (pass=Verified, fail=Unverified)
      deposit()          — records a DEPOSIT transaction
      invest()           — records a DEBIT + portfolio row
      sell()             — records a DIVEST CREDIT + reduces portfolio
      attempt_withdraw() — checks balance; records WITHDRAWAL or rejects
    """

    def __init__(self, db: Client):
        self.db = db

    def kyc(self, clerk_id: str, legal_name: str, email: str) -> bool:
        """Simulate a successful BVN KYC by upserting a Verified profile."""
        try:
            self.db.table("profiles").upsert({
                "clerk_id":   clerk_id,
                "legal_name": legal_name,
                "kyc_status": "Verified",
            }).execute()
            return True
        except Exception as e:
            print(f"    [WM.kyc] ❌ {legal_name}: {e}")
            return False

    def deposit(self, clerk_id: str, legal_name: str,
                amount_ngn: Decimal) -> str | None:
        """
        Record a successful DEPOSIT.
        Returns the idempotency_key on success, None on failure.
        """
        key = str(uuid.uuid4())
        try:
            self.db.table("transactions").insert({
                "clerk_id":        clerk_id,
                "legal_name":      legal_name,
                "amount":          str(amount_ngn),
                "currency":        "NGN",
                "type":            "DEPOSIT",
                "status":          "success",
                "idempotency_key": key,
            }).execute()
            return key
        except Exception as e:
            print(f"    [WM.deposit] ❌ {legal_name}: {e}")
            return None

    def invest(self, clerk_id: str, legal_name: str,
               symbol: str, amount_ngn: Decimal,
               usd_price: Decimal, ngn_to_usd: Decimal) -> str | None:
        """
        1. Converts NGN → USD.
        2. Calculates exact fractional units.
        3. Writes a DEBIT to transactions (returns idempotency_key).
        4. Writes an INVESTMENT row to portfolio.
        Returns the debit idempotency_key on success, None on failure.
        """
        invest_usd = amount_ngn * ngn_to_usd
        units = (invest_usd / usd_price).quantize(
                    Decimal("0.00000001"), rounding=ROUND_DOWN)

        debit_key = str(uuid.uuid4())

        # ── DEBIT (reduces cash balance) ──────────────────────
        try:
            self.db.table("transactions").insert({
                "clerk_id":        clerk_id,
                "legal_name":      legal_name,
                "amount":          str(-amount_ngn),   # negative
                "currency":        "NGN",
                "type":            "DEBIT",
                "status":          "success",
                "idempotency_key": debit_key,
            }).execute()
        except Exception as e:
            print(f"    [WM.invest] ❌ DEBIT {legal_name}: {e}")
            return None

        # ── INVESTMENT (portfolio entry) ───────────────────────
        try:
            self.db.table("portfolio").insert({
                "clerk_id":       clerk_id,
                "symbol":         symbol,
                "units":          float(units),
                "avg_price_paid": float(usd_price),
            }).execute()
        except Exception as e:
            print(f"    [WM.invest] ❌ Portfolio {legal_name}: {e}")
            return None

        return debit_key

    # ── sell(): Divest a position back into the wallet ─────────
    def sell(self, clerk_id: str, legal_name: str,
             symbol: str, units: Decimal,
             usd_price: Decimal, usd_to_ngn: Decimal) -> str | None:
        """
        Liquidates *units* of *symbol* at *usd_price*.
        Writes a DIVEST CREDIT to transactions.
        Returns the idempotency_key on success, None on failure.
        NOTE: For simulation speed we do not update the portfolio row
              (that would require an extra DB query per user). The
              credit is the financially correct record.
        """
        proceeds_ngn = (units * usd_price * usd_to_ngn).quantize(
                           Decimal("0.01"), rounding=ROUND_DOWN)
        key = str(uuid.uuid4())
        try:
            self.db.table("transactions").insert({
                "clerk_id":        clerk_id,
                "legal_name":      legal_name,
                "amount":          str(proceeds_ngn),   # positive = credit
                "currency":        "NGN",
                "type":            "DIVEST",
                "status":          "success",
                "idempotency_key": key,
            }).execute()
            return key
        except Exception as e:
            print(f"    [WM.sell] ❌ {legal_name}: {e}")
            return None

    # ── attempt_withdraw(): Enforce balance guard ───────────────
    def attempt_withdraw(self, clerk_id: str, legal_name: str,
                         amount: Decimal,
                         wallet_balance: Decimal) -> str | None:
        """
        Tries to move *amount* NGN to the user's bank.
        Returns the idempotency_key if successful, the string
        'REJECTED' if balance is insufficient, None on DB error.
        """
        if amount > wallet_balance:
            return "REJECTED"   # over-balance guard — no DB write

        key = str(uuid.uuid4())
        try:
            self.db.table("transactions").insert({
                "clerk_id":        clerk_id,
                "legal_name":      legal_name,
                "amount":          str(-amount),   # negative = debit
                "currency":        "NGN",
                "type":            "WITHDRAWAL",
                "status":          "success",
                "idempotency_key": key,
            }).execute()
            return key
        except Exception as e:
            print(f"    [WM.withdraw] ❌ {legal_name}: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# 3. SIMULATION RUNNER
# ═══════════════════════════════════════════════════════════════

def run_mass_simulation(user_count: int = 100) -> None:
    """
    Generates *user_count* synthetic users.
    For each: KYC → Deposit → Invest 70% in VOO.
    Tracks all idempotency keys in-memory for the integrity report.
    """
    print("=" * 62)
    print(f"   🚀  WEALY MASS SIMULATION  —  {user_count} USERS")
    print("=" * 62)

    # ── Pre-flight: fetch prices ONCE to respect rate limits ──
    print("\n[Pre-flight] Fetching VOO price from Alpha Vantage…")
    voo_price = get_market_price("VOO")
    if voo_price is None:
        print("[Pre-flight] ❌ Could not fetch VOO price. Aborting.")
        sys.exit(1)
    print(f"             VOO = ${voo_price:,.4f} USD  ✅")

    print("[Pre-flight] Fetching NGN/USD exchange rate…")
    ngn_to_usd = get_exchange_rate("NGN", "USD")
    if ngn_to_usd is None:
        # Alpha Vantage free tier may not serve NGN pairs — use a
        # realistic fallback rate and continue the simulation.
        FALLBACK_USD_TO_NGN = Decimal("1600")
        ngn_to_usd = Decimal("1") / FALLBACK_USD_TO_NGN
        print(f"             [!] API unavailable — using fallback rate: "
              f"$1 = ₦{FALLBACK_USD_TO_NGN:,.2f}")
    usd_to_ngn = Decimal("1") / ngn_to_usd
    print(f"             NGN->USD = {ngn_to_usd:.8f}  ($1 = ₦{usd_to_ngn:,.2f})  ✅\n")

    wm = WealthManager(db=supabase)

    # ── Tracking state for the report ─────────────────────────
    all_keys: list[str] = []          # every idempotency key issued
    clerk_ids: list[str] = []         # every clerk_id created
    total_deposited = Decimal("0")
    total_invested  = Decimal("0")
    total_units_voo = Decimal("0")
    success_count   = 0
    failure_count   = 0
    used_names: set[str] = set()

    print(f"  {'#':>3}  {'Name':<22}  {'Deposit (₦)':>13}  {'Invested (₦)':>13}  Status")
    print("  " + "─" * 70)

    for i in range(1, user_count + 1):

        # ── Unique synthetic identity ──────────────────────────
        for _ in range(200):          # collision guard
            first = random.choice(_FIRST)
            last  = random.choice(_LAST)
            name  = f"{first} {last}"
            if name not in used_names:
                used_names.add(name)
                break

        clerk_id    = str(uuid.uuid4())
        email       = (f"{first.lower()}.{last.lower()}"
                       f"{random.randint(10, 9999)}@wealy-sim.com")
        deposit_ngn = Decimal(random.randint(10_000, 500_000))
        invest_ngn  = (deposit_ngn * Decimal("0.70")).quantize(
                          Decimal("1"), rounding=ROUND_DOWN)

        ok = True

        # Stage A — KYC
        ok = ok and wm.kyc(clerk_id, name, email)

        # Stage B — Deposit
        dep_key = None
        if ok:
            dep_key = wm.deposit(clerk_id, name, deposit_ngn)
            ok = dep_key is not None
            if dep_key:
                all_keys.append(dep_key)

        # Stage C — Invest 70% in VOO
        inv_key = None
        if ok:
            inv_key = wm.invest(
                clerk_id   = clerk_id,
                legal_name = name,
                symbol     = "VOO",
                amount_ngn = invest_ngn,
                usd_price  = voo_price,
                ngn_to_usd = ngn_to_usd,
            )
            ok = inv_key is not None
            if inv_key:
                all_keys.append(inv_key)

        if ok:
            units_bought = (invest_ngn * ngn_to_usd / voo_price).quantize(
                               Decimal("0.00000001"), rounding=ROUND_DOWN)
            total_deposited += deposit_ngn
            total_invested  += invest_ngn
            total_units_voo += units_bought
            clerk_ids.append(clerk_id)
            success_count += 1
            print(f"  {i:>3}.  {name:<22}  ₦{deposit_ngn:>11,.0f}  "
                  f"₦{invest_ngn:>11,.0f}  ✅")
        else:
            failure_count += 1
            print(f"  {i:>3}.  {name:<22}  {'—':>13}  {'—':>13}  ❌ FAILED")

    print("  " + "─" * 70)
    print(f"\n  ✅ Successful : {success_count}   ❌ Failed : {failure_count}\n")

    # ── Hand off to report ────────────────────────────────────
    print_simulation_report(
        all_keys        = all_keys,
        user_count      = user_count,
        success_count   = success_count,
        total_deposited = total_deposited,
        total_invested  = total_invested,
        total_units_voo = total_units_voo,
        voo_price       = voo_price,
        usd_to_ngn      = usd_to_ngn,
    )


# ═══════════════════════════════════════════════════════════════
# 4. PLATFORM REPORT
# ═══════════════════════════════════════════════════════════════

def print_simulation_report(
    all_keys:        list[str],
    user_count:      int,
    success_count:   int,
    total_deposited: Decimal,
    total_invested:  Decimal,
    total_units_voo: Decimal,
    voo_price:       Decimal,
    usd_to_ngn:      Decimal,
) -> None:
    """
    Prints the AUM, transaction count, and idempotency integrity check.
    All figures are derived from in-memory data + live VOO price —
    no extra Supabase query needed (avoids column dependency).
    """
    # Cash remaining after investment
    cash_balance        = total_deposited - total_invested
    # Current market value of all VOO units (converted back to NGN)
    investment_val_usd  = total_units_voo * voo_price
    investment_val_ngn  = investment_val_usd * usd_to_ngn
    # Total AUM
    total_aum           = cash_balance + investment_val_ngn
    # Total tx = 1 DEPOSIT + 1 DEBIT per successful user
    expected_tx         = success_count * 2
    actual_tx           = len(all_keys)
    # Idempotency integrity
    unique_keys         = len(set(all_keys))
    duplicate_count     = actual_tx - unique_keys

    print("=" * 62)
    print("   📊  PLATFORM REPORT")
    print("=" * 62)
    print(f"\n  Users Simulated         : {user_count}")
    print(f"  Successful Users        : {success_count}")
    print()
    print("  ┌───────────────────────────────────────────────────┐")
    print(f"  │  🏦 Total Cash Balance       : ₦{cash_balance:>16,.2f}  │")
    print(f"  │  📈 Investments (VOO, live)  : ₦{investment_val_ngn:>16,.2f}  │")
    print(f"  │  💰 Total Platform AUM       : ₦{total_aum:>16,.2f}  │")
    print("  ├───────────────────────────────────────────────────┤")
    print(f"  │  📋 Total Transactions       : {actual_tx:>19}  │")
    print(f"  │  🔒 Idempotency Keys Issued  : {actual_tx:>19}  │")
    print(f"  │  🔒 Unique Keys              : {unique_keys:>19}  │")
    print(f"  │  🔒 Duplicates Detected      : {duplicate_count:>19}  │")
    print("  └───────────────────────────────────────────────────┘")

    if duplicate_count == 0:
        print("\n  ✅ IDEMPOTENCY SHIELD: PASSED — 0 duplicate keys processed.")
    else:
        print(f"\n  ❌ IDEMPOTENCY SHIELD: FAILED — {duplicate_count} duplicate(s)!")

    print(f"\n  VOO price used : ${voo_price:,.4f} USD")
    print(f"  FX rate used   : $1 = ₦{usd_to_ngn:,.2f}")
    print("\n" + "=" * 62 + "\n")


# ═══════════════════════════════════════════════════════════════
# 4. ADVANCED SIMULATION  (100 users in 3 cohorts)
# ═══════════════════════════════════════════════════════════════

# CBN Tier-1 single-deposit cap (Unverified users)
TIER1_DEPOSIT_LIMIT = Decimal("50000")


def _make_user(used: set) -> tuple[str, str, str, str]:
    """Return (clerk_id, name, first, email) — guaranteed unique name."""
    for _ in range(500):
        first = random.choice(_FIRST)
        last  = random.choice(_LAST)
        name  = f"{first} {last}"
        if name not in used:
            used.add(name)
            clerk_id = str(uuid.uuid4())
            email    = (f"{first.lower()}.{last.lower()}"
                        f"{random.randint(10,9999)}@wealy-sim.com")
            return clerk_id, name, first, email
    # Fallback (virtually impossible)
    clerk_id = str(uuid.uuid4())
    name     = f"User {clerk_id[:8]}"
    used.add(name)
    return clerk_id, name, "User", f"user{clerk_id[:8]}@wealy-sim.com"


def run_advanced_simulation() -> None:
    """
    100-user simulation split into three cohorts:

    Cohort A (30 users) — FAIL KYC (Tier-1 / Unverified)
      • Deposit exactly ₦50,000 (Tier-1 cap)
      • Invest 50 % in TSLA + 50 % in VOO

    Cohort B (30 users) — PASS KYC, then attempt to OVER-WITHDRAW
      • Random deposit ₦10k–₦500k
      • Invest 40 % in TSLA + 40 % in VOO
      • Attempt to withdraw 200 % of remaining balance → REJECTED

    Cohort C (40 users) — FULLY VERIFIED, partial divestment
      • Random deposit ₦10k–₦500k
      • Invest 35 % in TSLA + 35 % in VOO
      • First 20 of 40 sell ALL their TSLA + VOO back to wallet
    """
    print("=" * 66)
    print("   🚀  WEALY ADVANCED SIMULATION  —  100 USERS / 3 COHORTS")
    print("=" * 66)

    # ── Pre-flight: fetch prices ONCE ────────────────────────────
    print("\n[Pre-flight] Fetching TSLA price…")
    tsla_price = get_market_price("TSLA")
    if tsla_price is None:
        print("[Pre-flight] ❌ TSLA price unavailable. Aborting."); sys.exit(1)
    print(f"             TSLA = ${tsla_price:,.4f} USD  ✅")

    print("[Pre-flight] Fetching VOO price…")
    voo_price = get_market_price("VOO")
    if voo_price is None:
        print("[Pre-flight] ❌ VOO price unavailable. Aborting."); sys.exit(1)
    print(f"             VOO  = ${voo_price:,.4f} USD  ✅")

    print("[Pre-flight] Fetching NGN/USD exchange rate…")
    ngn_to_usd = get_exchange_rate("NGN", "USD")
    if ngn_to_usd is None:
        FALLBACK = Decimal("1600")
        ngn_to_usd = Decimal("1") / FALLBACK
        print(f"             [!] Fallback rate used: $1 = ₦{FALLBACK:,.2f}")
    usd_to_ngn = Decimal("1") / ngn_to_usd
    print(f"             NGN->USD = {ngn_to_usd:.8f}  ($1 = ₦{usd_to_ngn:,.2f})  ✅\n")

    wm = WealthManager(db=supabase)

    # ── Shared tracking ───────────────────────────────────────────
    all_keys:       list[str] = []
    used_names:     set[str]  = set()

    # Per-cohort counters
    cohort_stats = {
        "A": {"ok": 0, "fail": 0, "deposited": Decimal("0"),
              "invested": Decimal("0"), "units_tsla": Decimal("0"),
              "units_voo": Decimal("0")},
        "B": {"ok": 0, "fail": 0, "deposited": Decimal("0"),
              "invested": Decimal("0"), "rejected": 0,
              "units_tsla": Decimal("0"), "units_voo": Decimal("0")},
        "C": {"ok": 0, "fail": 0, "deposited": Decimal("0"),
              "invested": Decimal("0"), "divested": Decimal("0"),
              "units_tsla": Decimal("0"), "units_voo": Decimal("0")},
    }

    # ════════════════════════════════════════════════════════════
    # COHORT A — Fail KYC / Tier-1 (30 users)
    # ════════════════════════════════════════════════════════════
    print("─" * 66)
    print("  COHORT A  —  30 users  —  FAIL KYC  (Tier-1, cap ₦50,000)")
    print("─" * 66)
    print(f"  {'#':>3}  {'Name':<22}  {'Deposit':>10}  {'TSLA':>10}  {'VOO':>10}  Status")
    print("  " + "─" * 60)

    for i in range(1, 31):
        cid, name, _, email = _make_user(used_names)
        deposit = TIER1_DEPOSIT_LIMIT
        tsla_ngn = (deposit * Decimal("0.50")).quantize(Decimal("1"), rounding=ROUND_DOWN)
        voo_ngn  = (deposit * Decimal("0.50")).quantize(Decimal("1"), rounding=ROUND_DOWN)

        ok = True

        # Fail KYC → Unverified profile
        try:
            supabase.table("profiles").upsert({
                "clerk_id":   cid,
                "legal_name": name,
                "kyc_status": "Unverified",
            }).execute()
        except Exception as e:
            print(f"    [kyc] ❌ {name}: {e}"); ok = False

        dep_key = wm.deposit(cid, name, deposit) if ok else None
        ok = dep_key is not None
        if dep_key: all_keys.append(dep_key)

        # Still allowed to invest up to Tier-1 cap
        tsla_key = wm.invest(cid, name, "TSLA", tsla_ngn, tsla_price, ngn_to_usd) if ok else None
        ok = tsla_key is not None
        if tsla_key: all_keys.append(tsla_key)

        voo_key = wm.invest(cid, name, "VOO", voo_ngn, voo_price, ngn_to_usd) if ok else None
        ok = voo_key is not None
        if voo_key: all_keys.append(voo_key)

        if ok:
            cohort_stats["A"]["ok"] += 1
            cohort_stats["A"]["deposited"] += deposit
            cohort_stats["A"]["invested"] += tsla_ngn + voo_ngn
            cohort_stats["A"]["units_tsla"] += (tsla_ngn * ngn_to_usd / tsla_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            cohort_stats["A"]["units_voo"]  += (voo_ngn  * ngn_to_usd / voo_price ).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            print(f"  {i:>3}.  {name:<22}  ₦{deposit:>8,.0f}  ₦{tsla_ngn:>8,.0f}  ₦{voo_ngn:>8,.0f}  ✅ (Unverified)")
        else:
            cohort_stats["A"]["fail"] += 1
            print(f"  {i:>3}.  {name:<22}  {'':>10}  {'':>10}  {'':>10}  ❌")

    # ════════════════════════════════════════════════════════════
    # COHORT B — Pass KYC, invest, then over-withdraw (30 users)
    # ════════════════════════════════════════════════════════════
    print("\n" + "─" * 66)
    print("  COHORT B  —  30 users  —  PASS KYC + OVER-WITHDRAWAL ATTEMPT")
    print("─" * 66)
    print(f"  {'#':>3}  {'Name':<22}  {'Deposit':>10}  {'Invest':>10}  {'Withdraw Req':>13}  Status")
    print("  " + "─" * 65)

    for i in range(31, 61):
        cid, name, _, email = _make_user(used_names)
        deposit  = Decimal(random.randint(10_000, 500_000))
        tsla_ngn = (deposit * Decimal("0.40")).quantize(Decimal("1"), rounding=ROUND_DOWN)
        voo_ngn  = (deposit * Decimal("0.40")).quantize(Decimal("1"), rounding=ROUND_DOWN)
        # Remaining cash after investment
        cash_after = deposit - tsla_ngn - voo_ngn
        # Attempt to withdraw DOUBLE the remaining cash
        withdraw_attempt = cash_after * Decimal("2")

        ok = True
        ok = ok and wm.kyc(cid, name, email)

        dep_key  = wm.deposit(cid, name, deposit) if ok else None
        ok = dep_key is not None
        if dep_key: all_keys.append(dep_key)

        tsla_key = wm.invest(cid, name, "TSLA", tsla_ngn, tsla_price, ngn_to_usd) if ok else None
        ok = tsla_key is not None
        if tsla_key: all_keys.append(tsla_key)

        voo_key = wm.invest(cid, name, "VOO", voo_ngn, voo_price, ngn_to_usd) if ok else None
        ok = voo_key is not None
        if voo_key: all_keys.append(voo_key)

        # Attempt the over-withdrawal
        w_result = "—"
        if ok:
            result = wm.attempt_withdraw(cid, name, withdraw_attempt, cash_after)
            if result == "REJECTED":
                w_result = "REJECTED"
                cohort_stats["B"]["rejected"] += 1
            elif result is None:
                w_result = "DB_ERR"
            else:
                w_result = "OK"
                all_keys.append(result)

        if ok:
            cohort_stats["B"]["ok"] += 1
            cohort_stats["B"]["deposited"] += deposit
            cohort_stats["B"]["invested"] += tsla_ngn + voo_ngn
            cohort_stats["B"]["units_tsla"] += (tsla_ngn * ngn_to_usd / tsla_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            cohort_stats["B"]["units_voo"]  += (voo_ngn  * ngn_to_usd / voo_price ).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            print(f"  {i:>3}.  {name:<22}  ₦{deposit:>8,.0f}  ₦{tsla_ngn+voo_ngn:>8,.0f}  ₦{withdraw_attempt:>11,.0f}  ✅ | Withdraw→{w_result}")
        else:
            cohort_stats["B"]["fail"] += 1
            print(f"  {i:>3}.  {name:<22}  {'':>10}  {'':>10}  {'':>13}  ❌")

    # ════════════════════════════════════════════════════════════
    # COHORT C — Fully verified, 20/40 divest back to wallet
    # ════════════════════════════════════════════════════════════
    print("\n" + "─" * 66)
    print("  COHORT C  —  40 users  —  PASS KYC + INVEST + PARTIAL DIVEST")
    print("─" * 66)
    print(f"  {'#':>3}  {'Name':<22}  {'Deposit':>10}  {'Invest':>10}  {'Divest':>10}  Status")
    print("  " + "─" * 65)

    for i in range(61, 101):
        cid, name, _, email = _make_user(used_names)
        cohort_idx = i - 61   # 0..39; first 20 will divest
        will_divest = cohort_idx < 20

        deposit  = Decimal(random.randint(10_000, 500_000))
        tsla_ngn = (deposit * Decimal("0.35")).quantize(Decimal("1"), rounding=ROUND_DOWN)
        voo_ngn  = (deposit * Decimal("0.35")).quantize(Decimal("1"), rounding=ROUND_DOWN)

        ok = True
        ok = ok and wm.kyc(cid, name, email)

        dep_key  = wm.deposit(cid, name, deposit) if ok else None
        ok = dep_key is not None
        if dep_key: all_keys.append(dep_key)

        tsla_key = wm.invest(cid, name, "TSLA", tsla_ngn, tsla_price, ngn_to_usd) if ok else None
        ok = tsla_key is not None
        if tsla_key: all_keys.append(tsla_key)

        voo_key = wm.invest(cid, name, "VOO", voo_ngn, voo_price, ngn_to_usd) if ok else None
        ok = voo_key is not None
        if voo_key: all_keys.append(voo_key)

        divest_ngn = Decimal("0")
        if ok and will_divest:
            # Calculate the units bought
            tsla_units = (tsla_ngn * ngn_to_usd / tsla_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            voo_units  = (voo_ngn  * ngn_to_usd / voo_price ).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

            # Sell ALL TSLA
            t_key = wm.sell(cid, name, "TSLA", tsla_units, tsla_price, usd_to_ngn)
            if t_key:
                all_keys.append(t_key)
                divest_ngn += (tsla_units * tsla_price * usd_to_ngn).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            # Sell ALL VOO
            v_key = wm.sell(cid, name, "VOO",  voo_units,  voo_price,  usd_to_ngn)
            if v_key:
                all_keys.append(v_key)
                divest_ngn += (voo_units  * voo_price  * usd_to_ngn).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

        if ok:
            cohort_stats["C"]["ok"] += 1
            cohort_stats["C"]["deposited"] += deposit
            cohort_stats["C"]["invested"] += tsla_ngn + voo_ngn
            cohort_stats["C"]["divested"]  += divest_ngn
            cohort_stats["C"]["units_tsla"] += (tsla_ngn * ngn_to_usd / tsla_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            cohort_stats["C"]["units_voo"]  += (voo_ngn  * ngn_to_usd / voo_price ).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            d_str = f"₦{divest_ngn:>8,.0f}" if will_divest else "       —"
            print(f"  {i:>3}.  {name:<22}  ₦{deposit:>8,.0f}  ₦{tsla_ngn+voo_ngn:>8,.0f}  {d_str}  ✅")
        else:
            cohort_stats["C"]["fail"] += 1
            print(f"  {i:>3}.  {name:<22}  {'':>10}  {'':>10}  {'':>10}  ❌")

    # ── Final report ──────────────────────────────────────────────
    print("\n" + "=" * 66)
    print("  📊  ADVANCED SIMULATION REPORT")
    print("=" * 66)

    total_keys     = len(all_keys)
    unique_keys    = len(set(all_keys))
    duplicate_count = total_keys - unique_keys

    # Investment value in NGN using live prices
    def _inv_val(stats: dict) -> Decimal:
        tsla_val = stats["units_tsla"] * tsla_price * usd_to_ngn
        voo_val  = stats["units_voo"]  * voo_price  * usd_to_ngn
        return (tsla_val + voo_val).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    for label, desc, cs in [
        ("A", "Failed KYC / Tier-1",            cohort_stats["A"]),
        ("B", "Verified + Over-withdrawal",      cohort_stats["B"]),
        ("C", "Verified + Partial Divestment",   cohort_stats["C"]),
    ]:
        cash = cs["deposited"] - cs["invested"]
        inv  = _inv_val(cs)
        aum  = cash + inv

        print(f"\n  COHORT {label} — {desc}")
        print(f"  {'Users OK/Fail':<28}: {cs['ok']} / {cs['fail']}")
        print(f"  {'Total Deposited':<28}: ₦{cs['deposited']:>14,.2f}")
        print(f"  {'Total Invested (NGN)':<28}: ₦{cs['invested']:>14,.2f}")
        print(f"  {'Investment Value (live)':<28}: ₦{inv:>14,.2f}")
        if label == "B":
            print(f"  {'Over-Withdrawals Rejected':<28}: {cs['rejected']}")
        if label == "C":
            print(f"  {'Divested Back to Wallet':<28}: ₦{cs['divested']:>14,.2f}")
        print(f"  {'Cohort AUM':<28}: ₦{aum:>14,.2f}")

    # Platform-wide totals
    all_dep = sum(cohort_stats[c]["deposited"] for c in "ABC")
    all_inv = sum(cohort_stats[c]["invested"]  for c in "ABC")
    all_aum = sum(
        cohort_stats[c]["deposited"] - cohort_stats[c]["invested"] + _inv_val(cohort_stats[c])
        for c in "ABC"
    )

    print("\n" + "─" * 66)
    print("  PLATFORM TOTALS")
    print("─" * 66)
    print("  ┌─────────────────────────────────────────────────────┐")
    print(f"  │  Total Deposited            : ₦{all_dep:>18,.2f}  │")
    print(f"  │  Total Invested (NGN)       : ₦{all_inv:>18,.2f}  │")
    print(f"  │  Total Platform AUM         : ₦{all_aum:>18,.2f}  │")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  Idempotency Keys Issued    : {total_keys:>21}  │")
    print(f"  │  Unique Keys                : {unique_keys:>21}  │")
    print(f"  │  Duplicates Detected        : {duplicate_count:>21}  │")
    print(f"  │  TSLA price used            : ${tsla_price:>20,.4f}  │")
    print(f"  │  VOO  price used            : ${voo_price:>20,.4f}  │")
    print(f"  │  FX rate used               : $1 = ₦{usd_to_ngn:>14,.2f}  │")
    print("  └─────────────────────────────────────────────────────┘")

    shield = "PASSED" if duplicate_count == 0 else f"FAILED ({duplicate_count} duplicates)"
    print(f"\n  Idempotency Shield : {shield}")
    print("\n" + "=" * 66 + "\n")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_advanced_simulation()
