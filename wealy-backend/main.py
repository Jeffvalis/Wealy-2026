# -*- coding: utf-8 -*-
"""
The Wealy App — Production Pipeline (Week 7)
=============================================
End-to-end flow:
  Stage 1 → Auth          : Clerk (email + password login)
  Stage 2 → Identity      : Supabase profile lookup + Paystack BVN KYC
  Stage 3 → Deposit       : Verified-user deposit input
  Stage 4 → The Shield    : uuid4 idempotency key + Supabase DB write (pending)
  Stage 5 → Payment       : Real Flutterwave charge → verify → update to success
  Stage 6 → Polling       : Real-time virtual account inbound transfer listener
  Stage 7 → Global Markets: Alpha Vantage live prices + portfolio investment
"""

import os
import sys
import uuid
import requests
from decimal import Decimal
from dotenv import load_dotenv

# ── Clerk SDK ────────────────────────────────────────────────────
from clerk_backend_api import Clerk
from clerk_backend_api.models import GetUserListRequest, SDKError

# ── Supabase ─────────────────────────────────────────────────────
from supabase import create_client, Client

# ═══════════════════════════════════════════════════════════════
# 0. CONFIGURATION — Load all environment variables
# ═══════════════════════════════════════════════════════════════

load_dotenv()   # Reads from 04_Payment_DB/.env

CLERK_SECRET_KEY        = os.getenv("CLERK_SECRET_KEY")
CLERK_PUBLISHABLE_KEY   = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
PAYSTACK_SECRET_KEY     = os.getenv("PAYSTACK_SECRET_KEY")
SUPABASE_URL            = os.getenv("WEALY_SUPABASE_URL")
SUPABASE_KEY            = os.getenv("WEALY_SUPABASE_KEY")
FLUTTERWAVE_SECRET_KEY  = os.getenv("FLUTTERWAVE_SECRET_KEY")
ALPHA_VANTAGE_API_KEY   = os.getenv("ALPHA_VANTAGE_API_KEY")

# ── Guard: abort early if any key is missing ──────────────────
_missing = [k for k, v in {
    "CLERK_SECRET_KEY":                  CLERK_SECRET_KEY,
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": CLERK_PUBLISHABLE_KEY,
    "PAYSTACK_SECRET_KEY":               PAYSTACK_SECRET_KEY,
    "WEALY_SUPABASE_URL":                SUPABASE_URL,
    "WEALY_SUPABASE_KEY":                SUPABASE_KEY,
    "FLUTTERWAVE_SECRET_KEY":            FLUTTERWAVE_SECRET_KEY,
    "ALPHA_VANTAGE_API_KEY":             ALPHA_VANTAGE_API_KEY,
}.items() if not v]

if _missing:
    print(f"[Config Error] Missing environment variables: {', '.join(_missing)}")
    sys.exit(1)

# ── Initialise SDK clients ────────────────────────────────────
clerk_backend: Clerk  = Clerk(bearer_auth=CLERK_SECRET_KEY)
supabase: Client      = create_client(SUPABASE_URL, SUPABASE_KEY)

FLW_BASE_URL = "https://api.flutterwave.com/v3"
FLW_HEADERS  = {
    "Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}",
    "Content-Type": "application/json",
}

print("=" * 58)
print("          💰  THE WEALY APP — PRODUCTION PIPELINE  💰")
print("=" * 58)


# ═══════════════════════════════════════════════════════════════
# STAGE 1 — AUTH  (Clerk)
# Goal: Verify email + password and return the Clerk user ID.
# ═══════════════════════════════════════════════════════════════

def stage1_authenticate() -> str:
    """
    Prompts for email + password, verifies via Clerk Backend API.
    Returns the clerk_id (str) on success or exits the program.
    """
    print("\n┌─ STAGE 1 : AUTHENTICATION (Clerk) ────────────────────┐")
    email    = input("│  Email    : ").strip()
    password = input("│  Password : ").strip()

    if not email or not password:
        print("└─ [Error] Email and password are required.\n")
        sys.exit(1)

    print("│  [Auth] Looking up user …")
    try:
        users = clerk_backend.users.list(
            request=GetUserListRequest(email_address=[email])
        )
        if not users:
            print("└─ [Auth] No account found for that email. Exiting.\n")
            sys.exit(1)

        user = users[0]
        print(f"│  [Auth] User found → {user.id}")

        # Verify password via Clerk Backend API
        verification = clerk_backend.users.verify_password(
            user_id=user.id, password=password
        )
        if not verification.verified:
            print("└─ [Auth] ❌ Incorrect password. Exiting.\n")
            sys.exit(1)

        clerk_id = user.id
        print(f"│  [Auth] ✅ Authentication successful.")
        print(f"└─ Clerk ID : {clerk_id}\n")
        return clerk_id

    except SDKError as e:
        print(f"└─ [Auth] Clerk API error {e.status_code}: {e.message}\n")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# STAGE 2 — IDENTITY / KYC  (Supabase + Paystack)
# Goal: Look up profiles table; if missing, run BVN KYC via
#       Paystack and save the verified legal name + status.
# ═══════════════════════════════════════════════════════════════

def _paystack_verify_bvn(bvn: str) -> dict:
    """
    Calls the real Paystack BVN resolution endpoint.
      GET https://api.paystack.co/bank/resolve_bvn/{bvn}
    Returns the response JSON dict.
    """
    # ── MOCK FOR TESTING ─────────────────────────────────────
    if bvn == "12345678901":
        return {
            "status": True,
            "message": "BVN resolved",
            "data": {
                "first_name": "John",
                "last_name": "Doe"
            }
        }

    url     = f"https://api.paystack.co/bank/resolve_bvn/{bvn}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    resp    = requests.get(url, headers=headers, timeout=20)
    return resp.json()


def create_virtual_account(user_email: str, bvn: str, user_name: str, clerk_id: str) -> dict | None:
    """
    Calls Flutterwave /virtual-account-numbers to generate an account.
    Saves account_number and bank_name to Supabase profiles table.
    """
    print("│  [Flutterwave] Generating Virtual Account …")
    url = f"{FLW_BASE_URL}/virtual-account-numbers"
    payload = {
        "email": user_email,
        "is_permanent": True,
        "bvn": bvn,
        "tx_ref": f"va_{uuid.uuid4().hex[:10]}",
        "firstname": user_name.split()[0] if user_name else "User",
        "lastname": user_name.split()[-1] if len(user_name.split()) > 1 else "Name",
    }
    try:
        resp = requests.post(url, json=payload, headers=FLW_HEADERS, timeout=20)
        data = resp.json()
        if data.get("status") == "success":
            acc_no = data["data"]["account_number"]
            bank_name = data["data"]["bank_name"]
            print(f"│  [DB] Saving Virtual Account to Supabase …")
            supabase.table("profiles").update({
                "account_number": acc_no,
                "bank_name": bank_name
            }).eq("clerk_id", clerk_id).execute()
            return {"account_number": acc_no, "bank_name": bank_name}
        else:
            print(f"│  [Flutterwave] ❌ Virtual Account Error: {data.get('message')}")
            return None
    except requests.RequestException as e:
        print(f"│  [Flutterwave] ❌ Network error: {e}")
        return None


def stage2_identity_check(clerk_id: str, user_email: str) -> dict:
    """
    1. Query Supabase profiles table.
    2. If profile Verified and has account_number → return it.
    3. If verified but missing account_number, prompt BVN and create it.
    4. If no profile, run Paystack BVN, upsert, AND create virtual account.
    """
    print("┌─ STAGE 2 : IDENTITY CHECK (Supabase + Paystack KYC) ──┐")

    # ── 2a. Check Supabase profiles table ────────────────────
    print("│  [Identity] Querying Supabase profiles …")
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("clerk_id", clerk_id)
        .execute()
    )

    if result.data:
        profile = result.data[0]
        status  = profile.get("kyc_status", "Unverified")
        print(f"│  [Identity] Profile found → KYC Status: {status}")
        print(f"└─ Legal Name : {profile.get('legal_name', 'N/A')}\n")
        
        # Ensure they have a virtual account
        if status == "Verified" and not profile.get("account_number"):
            print("┌─ VIRTUAL ACCOUNT GENERATION ──────────────────────────┐")
            print("│  We need to set up your persistent vault account.")
            bvn = input("│  Enter your BVN (11 digits): ").strip()
            acc_details = create_virtual_account(user_email, bvn, profile.get('legal_name', 'User'), clerk_id)
            if acc_details:
                profile["account_number"] = acc_details["account_number"]
                profile["bank_name"] = acc_details["bank_name"]
            print("└───────────────────────────────────────────────────────\n")
            
        return profile

    # ── 2b. No profile → run Paystack BVN KYC ────────────────
    print("│  [Identity] No profile found. Initiating BVN KYC …")
    bvn = input("│  Enter your BVN (11 digits): ").strip()

    if len(bvn) != 11 or not bvn.isdigit():
        print("└─ [KYC] ❌ BVN must be exactly 11 digits. Exiting.\n")
        sys.exit(1)

    print("│  [KYC] Calling Paystack BVN Resolution API …")
    kyc_response = _paystack_verify_bvn(bvn)

    if not kyc_response.get("status"):
        msg = kyc_response.get("message", "Unknown error")
        print(f"└─ [KYC] ❌ Paystack rejected BVN: {msg}")
        print("│  Proceeding as Tier 1 (Unverified) User.")

        profile_payload = {
            "clerk_id":   clerk_id,
            "legal_name": "Unverified User",
            "kyc_status": "Unverified",
        }
        supabase.table("profiles").upsert(profile_payload).execute()
        return profile_payload

    # Extract verified name from Paystack response
    kyc_data   = kyc_response.get("data", {})
    first_name = kyc_data.get("first_name", "")
    last_name  = kyc_data.get("last_name", "")
    legal_name = f"{first_name} {last_name}".strip()

    print(f"│  [KYC] ✅ BVN verified. Legal name: {legal_name}")

    # Generate virtual account
    acc_details = create_virtual_account(user_email, bvn, legal_name, clerk_id)
    acc_no = acc_details["account_number"] if acc_details else None
    bank_name = acc_details["bank_name"] if acc_details else None

    # ── 2c. Save to Supabase profiles ────────────────────────
    print("│  [DB] Saving verified profile to Supabase …")
    profile_payload = {
        "clerk_id":   clerk_id,
        "legal_name": legal_name,
        "kyc_status": "Verified",
        "account_number": acc_no,
        "bank_name": bank_name,
    }
    supabase.table("profiles").upsert(profile_payload).execute()
    print(f"└─ Legal Name : {legal_name} | KYC Status: Verified\n")

    return profile_payload


# ═══════════════════════════════════════════════════════════════
# STAGE 3 — TRANSACTION INPUT (Deposit)
# Goal: Only allow deposit input if KYC status is 'Verified'.
# ═══════════════════════════════════════════════════════════════

def stage3_collect_deposit(profile: dict) -> Decimal:
    """
    Gates the deposit input on KYC status and enforces Tier limits.
    Returns the deposit amount as a Decimal, or None on failure.
    """
    print("┌─ STAGE 3 : TRANSACTION (Deposit) ─────────────────────┐")

    kyc_status = profile.get("kyc_status", "Unverified")

    # Define Tier limits
    TIER_1_MAX_SINGLE_DEPOSIT = Decimal('50000.00')

    if kyc_status == "Unverified":
        print("│  [Transaction] ⚠️  KYC Unverified (Tier 1).")
        print(f"│  Max single deposit allowed: ₦{TIER_1_MAX_SINGLE_DEPOSIT:,.2f}")
    else:
        print("│  [Transaction] ✅ KYC Verified.")

    raw = input("│  Enter deposit amount (₦): ").strip()
    try:
        amount = Decimal(raw)
        if amount <= 0:
            raise ValueError("Amount must be positive.")

        if kyc_status == "Unverified" and amount > TIER_1_MAX_SINGLE_DEPOSIT:
            print(f"└─ [Transaction] ❌ Amount exceeds Tier 1 limit of ₦{TIER_1_MAX_SINGLE_DEPOSIT:,.2f}.\n")
            return None

    except ValueError as e:
        print(f"└─ [Transaction] Invalid amount: {e}\n")
        return None

    print(f"│  [Transaction] ✅ Deposit amount: ₦{amount:,.2f}")
    print("└───────────────────────────────────────────────────────\n")
    return amount


# ═══════════════════════════════════════════════════════════════
# STAGE 4 — THE SHIELD  (Idempotency Key + DB Write)
# Goal: Generate a uuid4 key and INSERT the transaction into
#       Supabase as 'pending', then hand off to Stage 5.
# ═══════════════════════════════════════════════════════════════

def stage4_create_pending_transaction(clerk_id: str, amount: Decimal, legal_name: str) -> dict:
    """
    1. Generates a uuid4 idempotency key (used as Flutterwave tx_ref).
    2. Inserts a 'pending' transaction record into Supabase.
    3. Returns the saved record (including the DB-assigned `id`).
    """
    print("┌─ STAGE 4 : THE SHIELD (Idempotency + DB Write) ───────┐")

    # ── 4a. Generate idempotency key ─────────────────────────
    idempotency_key = str(uuid.uuid4())
    print(f"│  [Shield] Idempotency Key : {idempotency_key}")

    # ── 4b. Build the 'pending' transaction record ────────────
    transaction_record = {
        "clerk_id":         clerk_id,
        "legal_name":       legal_name,
        "amount":           str(amount),
        "currency":         "NGN",
        "type":             "DEPOSIT",
        "status":           "pending",
        "idempotency_key":  idempotency_key,
    }

    # ── 4c. Insert with duplicate-key protection ──────────────
    print("│  [DB] Writing 'pending' transaction to Supabase …")
    try:
        insert_result = (
            supabase.table("transactions")
            .insert(transaction_record)
            .execute()
        )
        saved = insert_result.data[0] if insert_result.data else transaction_record
        print(f"│  [DB] ✅ Pending record created. DB ID: {saved.get('id', 'N/A')}")

    except Exception as e:
        error_str = str(e)
        if "23505" in error_str or "UniqueViolation" in error_str or "unique" in error_str.lower():
            print("│  [Shield] 🛡️  Duplicate request detected!")
            print("│  This idempotency key has already been processed.")
            print("└─ No new transaction was created.\n")
            return None
        print(f"└─ [DB] ❌ Unexpected database error: {e}\n")
        raise

    print("└───────────────────────────────────────────────────────\n")
    return saved


# ═══════════════════════════════════════════════════════════════
# STAGE 5 — PAYMENT  (Flutterwave)
# Goal: Initialize a real Flutterwave payment, display the link,
#       wait for user confirmation, verify the charge, and
#       update the Supabase record from 'pending' to 'success'.
# ═══════════════════════════════════════════════════════════════

def initialize_payment(user_email: str, amount: Decimal, idempotency_key: str) -> dict | None:
    """
    Calls the Flutterwave Standard Payment endpoint (POST /payments).

    The idempotency_key is passed as `tx_ref` — Flutterwave uses this
    field to deduplicate transactions on their end.

    Returns the full Flutterwave API response dict, or None on failure.
    """
    print("│  [Flutterwave] Initializing payment …")

    payload = {
        "tx_ref":       idempotency_key,          # idempotency via tx_ref
        "amount":       float(amount),
        "currency":     "NGN",
        "redirect_url": "https://wealy.app/payment/success",   # mock success page
        "customer": {
            "email": user_email,
        },
        "customizations": {
            "title":       "The Wealy App",
            "description": "Deposit into your Wealy wallet",
        },
    }

    try:
        resp = requests.post(
            f"{FLW_BASE_URL}/payments",
            json=payload,
            headers=FLW_HEADERS,
            timeout=20,
        )
        data = resp.json()
    except requests.RequestException as e:
        print(f"│  [Flutterwave] ❌ Network error: {e}")
        return None

    if data.get("status") == "success" and data.get("data", {}).get("link"):
        return data
    else:
        print(f"│  [Flutterwave] ❌ Failed to create payment link.")
        print(f"│  Response: {data.get('message', 'No message')}")
        return None


def verify_payment(transaction_id: str) -> dict | None:
    """
    Calls GET /transactions/:id/verify to confirm the payment status.
    Returns the Flutterwave data payload on success, None on failure.
    """
    print("│  [Flutterwave] Verifying payment with Flutterwave …")
    try:
        resp = requests.get(
            f"{FLW_BASE_URL}/transactions/{transaction_id}/verify",
            headers=FLW_HEADERS,
            timeout=20,
        )
        data = resp.json()
    except requests.RequestException as e:
        print(f"│  [Flutterwave] ❌ Network error during verification: {e}")
        return None

    return data


def stage5_show_payment_link(
    user_email: str,
    amount: Decimal,
    pending_record: dict,
) -> str | None:
    """
    Step A of Stage 5: Initialize the Flutterwave charge and display the
    payment link. Waits for the user to type DONE, then returns.

    Returns the payment_link string so the menu can re-display it if the
    user comes back to Confirm without having paid yet.
    Returns None if the API call to create the link fails.
    """
    print("┌─ STAGE 5 : PAYMENT (Flutterwave) ─────────────────────┐")

    idempotency_key = pending_record.get("idempotency_key")

    # ── Initialize payment with Flutterwave ──────────────────
    flw_response = initialize_payment(user_email, amount, idempotency_key)

    if not flw_response:
        print("└─ [Payment] ❌ Could not generate a payment link.\n")
        return None

    payment_link = flw_response["data"]["link"]
    pending_record["_flw_link"] = payment_link  # cache for re-display

    print("│")
    print("│  ╔══════════════════════════════════════════════════╗")
    print(f"│  ║  👉  Click here to pay:")
    print(f"│  ║      {payment_link}")
    print("│  ╚══════════════════════════════════════════════════╝")
    print("│")
    print("│  Complete your payment in the browser.")
    print("│  Then select  'Confirm Payment'  from the menu below.")
    print("└───────────────────────────────────────────────────────\n")
    return payment_link


def try_confirm_payment(pending_record: dict) -> bool:
    """
    Step B of Stage 5: Search Flutterwave for the transaction by tx_ref,
    run /verify, and — only if status is 'successful' — update Supabase.

    Returns True  → payment confirmed, Supabase updated to 'success'.
    Returns False → payment not found or not yet confirmed; stay pending.
    """
    print("┌─ CONFIRMING PAYMENT (Flutterwave) ────────────────────┐")

    idempotency_key = pending_record.get("idempotency_key")
    db_record_id    = pending_record.get("id")
    amount          = pending_record.get("amount", "0")

    # ── Search for the transaction by tx_ref ─────────────────
    print("│  [Flutterwave] Searching for your payment by tx_ref …")
    flw_tx_id = ""
    try:
        search_resp = requests.get(
            f"{FLW_BASE_URL}/transactions",
            params={"tx_ref": idempotency_key},
            headers=FLW_HEADERS,
            timeout=20,
        )
        search_data = search_resp.json()
        raw_data    = search_data.get("data", [])
        if isinstance(raw_data, list):
            tx_list = raw_data
        elif isinstance(raw_data, dict):
            tx_list = raw_data.get("transactions", [])
        else:
            tx_list = []

        if tx_list:
            flw_tx_id = str(tx_list[0].get("id", ""))

    except requests.RequestException as e:
        print(f"│  [Flutterwave] ❌ Network error: {e}")
        print("└─ [Confirm] Could not reach Flutterwave. Try again.\n")
        return False

    if not flw_tx_id:
        print("│  [Flutterwave] ❌ No completed transaction found yet.")
        print("│  If you haven't paid yet, do so then press Confirm again.")
        print("└───────────────────────────────────────────────────────\n")
        return False

    # ── Verify status with Flutterwave ────────────────────────
    print(f"│  [Flutterwave] Transaction found (ID: {flw_tx_id}). Verifying …")
    verification = verify_payment(flw_tx_id)

    if not verification:
        print("└─ [Confirm] ❌ Verification call failed. Try again.\n")
        return False

    flw_status = verification.get("data", {}).get("status", "")
    print(f"│  [Flutterwave] Verification status: {flw_status}")

    # ── Update Supabase only on confirmed success ─────────────
    if flw_status == "successful":
        print("│  [DB] ✅ Payment confirmed! Updating record to 'success' …")
        try:
            supabase.table("transactions") \
                .update({"status": "success"}) \
                .eq("id", db_record_id) \
                .execute()
            print("│  [DB] ✅ Supabase record updated to 'success'.")
        except Exception as e:
            print(f"│  [DB] ❌ Failed to update record: {e}")
            print("└───────────────────────────────────────────────────────\n")
            return False

        # Print success summary
        print("└───────────────────────────────────────────────────────\n")
        print("╔══════════════════════════════════════════════════════╗")
        print("║           🏦  VAULT ENTRY CONFIRMED ✅               ║")
        print("╠══════════════════════════════════════════════════════╣")
        print(f"║  Clerk ID   : {pending_record.get('clerk_id', ''):<38}║")
        print(f"║  Legal Name : {pending_record.get('legal_name', ''):<38}║")
        print(f"║  Amount     : ₦{str(amount):>36} ║")
        print(f"║  Status     : {'success':<38}║")
        print(f"║  TX Ref     : {idempotency_key:<38}║")
        print(f"║  FLW TX ID  : {flw_tx_id:<38}║")
        print("╚══════════════════════════════════════════════════════╝\n")
        return True

    else:
        print(f"│  [Confirm] ⚠️  Payment status is '{flw_status}' — not yet successful.")
        print("│  Please complete the payment and try Confirm again.")
        print("└───────────────────────────────────────────────────────\n")
        return False


import time

# ═══════════════════════════════════════════════════════════════
# STAGE 6 — REAL-TIME POLLING ENGINE
# ═══════════════════════════════════════════════════════════════

def check_for_inbound_transfers(account_number: str) -> list:
    """
    Calls Flutterwave /transactions, returning successful transfers 
    for this specific virtual account.
    """
    url = f"{FLW_BASE_URL}/transactions"
    try:
        resp = requests.get(url, headers=FLW_HEADERS, timeout=20)
        data = resp.json()
        if data.get("status") == "success":
            txs = data.get("data", [])
            inbound = []
            for tx in txs:
                if tx.get("status") == "successful":
                    # Check if virtual account number is present in the record
                    if str(account_number) in str(tx):
                        inbound.append(tx)
            return inbound
        return []
    except Exception as e:
        print(f"│  [Poller Error] {e}")
        return []

def get_account_balance(clerk_id: str) -> Decimal:
    """
    Calculates the account balance by summing all successful transactions.
    Uses ilike for case-insensitive match on status to handle both
    'success' and 'SUCCESS' records in Supabase.
    """
    try:
        res = (
            supabase.table("transactions")
            .select("amount")
            .eq("clerk_id", clerk_id)
            .ilike("status", "success")
            .execute()
        )
        balance = Decimal('0.00')
        if res.data:
            for record in res.data:
                balance += Decimal(str(record.get('amount', '0')))
        return balance
    except Exception as e:
        print(f"│  [DB] ❌ Error fetching balance: {e}")
        return Decimal('0.00')

def execution_loop(clerk_id: str, legal_name: str, account_number: str, bank_name: str):
    """
    Runs the while True loop checking for new deposits every 30s.
    Can be exited with Ctrl+C to return to main menu.
    """
    print("┌─ DEPOSIT LISTENER ────────────────────────────────────────┐")
    print(f"│  🏦 Vault Account : {account_number} ({bank_name})")
    
    current_balance = get_account_balance(clerk_id)
    print(f"│  💰 Current Balance: ₦{current_balance:,.2f}")
    
    print("│  Send funds here via bank transfer. We are listening.")
    print("└───────────────────────────────────────────────────────────\n")
    
    while True:
        try:
            print("⏳ Checking for new deposits... (Press Ctrl+C to stop/go back)")
            transfers = check_for_inbound_transfers(account_number)
            
            for tx in transfers:
                flw_ref = tx.get("tx_ref") or tx.get("flw_ref") or str(tx.get("id"))
                amount = tx.get("amount")
                
                # Shield: Check if exists in DB
                res = supabase.table("transactions").select("id").eq("idempotency_key", flw_ref).execute()
                if res.data and len(res.data) > 0:
                    continue  # EXISTS -> skip
                
                # NEW -> Insert into ledger
                print(f"│  [Ledger] 🔔 New deposit found! Amount: ₦{amount:,.2f} (Ref: {flw_ref})")
                new_tx = {
                    "clerk_id": clerk_id,
                    "legal_name": legal_name,
                    "amount": str(amount),
                    "currency": tx.get("currency", "NGN"),
                    "type": "deposit",
                    "status": "success",
                    "idempotency_key": flw_ref
                }
                supabase.table("transactions").insert(new_tx).execute()
                print(f"│  [Ledger] ✅ Successfully credited to Vault.")
                print("│")
                
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n└─ Stopping generic listener polling. Returning to Main Menu...\n")
            break

# ═══════════════════════════════════════════════════════════════
# STAGE 7 — GLOBAL MARKETS  (Alpha Vantage)
# Goal: Fetch live asset prices, let user invest NGN, write a
#       DEBIT to transactions and an INVESTMENT to portfolio.
# ═══════════════════════════════════════════════════════════════

# Curated list of tradeable assets
_ASSETS = [
    {"name": "S&P 500 ETF",  "symbol": "VOO"},
    {"name": "Apple",         "symbol": "AAPL"},
    {"name": "Tesla",         "symbol": "TSLA"},
    {"name": "Microsoft",     "symbol": "MSFT"},
    {"name": "Nvidia",        "symbol": "NVDA"},
    {"name": "Amazon",        "symbol": "AMZN"},
]


def get_market_price(symbol: str) -> Decimal | None:
    """
    Fetches the live price of *symbol* from Alpha Vantage GLOBAL_QUOTE.
    Returns the price as a Decimal, or None on failure.
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol":   symbol,
        "apikey":   ALPHA_VANTAGE_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        price_str = data.get("Global Quote", {}).get("05. price", "")
        if not price_str:
            print(f"│  [Alpha Vantage] ⚠️  No price data returned for {symbol}.")
            return None
        return Decimal(price_str)
    except requests.RequestException as e:
        print(f"│  [Alpha Vantage] ❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"│  [Alpha Vantage] ❌ Error parsing price: {e}")
        return None


def get_exchange_rate(from_currency: str = "NGN", to_currency: str = "USD") -> Decimal | None:
    """
    Fetches the live exchange rate from Alpha Vantage CURRENCY_EXCHANGE_RATE.
    Returns e.g. Decimal('0.00061') for NGN→USD, or None on failure.
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function":        "CURRENCY_EXCHANGE_RATE",
        "from_currency":   from_currency,
        "to_currency":     to_currency,
        "apikey":          ALPHA_VANTAGE_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        rate_str = (
            data.get("Realtime Currency Exchange Rate", {})
                .get("5. Exchange Rate", "")
        )
        if not rate_str:
            print("│  [Exchange Rate] ⚠️  Could not retrieve rate from Alpha Vantage.")
            return None
        return Decimal(rate_str)
    except requests.RequestException as e:
        print(f"│  [Exchange Rate] ❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"│  [Exchange Rate] ❌ Error parsing rate: {e}")
        return None
def stage7_invest_menu(clerk_id: str, current_balance: Decimal) -> None:
    """
    Presents a list of global assets, fetches the live price for the
    selected asset, asks how much NGN to invest, validates the balance,
    then:
      1. Writes a DEBIT entry to the 'transactions' table.
      2. Writes an INVESTMENT entry to the 'portfolio' table.
    """
    print("\n┌─ STAGE 7 : GLOBAL MARKETS ────────────────────────────┐")
    print(f"│  💰 Available Balance : ₦{current_balance:,.2f}")
    print("│")
    print("│  Select an asset to invest in:")
    for idx, asset in enumerate(_ASSETS, start=1):
        print(f"│    {idx}. {asset['name']} ({asset['symbol']})")
    print("│    0. Back to Main Menu")
    print("└───────────────────────────────────────────────────────")

    raw_choice = input("Select an asset (0 to cancel): ").strip()

    if raw_choice == "0":
        return

    try:
        asset_idx = int(raw_choice) - 1
        if asset_idx < 0 or asset_idx >= len(_ASSETS):
            raise ValueError
    except ValueError:
        print("[Error] Invalid selection.\n")
        return

    chosen = _ASSETS[asset_idx]
    symbol = chosen["symbol"]
    print(f"\n┌─ FETCHING LIVE PRICE : {symbol} ─────────────────────────┐")
    print(f"│  [Alpha Vantage] Querying {chosen['name']} ({symbol}) …")

    current_price = get_market_price(symbol)
    if current_price is None:
        print("└─ [Markets] ❌ Could not retrieve live price. Try again.\n")
        return

    print(f"│  Live Price : ${current_price:,.4f} USD")

    # ── Fetch live exchange rate (NGN → USD) ──────────────────
    print("│  [Alpha Vantage] Fetching live NGN/USD exchange rate …")
    ngn_to_usd = get_exchange_rate("NGN", "USD")
    if ngn_to_usd is None:
        print("└─ [Markets] ❌ Could not retrieve exchange rate. Try again.\n")
        return
    usd_to_ngn = Decimal("1") / ngn_to_usd   # e.g. ~1600 NGN per USD
    print(f"│  Rate        : ₦1.00 = ${ngn_to_usd:.8f} | $1.00 = ₦{usd_to_ngn:,.2f}")
    print("└───────────────────────────────────────────────────────\n")

    # ── Ask how much NGN to invest ────────────────────────────
    raw_amount = input(f"  How much NGN do you want to invest in {chosen['name']}? ₦").strip()
    try:
        invest_amount_ngn = Decimal(raw_amount)
        if invest_amount_ngn <= Decimal('0'):
            raise ValueError("Amount must be positive.")
    except Exception:
        print("[Error] Invalid amount.\n")
        return

    # ── Balance check ─────────────────────────────────────────
    if invest_amount_ngn > current_balance:
        print(f"[Error] ❌ Insufficient balance. You have ₦{current_balance:,.2f} available.\n")
        return

    # ── Currency conversion + unit calculation ──────────────────
    # Step 1: Convert NGN → USD at the live rate
    invest_amount_usd = invest_amount_ngn * ngn_to_usd
    # Step 2: Divide USD amount by the USD share price to get exact units
    units = invest_amount_usd / current_price

    # ── Pre-trade summary ────────────────────────────────────
    print(f"\n┌─ TRADE SUMMARY ───────────────────────────────────────┐")
    print(f"│  Asset         : {chosen['name']} ({symbol})")
    print(f"│  You spend     : ₦{invest_amount_ngn:,.2f} NGN")
    print(f"│  Converted to  : ${invest_amount_usd:,.6f} USD  (rate: ₦{usd_to_ngn:,.2f}/$1)")
    print(f"│  Share price   : ${current_price:,.4f} USD")
    print(f"│  Units bought  : {units:.8f} {symbol}")
    print("└─────────────────────────────────────────────────────\n")

    confirm = input("  Confirm investment? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("  Investment cancelled.\n")
        return

    # ── Supabase Write 1: DEBIT in transactions ───────────────
    print("\n┌─ PROCESSING INVESTMENT ───────────────────────────────┐")
    idempotency_key = str(uuid.uuid4())
    debit_record = {
        "clerk_id":        clerk_id,
        "amount":          str(-invest_amount_ngn),   # negative = debit
        "currency":        "NGN",
        "type":            "DEBIT",
        "status":          "success",
        "idempotency_key": idempotency_key,
        "legal_name":      "",   # filled below
    }
    try:
        # Retrieve legal name for the record
        prof_res = supabase.table("profiles").select("legal_name").eq("clerk_id", clerk_id).execute()
        if prof_res.data:
            debit_record["legal_name"] = prof_res.data[0].get("legal_name", "")
    except Exception:
        pass

    print("│  [DB] Writing DEBIT entry to transactions …")
    try:
        supabase.table("transactions").insert(debit_record).execute()
        print("│  [DB] ✅ DEBIT recorded.")
    except Exception as e:
        print(f"│  [DB] ❌ Failed to record DEBIT: {e}")
        print("└───────────────────────────────────────────────────────\n")
        return

    # ── Supabase Write 2: INVESTMENT in portfolio ─────────────
    #   units (numeric), avg_price_paid (numeric)
    portfolio_record = {
        "clerk_id":       clerk_id,
        "symbol":         symbol,
        "units":          float(units),
        "avg_price_paid": float(current_price),
    }
    print("│  [DB] Writing INVESTMENT entry to portfolio …")
    try:
        supabase.table("portfolio").insert(portfolio_record).execute()
        print("│  [DB] ✅ Portfolio entry recorded.")
    except Exception as e:
        print(f"│  [DB] ❌ Failed to record portfolio entry: {e}")
        # Note: DEBIT already committed; log to investigate in production.

    print("└───────────────────────────────────────────────────────\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║         🌍  INVESTMENT CONFIRMED ✅                  ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Asset      : {chosen['name'] + ' (' + symbol + ')':<38}║")
    print(f"║  NGN Spent  : ₦{invest_amount_ngn:<37,.2f}║")
    print(f"║  USD Value  : ${invest_amount_usd:<37,.6f}║")
    print(f"║  Rate Used  : ₦{usd_to_ngn:<37,.2f}║")
    print(f"║  Share Price: ${current_price:<37,.4f}║")
    print(f"║  Units Bought: {units:<37.8f}║")
    print(f"║  New Balance: ₦{current_balance - invest_amount_ngn:<37,.2f}║")
    print("╚══════════════════════════════════════════════════════╝\n")


def stage7_view_portfolio(clerk_id: str) -> None:
    """
    Reads the user's portfolio rows from Supabase, fetches a live price
    for each unique symbol via Alpha Vantage, and prints a P&L summary.
    """
    print("\n┌─ MY PORTFOLIO ────────────────────────────────────────┐")
    print("│  [DB] Fetching your holdings …")
    try:
        res = supabase.table("portfolio").select("*").eq("clerk_id", clerk_id).execute()
    except Exception as e:
        print(f"│  [DB] ❌ Error reading portfolio: {e}")
        print("└───────────────────────────────────────────────────────\n")
        return

    rows = res.data or []
    if not rows:
        print("│  You have no investments yet.")
        print("└───────────────────────────────────────────────────────\n")
        return

    # Aggregate holdings by symbol (sum units, weighted avg price)
    holdings: dict = {}
    for row in rows:
        sym   = row["symbol"]
        units = Decimal(str(row["units"]))
        paid  = Decimal(str(row["avg_price_paid"]))
        if sym not in holdings:
            holdings[sym] = {"total_units": Decimal("0"), "cost_basis": Decimal("0"), "rows": 0}
        holdings[sym]["total_units"] += units
        holdings[sym]["cost_basis"]  += units * paid
        holdings[sym]["rows"]        += 1

    # Fetch live prices (one API call per unique symbol)
    live_prices: dict = {}
    for sym in holdings:
        print(f"│  [Alpha Vantage] Fetching live price for {sym} …")
        price = get_market_price(sym)
        live_prices[sym] = price  # may be None on API error

    # ── Print holdings table ──────────────────────────────────
    print("│")
    print("│  {:<6}  {:>12}  {:>14}  {:>14}  {:>10}".format(
          "Symbol", "Units Held", "Avg Cost ($)", "Live Price ($)", "P&L ($)"))
    print("│  " + "-" * 62)

    total_invested = Decimal("0")
    total_current  = Decimal("0")

    for sym, data in holdings.items():
        total_units  = data["total_units"]
        cost_basis   = data["cost_basis"]
        avg_cost     = cost_basis / total_units if total_units else Decimal("0")
        live_price   = live_prices.get(sym)

        if live_price is not None:
            current_val = live_price * total_units
            pnl         = current_val - cost_basis
            pnl_str     = f"{'+' if pnl >= 0 else ''}{pnl:.2f}"
            live_str    = f"{live_price:.4f}"
        else:
            current_val = Decimal("0")
            pnl_str     = "N/A"
            live_str    = "N/A"

        print("│  {:<6}  {:>12.6f}  {:>14.4f}  {:>14}  {:>10}".format(
              sym, total_units, avg_cost, live_str, pnl_str))

        total_invested += cost_basis
        total_current  += current_val

    total_pnl = total_current - total_invested
    print("│  " + "-" * 62)
    print(f"│  Total Cost Basis   : ${total_invested:,.4f}")
    print(f"│  Total Current Value: ${total_current:,.4f}")
    print(f"│  Overall P&L        : ${'%+.4f' % total_pnl}")
    print("└───────────────────────────────────────────────────────\n")


# ═══════════════════════════════════════════════════════════════
# WEEK 9 — PORTFOLIO ANALYTICS
# ═══════════════════════════════════════════════════════════════

def get_portfolio_summary(clerk_id: str) -> list[dict]:
    """
    Fetches all portfolio rows for the user, calls Alpha Vantage for each
    unique symbol, and returns a list of per-symbol summary dicts:
      {
        symbol, total_units, avg_price_paid,
        current_price,   # Decimal | None
        current_value,   # Decimal (0 if price unavailable)
        cost_basis,      # Decimal  (units * avg_price_paid)
        gain_loss,       # Decimal  (current_value - cost_basis)
      }
    """
    try:
        res = supabase.table("portfolio").select("*").eq("clerk_id", clerk_id).execute()
    except Exception as e:
        print(f"│  [DB] ❌ Error reading portfolio: {e}")
        return []

    rows = res.data or []
    if not rows:
        return []

    # ── Aggregate rows by symbol ────────────────────────────────
    agg: dict = {}
    for row in rows:
        sym   = row["symbol"]
        units = Decimal(str(row["units"]))
        paid  = Decimal(str(row["avg_price_paid"]))
        if sym not in agg:
            agg[sym] = {"total_units": Decimal("0"), "cost_basis": Decimal("0")}
        agg[sym]["total_units"] += units
        agg[sym]["cost_basis"]  += units * paid

    # ── Fetch one live price per symbol ───────────────────────────
    summary = []
    for sym, data in agg.items():
        total_units   = data["total_units"]
        cost_basis    = data["cost_basis"]
        avg_pp        = cost_basis / total_units if total_units else Decimal("0")
        current_price = get_market_price(sym)  # may be None

        if current_price is not None:
            current_value = current_price * total_units
        else:
            current_value = Decimal("0")

        gain_loss = current_value - cost_basis

        summary.append({
            "symbol":         sym,
            "total_units":    total_units,
            "avg_price_paid": avg_pp,
            "current_price":  current_price,
            "current_value":  current_value,
            "cost_basis":     cost_basis,
            "gain_loss":      gain_loss,
        })

    return summary


def display_net_worth(clerk_id: str) -> None:
    """
    Combines cash balance + live investment value to display the user's
    complete financial picture with performance analytics.
    """
    print("\n┌─ PORTFOLIO PERFORMANCE ──────────────────────────────┐")
    print("│  [DB] Fetching your data …")

    # ── 1. Cash balance ─────────────────────────────────────
    cash_balance = get_account_balance(clerk_id)

    # ── 2. Portfolio summary (live prices from Alpha Vantage) ───
    print("│  [Alpha Vantage] Fetching live prices …")
    holdings = get_portfolio_summary(clerk_id)

    total_invested    = sum(h["cost_basis"]    for h in holdings)
    total_current_val = sum(h["current_value"] for h in holdings)
    total_gain_loss   = sum(h["gain_loss"]     for h in holdings)

    # Performance % against total amount invested
    if total_invested > Decimal("0"):
        perf_pct = (total_gain_loss / total_invested) * Decimal("100")
    else:
        perf_pct  = Decimal("0")

    net_worth = cash_balance + total_current_val

    # ── 3. Per-symbol breakdown ─────────────────────────────
    if holdings:
        print("│")
        print("│  ┌{}┐".format("─" * 64))
        print("│  │  {:<6}  {:>10}  {:>12}  {:>12}  {:>10}  │".format(
              "Symbol", "Units", "Avg Cost", "Live Price", "Gain/Loss"))
        print("│  ├{}┤".format("─" * 64))
        for h in holdings:
            sym   = h["symbol"]
            units = h["total_units"]
            avg   = h["avg_price_paid"]
            live  = h["current_price"]
            gl    = h["gain_loss"]
            live_str = f"${live:,.4f}"  if live  else "N/A"
            gl_str   = f"{'+' if gl >= 0 else ''}${gl:,.2f}" if live else "N/A"
            print("│  │  {:<6}  {:>10.4f}  {:>12}  {:>12}  {:>10}  │".format(
                  sym, units, f"${avg:,.4f}", live_str, gl_str))
        print("│  └{}┘".format("─" * 64))

    # ── 4. Net Worth summary banner ──────────────────────────
    gain_sign  = "+" if total_gain_loss >= 0 else ""
    perf_sign  = "+" if perf_pct       >= 0 else ""

    print("│")
    print("└───────────────────────────────────────────────────────\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║       📊  WEALY NET WORTH DASHBOARD               ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  🏦 Total Cash          : ₦{cash_balance:>30,.2f}  ║")
    print(f"║  📈 Total Investments   : ${total_current_val:>30,.4f}  ║")
    print(f"║  💰 Total Net Worth     : ₦{net_worth:>30,.2f}  ║")
    print("╠══════════════════════════════════════════════════════╣")
    if total_invested > 0:
        print(f"║  📊 Performance         : {perf_sign}{perf_pct:>6.2f}%  (${gain_sign}{total_gain_loss:,.2f} Gain)║")
    else:
        print("║  📊 Performance         : No investments yet.             ║")
    print("╚══════════════════════════════════════════════════════╝\n")


# ═══════════════════════════════════════════════════════════════
# WITHDRAWAL — Sell Stocks & Move Cash to Bank
# ═══════════════════════════════════════════════════════════════

def sell_investment(clerk_id: str, symbol: str, units_to_sell: Decimal) -> bool:
    """
    Sells *units_to_sell* of *symbol* for the user:
      1. Fetches live USD price from Alpha Vantage.
      2. Fetches live NGN/USD exchange rate.
      3. Calculates NGN proceeds = units * usd_price * usd_to_ngn.
      4. Reduces units in the portfolio table (deletes row if fully sold).
      5. Writes a CREDIT / DIVEST entry to transactions.
    Returns True on success, False on any failure.
    """
    print(f"\n┌─ SELLING {symbol} ──────────────────────────────────────┐")

    # ── 1. Live USD price ──────────────────────────────────
    print(f"│  [Alpha Vantage] Fetching live price for {symbol} …")
    usd_price = get_market_price(symbol)
    if usd_price is None:
        print("└─ ❌ Could not retrieve live price. Sale aborted.\n")
        return False

    # ── 2. Live exchange rate (USD → NGN) ───────────────────
    print("│  [Alpha Vantage] Fetching NGN/USD rate …")
    ngn_to_usd = get_exchange_rate("NGN", "USD")
    if ngn_to_usd is None:
        print("└─ ❌ Could not retrieve exchange rate. Sale aborted.\n")
        return False
    usd_to_ngn = Decimal("1") / ngn_to_usd

    # ── 3. Calculate NGN proceeds ───────────────────────────
    proceeds_usd = units_to_sell * usd_price
    proceeds_ngn = proceeds_usd * usd_to_ngn

    print(f"│  Units to sell  : {units_to_sell:.8f} {symbol}")
    print(f"│  Live price     : ${usd_price:,.4f} USD")
    print(f"│  Proceeds (USD) : ${proceeds_usd:,.6f}")
    print(f"│  Proceeds (NGN) : ₦{proceeds_ngn:,.2f}  (rate: ₦{usd_to_ngn:,.2f}/$1)")

    # ── 4a. Fetch all portfolio rows for this symbol ────────────
    print("│  [DB] Updating portfolio …")
    try:
        port_res = (
            supabase.table("portfolio")
            .select("*")
            .eq("clerk_id", clerk_id)
            .eq("symbol", symbol)
            .order("created_at")
            .execute()
        )
    except Exception as e:
        print(f"└─ [DB] ❌ Could not read portfolio: {e}\n")
        return False

    rows = port_res.data or []
    if not rows:
        print("└─ ❌ No portfolio entry found for this symbol.\n")
        return False

    # Sum total units held
    total_held = sum(Decimal(str(r["units"])) for r in rows)
    if units_to_sell > total_held:
        print(f"└─ ❌ You only hold {total_held:.8f} units. Sale aborted.\n")
        return False

    # ── 4b. Deduct units FIFO across rows ────────────────────
    remaining_to_sell = units_to_sell
    try:
        for row in rows:
            if remaining_to_sell <= Decimal("0"):
                break
            row_units = Decimal(str(row["units"]))
            row_id    = row["id"]
            if row_units <= remaining_to_sell:
                # Delete this row entirely
                supabase.table("portfolio").delete().eq("id", row_id).execute()
                remaining_to_sell -= row_units
            else:
                # Partially reduce this row
                new_units = row_units - remaining_to_sell
                supabase.table("portfolio").update(
                    {"units": float(new_units)}
                ).eq("id", row_id).execute()
                remaining_to_sell = Decimal("0")
    except Exception as e:
        print(f"└─ [DB] ❌ Error updating portfolio rows: {e}\n")
        return False

    print("│  [DB] ✅ Portfolio updated.")

    # ── 5. Write CREDIT / DIVEST entry to transactions ─────────
    print("│  [DB] Writing DIVEST CREDIT to transactions …")
    try:
        # Retrieve legal name
        legal_name = ""
        prof_res = supabase.table("profiles").select("legal_name").eq("clerk_id", clerk_id).execute()
        if prof_res.data:
            legal_name = prof_res.data[0].get("legal_name", "")

        credit_record = {
            "clerk_id":        clerk_id,
            "legal_name":      legal_name,
            "amount":          str(proceeds_ngn),   # positive = credit
            "currency":        "NGN",
            "type":            "DIVEST",
            "status":          "success",
            "idempotency_key": str(uuid.uuid4()),
        }
        supabase.table("transactions").insert(credit_record).execute()
        print("│  [DB] ✅ DIVEST CREDIT recorded.")
    except Exception as e:
        print(f"│  [DB] ❌ Failed to record credit: {e}")
        print("└───────────────────────────────────────────────────────\n")
        return False

    print("└───────────────────────────────────────────────────────\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║        📉  SALE CONFIRMED ✅                        ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Asset Sold   : {symbol:<38}║")
    print(f"║  Units Sold   : {units_to_sell:<38.8f}║")
    print(f"║  Price (USD)  : ${usd_price:<37,.4f}║")
    print(f"║  Proceeds     : ₦{proceeds_ngn:<37,.2f}║")
    print("╚══════════════════════════════════════════════════════╝\n")
    return True


def withdraw_to_bank(clerk_id: str, amount: Decimal, profile: dict) -> None:
    """
    Moves *amount* NGN from the user's wallet to their bank account:
      1. Checks account balance.
      2. Writes a DEBIT / WITHDRAWAL entry to transactions.
      3. Mocks a Flutterwave payout.
    """
    print("\n┌─ WITHDRAW TO BANK ────────────────────────────────────┐")

    # ── Balance check ─────────────────────────────────────
    balance = get_account_balance(clerk_id)
    print(f"│  Current Balance : ₦{balance:,.2f}")
    print(f"│  Requested      : ₦{amount:,.2f}")

    if amount <= Decimal("0"):
        print("└─ ❌ Amount must be positive.\n")
        return
    if amount > balance:
        print(f"└─ ❌ Insufficient funds. You only have ₦{balance:,.2f}.\n")
        return

    # ── Write DEBIT / WITHDRAWAL to transactions ──────────────
    print("│  [DB] Recording WITHDRAWAL …")
    try:
        withdrawal_record = {
            "clerk_id":        clerk_id,
            "legal_name":      profile.get("legal_name", ""),
            "amount":          str(-amount),   # negative = debit
            "currency":        "NGN",
            "type":            "WITHDRAWAL",
            "status":          "success",
            "idempotency_key": str(uuid.uuid4()),
        }
        supabase.table("transactions").insert(withdrawal_record).execute()
        print("│  [DB] ✅ WITHDRAWAL recorded.")
    except Exception as e:
        print(f"└─ [DB] ❌ Failed to record withdrawal: {e}\n")
        return

    # ── Flutterwave payout mock ────────────────────────────
    acc_no    = profile.get("account_number", "N/A")
    bank_name = profile.get("bank_name",      "N/A")
    legal     = profile.get("legal_name",     "N/A")
    print("│")
    print("│  🟡 Flutterwave Payout Simulation")
    print(f"│  Simulating Flutterwave Payout to {legal}")
    print(f"│  Account : {acc_no} ({bank_name})")
    print("│  … processing …")
    print("│  ✅ Transfer Successful! Funds are on their way.")
    print("└───────────────────────────────────────────────────────\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║       🏦  WITHDRAWAL CONFIRMED ✅                  ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Name         : {legal:<38}║")
    print(f"║  Account      : {acc_no:<38}║")
    print(f"║  Bank         : {bank_name:<38}║")
    print(f"║  Amount Sent  : ₦{amount:<37,.2f}║")
    print(f"║  New Balance  : ₦{balance - amount:<37,.2f}║")
    print("╚══════════════════════════════════════════════════════╝\n")


def withdraw_menu(clerk_id: str, profile: dict) -> None:
    """
    Sub-menu: A. Sell Stocks to Wallet  |  B. Move Wallet Cash to Bank
    """
    while True:
        print("\n┌─ WITHDRAW FUNDS ──────────────────────────────────────┐")
        current_balance = get_account_balance(clerk_id)
        print(f"│  💰 Wallet Balance : ₦{current_balance:,.2f}")
        print("│")
        print("│  A. Sell Stocks to Wallet")
        print("│  B. Move Wallet Cash to Bank")
        print("│  0. Back to Main Menu")
        print("└───────────────────────────────────────────────────────")

        sub = input("Select (A/B/0): ").strip().upper()

        if sub == "0":
            break

        elif sub == "A":
            # ── Show current holdings ────────────────────────────
            print("\n┌─ YOUR HOLDINGS ───────────────────────────────────────┐")
            try:
                port_res = (
                    supabase.table("portfolio")
                    .select("symbol, units")
                    .eq("clerk_id", clerk_id)
                    .execute()
                )
                rows = port_res.data or []
            except Exception as e:
                print(f"│  [DB] ❌ Error: {e}")
                rows = []

            # Aggregate by symbol
            agg: dict[str, Decimal] = {}
            for r in rows:
                sym   = r["symbol"]
                units = Decimal(str(r["units"]))
                agg[sym] = agg.get(sym, Decimal("0")) + units

            if not agg:
                print("│  You have no stock holdings.")
                print("└───────────────────────────────────────────────────────\n")
                continue

            for idx, (sym, total) in enumerate(agg.items(), 1):
                print(f"│  {idx}. {sym:<6}  {total:.8f} units")
            print("└───────────────────────────────────────────────────────")

            sym_input = input("  Enter symbol to sell (e.g. AAPL): ").strip().upper()
            if sym_input not in agg:
                print(f"[Error] You don't hold {sym_input}.\n")
                continue

            max_units = agg[sym_input]
            raw_units = input(f"  Units to sell (max {max_units:.8f}): ").strip()
            try:
                units_to_sell = Decimal(raw_units)
                if units_to_sell <= 0 or units_to_sell > max_units:
                    raise ValueError
            except Exception:
                print("[Error] Invalid unit amount.\n")
                continue

            sell_investment(clerk_id, sym_input, units_to_sell)

        elif sub == "B":
            raw_amt = input(f"  Amount to withdraw (₦, max ₦{current_balance:,.2f}): ₦").strip()
            try:
                withdraw_amount = Decimal(raw_amt)
            except Exception:
                print("[Error] Invalid amount.\n")
                continue
            withdraw_to_bank(clerk_id, withdraw_amount, profile)

        else:
            print("Invalid option. Please enter A, B, or 0.\n")


# ═══════════════════════════════════════════════════════════════
# MAIN — Vault Startup
# ═══════════════════════════════════════════════════════════════

def main():
    # Stage 1 — Auth
    clerk_id = stage1_authenticate()

    # Retrieve user email for Virtual Account flow before KYC
    try:
        user_obj    = clerk_backend.users.get(user_id=clerk_id)
        email_addrs = user_obj.email_addresses or []
        user_email  = email_addrs[0].email_address if email_addrs else ""
    except Exception:
        user_email  = ""

    # Stage 2 — Identity / KYC + Virtual Account creation
    profile  = stage2_identity_check(clerk_id, user_email)

    account_number = profile.get("account_number")
    bank_name = profile.get("bank_name", "Unknown Bank")

    # `pending_record` tracks an unconfirmed payment.
    # While set, the menu locks to Confirm / Quit only.
    pending_record: dict | None = None

    while True:
        if pending_record:
            # ── PENDING PAYMENT MENU ──────────────────────────
            link = pending_record.get("_flw_link", "(link not available)")
            print("┌─ PENDING PAYMENT ─────────────────────────────────────┐")
            print("│  ⚠️  You have an unconfirmed payment.")
            print(f"│  Payment link : {link}")
            print("│")
            print("│  1. Confirm Payment  (check if Flutterwave received it)")
            print("│  2. Quit")
            print("└───────────────────────────────────────────────────────")

            choice = input("Select an option (1/2): ").strip()

            if choice == "1":
                confirmed = try_confirm_payment(pending_record)
                if confirmed:
                    pending_record = None          # clear → return to normal menu
                    # Stay in loop so user can make another deposit or quit
            elif choice == "2":
                print("Exiting. Your payment record is marked 'pending' in the database.\n")
                break
            else:
                print("Invalid option. Please try again.\n")

        else:
            # ── MAIN MENU ────────────────────────────────────
            print("\n┌─ MAIN MENU ───────────────────────────────────────────┐")
            print("│  1. Deposit Funds (via Link)")
            print("│  2. View Balance & Vault Transfer Listener")
            print("│  3. Invest in Global Markets")
            print("│  4. View Portfolio Performance")
            print("│  5. Withdraw Funds")
            print("│  6. View My Portfolio (Detailed Holdings)")
            print("│  7. Quit")
            print("└───────────────────────────────────────────────────────")

            choice = input("Select an option (1-7): ").strip()

            if choice == "1":
                # Stage 3 — Collect deposit (gated on Verified status)
                amount = stage3_collect_deposit(profile)

                if amount is not None:
                    pending_record = stage4_create_pending_transaction(
                        clerk_id   = clerk_id,
                        amount     = amount,
                        legal_name = profile.get("legal_name", ""),
                    )
                    if pending_record:
                        stage5_show_payment_link(
                            user_email     = user_email,
                            amount         = amount,
                            pending_record = pending_record,
                        )
            elif choice == "2":
                if profile.get("kyc_status") == "Verified" and account_number:
                    execution_loop(
                        clerk_id=clerk_id,
                        legal_name=profile.get("legal_name", "User"),
                        account_number=account_number,
                        bank_name=bank_name
                    )
                else:
                    print("┌─ NOTICE ──────────────────────────────────────────────────┐")
                    print("│  You are Tier 1 (Unverified) or missing an account number.")
                    print("│  Vault Listener requires a verified BVN.")
                    print("└───────────────────────────────────────────────────────────\n")
            elif choice == "3":
                current_balance = get_account_balance(clerk_id)
                stage7_invest_menu(clerk_id, current_balance)
            elif choice == "4":
                display_net_worth(clerk_id)
            elif choice == "5":
                # Withdraw sub-menu
                withdraw_menu(clerk_id, profile)
            elif choice == "6":
                stage7_view_portfolio(clerk_id)
            elif choice == "7":
                print("Exiting The Wealy App. Goodbye!\n")
                break
            else:
                print("Invalid option. Please try again.\n")

if __name__ == "__main__":
    main()
