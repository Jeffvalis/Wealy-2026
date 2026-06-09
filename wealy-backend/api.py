import os
import uuid
import asyncio
from decimal import Decimal
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Import logic and clients from the existing main.py
from main import (
    clerk_backend, supabase,
    _paystack_verify_bvn, create_virtual_account,
    initialize_payment, verify_payment, get_account_balance,
    get_market_price, get_exchange_rate,
    _ASSETS, FLW_BASE_URL, FLW_HEADERS
)
from clerk_backend_api.models import GetUserListRequest, SDKError

app = FastAPI(title="The Wealy App API", version="1.0.0")

# CORS for React frontend (Vite default port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class KYCRequest(BaseModel):
    clerk_id: str
    email: str
    bvn: str

class DepositRequest(BaseModel):
    clerk_id: str
    amount: float

class WithdrawRequest(BaseModel):
    clerk_id: str
    amount: float
    bank_code: str
    account_number: str

class InvestRequest(BaseModel):
    clerk_id: str
    symbol: str
    amount_ngn: float

class SellRequest(BaseModel):
    clerk_id: str
    symbol: str
    units: float

# ─── Auth & Profile ──────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    try:
        users = clerk_backend.users.list(request=GetUserListRequest(email_address=[req.email]))
        if not users:
            raise HTTPException(status_code=404, detail="No account found for that email.")
            
        user = users[0]
        verification = clerk_backend.users.verify_password(user_id=user.id, password=req.password)
        if not verification.verified:
            raise HTTPException(status_code=401, detail="Incorrect password.")
            
        # Fetch profile
        prof_res = supabase.table("profiles").select("*").eq("clerk_id", user.id).execute()
        profile = prof_res.data[0] if prof_res.data else None
        
        return {
            "clerk_id": user.id,
            "email": req.email,
            "profile": profile
        }
    except SDKError as e:
        # Clerk throws a 422 error when the password is mathematically incorrect
        err_msg = str(e)
        if "incorrect_password" in err_msg or "422" in err_msg:
            raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
        raise HTTPException(status_code=500, detail="Authentication service error. Please contact support.")

@app.get("/api/profile/{clerk_id}")
def get_profile(clerk_id: str):
    res = supabase.table("profiles").select("*").eq("clerk_id", clerk_id).execute()
    if not res.data:
        return {"status": "Unverified", "profile": None}
    
    profile = res.data[0]
    balance = get_account_balance(clerk_id)
    return {
        "profile": profile,
        "wallet_balance": float(balance)
    }

# ─── KYC & Virtual Accounts ──────────────────────────────────────────────────

@app.post("/api/kyc")
def process_kyc(req: KYCRequest):
    bvn = req.bvn
    if len(bvn) != 11 or not bvn.isdigit():
        raise HTTPException(400, "BVN must be 11 digits.")
        
    kyc_response = _paystack_verify_bvn(bvn)
    if not kyc_response.get("status"):
        raise HTTPException(400, kyc_response.get("message", "Paystack CVV verification failed."))
        
    kyc_data = kyc_response.get("data", {})
    legal_name = f"{kyc_data.get('first_name', '')} {kyc_data.get('last_name', '')}".strip()
    
    # Generate virtual account
    acc_details = create_virtual_account(req.email, bvn, legal_name, req.clerk_id)
    
    payload = {
        "clerk_id": req.clerk_id,
        "legal_name": legal_name,
        "kyc_status": "Verified",
        "account_number": acc_details["account_number"] if acc_details else None,
        "bank_name": acc_details["bank_name"] if acc_details else None,
    }
    
    supabase.table("profiles").upsert(payload).execute()
    return {"message": "Identity Verified", "profile": payload}

# ─── Wallet Operations ───────────────────────────────────────────────────────

@app.post("/api/wallet/deposit")
def initiate_deposit(req: DepositRequest):
    # Get profile — KYC must be verified
    res = supabase.table("profiles").select("*").eq("clerk_id", req.clerk_id).execute()
    if not res.data or res.data[0].get("kyc_status") != "Verified":
        raise HTTPException(403, "Identity verification required for deposits.")
        
    profile = res.data[0]
    amount = Decimal(str(req.amount))
    legal_name = profile.get("legal_name", "")
    email = profile.get("email", f"{req.clerk_id}@wealy.app")

    idempotency_key = str(uuid.uuid4())
    tx_record = {
        "clerk_id": req.clerk_id,
        "legal_name": legal_name,
        "amount": str(amount),
        "currency": "NGN",
        "type": "DEPOSIT",
        "status": "pending",
        "idempotency_key": idempotency_key,
    }
    db_res = supabase.table("transactions").insert(tx_record).execute()
    db_id = db_res.data[0]['id'] if db_res.data else None

    flw_res = initialize_payment(email, amount, idempotency_key)
    if not flw_res:
        raise HTTPException(500, "Failed to initialize Flutterwave payment.")
        
    return {
        "payment_link": flw_res["data"]["link"],
        "tx_ref": idempotency_key,
        "db_id": db_id
    }

class VerifyRequest(BaseModel):
    clerk_id: str
    tx_ref: str  # The idempotency_key / tx_ref string

@app.post("/api/wallet/verify")
def verify_pending_deposit(req: VerifyRequest):
    """
    Manually verify a pending deposit by its tx_ref.
    Searches Flutterwave for the matching transaction, confirms it,
    and marks the Supabase record as 'success'.
    """
    import requests as _req
    
    # 1. Find the transaction in our DB by idempotency_key
    db_res = (
        supabase.table("transactions")
        .select("*")
        .eq("clerk_id", req.clerk_id)
        .eq("idempotency_key", req.tx_ref)
        .execute()
    )
    if not db_res.data:
        raise HTTPException(404, "Transaction not found. Check the reference code.")
    
    tx = db_res.data[0]
    if tx.get("status", "").lower() == "success":
        return {"message": "Transaction already verified.", "status": "success"}

    # 2. Search Flutterwave for the tx by tx_ref
    try:
        search = _req.get(
            f"{FLW_BASE_URL}/transactions",
            params={"tx_ref": req.tx_ref},
            headers=FLW_HEADERS,
            timeout=20,
        )
        search_data = search.json()
    except Exception as e:
        raise HTTPException(502, f"Could not reach Flutterwave: {e}")

    raw = search_data.get("data", [])
    tx_list = raw if isinstance(raw, list) else raw.get("transactions", [])
    
    if not tx_list:
        raise HTTPException(404, "Payment not found on Flutterwave. Please complete payment first.")
    
    flw_tx_id = str(tx_list[0].get("id", ""))
    
    # 3. Verify the specific transaction
    try:
        verify_resp = _req.get(
            f"{FLW_BASE_URL}/transactions/{flw_tx_id}/verify",
            headers=FLW_HEADERS,
            timeout=20,
        )
        verify_data = verify_resp.json()
    except Exception as e:
        raise HTTPException(502, f"Verification call failed: {e}")
    
    flw_status = verify_data.get("data", {}).get("status", "")
    
    if flw_status == "successful":
        # 4. Mark transaction as success in Supabase
        supabase.table("transactions").update({"status": "success"}).eq("id", tx["id"]).execute()
        return {
            "message": "✅ Payment verified and balance updated!",
            "status": "success",
            "amount": tx.get("amount")
        }
    else:
        raise HTTPException(402, f"Payment not yet confirmed by Flutterwave (status: {flw_status}). Please allow a few minutes and try again.")

@app.post("/api/webhook/flutterwave")
async def flutterwave_webhook(payload: dict):
    """
    Flutterwave calls this URL automatically when a payment is confirmed.
    Configure this URL in your Flutterwave dashboard under Webhooks.
    URL: http://your-server/api/webhook/flutterwave
    """
    event = payload.get("event", "")
    if event not in ("charge.completed", "transfer.completed"):
        return {"status": "ignored"}
    
    data     = payload.get("data", {})
    tx_ref   = data.get("tx_ref", "")
    status   = data.get("status", "")
    amount   = data.get("amount", 0)
    
    if status != "successful" or not tx_ref:
        return {"status": "not_successful"}
    
    # Find and update the matching pending transaction
    db_res = supabase.table("transactions").select("id,status").eq("idempotency_key", tx_ref).execute()
    if db_res.data:
        tx = db_res.data[0]
        if tx.get("status", "").lower() != "success":
            supabase.table("transactions").update({"status": "success"}).eq("id", tx["id"]).execute()
    
    return {"status": "ok"}


@app.post("/api/wallet/withdraw")
def withdraw(req: WithdrawRequest):
    balance = get_account_balance(req.clerk_id)
    amount = Decimal(str(req.amount))
    
    if amount <= Decimal("0") or amount > balance:
        raise HTTPException(400, "Invalid amount or insufficient funds.")
        
    res = supabase.table("profiles").select("legal_name").eq("clerk_id", req.clerk_id).execute()
    legal_name = res.data[0].get("legal_name", "") if res.data else ""
    
    tx_record = {
        "clerk_id": req.clerk_id,
        "legal_name": legal_name,
        "amount": str(-amount),
        "currency": "NGN",
        "type": "WITHDRAWAL",
        "status": "success",
        "idempotency_key": str(uuid.uuid4()),
    }
    supabase.table("transactions").insert(tx_record).execute()
    
    return {"message": "Withdrawal processed successfully", "amount": req.amount}

# ─── Market & Investments ────────────────────────────────────────────────────

@app.get("/api/market/assets")
def get_assets():
    # In production, we'd map live prices here, but caching is better.
    # We will return the static list, and frontend will fetch prices on demand.
    return _ASSETS

@app.get("/api/market/price/{symbol}")
def get_single_price(symbol: str):
    price = get_market_price(symbol)
    if not price:
        raise HTTPException(404, "Price unavailable")
    return {"symbol": symbol, "price": float(price)}

@app.post("/api/market/buy")
def buy_asset(req: InvestRequest):
    balance = get_account_balance(req.clerk_id)
    invest_amount_ngn = Decimal(str(req.amount_ngn))
    
    if invest_amount_ngn > balance:
        raise HTTPException(400, "Insufficient funds.")
        
    usd_price = get_market_price(req.symbol)
    ngn_to_usd = get_exchange_rate("NGN", "USD")
    
    # Fallback to mock values if Alpha Vantage rate limits us
    if not usd_price:
        usd_price = Decimal("250.00")
    if not ngn_to_usd:
        ngn_to_usd = Decimal("0.00065")
        
    invest_amount_usd = invest_amount_ngn * ngn_to_usd
    units = invest_amount_usd / usd_price
    
    # DB Writes
    tx_record = {
        "clerk_id": req.clerk_id,
        "amount": str(-invest_amount_ngn),
        "currency": "NGN",
        "type": "DEBIT",
        "status": "success",
        "idempotency_key": str(uuid.uuid4()),
    }
    
    port_record = {
        "clerk_id": req.clerk_id,
        "symbol": req.symbol,
        "units": float(units),
        "avg_price_paid": float(usd_price),
    }
    
    supabase.table("transactions").insert(tx_record).execute()
    supabase.table("portfolio").insert(port_record).execute()
    
    return {
        "message": "Investment successful",
        "units": float(units),
        "price": float(usd_price)
    }

@app.get("/api/transactions/{clerk_id}")
def get_transactions(clerk_id: str):
    res = supabase.table("transactions").select("*").eq("clerk_id", clerk_id).order("id", desc=True).execute()
    return {"transactions": res.data if res.data else []}

@app.get("/api/portfolio/{clerk_id}")
def get_full_portfolio(clerk_id: str):
    """
    Returns the user's portfolio: each holding with total units,
    plus overall cash and total net worth.
    """
    # 1. Sum total units per symbol from the portfolio table
    res = supabase.table("portfolio").select("symbol,units,avg_price_paid").eq("clerk_id", clerk_id).execute()
    
    holdings_map = {}  # symbol -> {total_units, total_cost}
    for row in (res.data or []):
        sym = row["symbol"]
        units = float(row.get("units") or 0)
        avg_price = float(row.get("avg_price_paid") or 0)
        if sym not in holdings_map:
            holdings_map[sym] = {"total_units": 0.0, "total_cost": 0.0}
        holdings_map[sym]["total_units"] += units
        holdings_map[sym]["total_cost"] += units * avg_price

    # 2. Build summary with live prices
    summary = []
    for sym, data in holdings_map.items():
        total_units = data["total_units"]
        total_cost = data["total_cost"]
        avg_price_paid = (total_cost / total_units) if total_units > 0 else 0
        current_price = get_market_price(sym)  # may be None if rate-limited
        current_value = float(current_price or avg_price_paid) * total_units
        cost_basis = avg_price_paid * total_units
        gain_loss = current_value - cost_basis
        summary.append({
            "symbol": sym,
            "total_units": total_units,
            "avg_price_paid": avg_price_paid,
            "current_price": float(current_price) if current_price else None,
            "current_value": current_value,
            "cost_basis": cost_basis,
            "gain_loss": gain_loss,
        })

    cash = get_account_balance(clerk_id)
    total_val = sum(item["current_value"] for item in summary)

    return {
        "cash_balance": float(cash),
        "portfolio_value": float(total_val),
        "total_net_worth": float(cash) + float(total_val),
        "holdings": summary
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
