# 📜 The Wealy App - Technical Requirements Document (TRD)

## 1. Executive Summary

**Wealy** is a premium, full-stack wealth management platform designed to automate identity verification, fiat deposits via virtual accounts, and global market investments for retail users in Nigeria (NGN base currency). The system acts as a consolidated orchestrator connecting various API providers into a single streamlined pipeline: Authentication -> KYC Registration -> Wallet Generation -> Real-time Ledger Management -> Asset Purchases.

## 2. Technology Stack & Rationale

Wealy is engineered with an "API-first" modular architecture. The application is segregated into a React frontend and a Python backend to maintain separation of concerns.

### Frontend
- **Framework:** React (bootstrapped with Vite)
- **Styling:** Vanilla CSS (For fine-grained control over animations, glassmorphism, and a tailored premium UI).
- **Rationale:** Vite provides rapid HMR (Hot Module Replacement) and modern build speeds. React enables a component-based architecture which scales perfectly as the platform gains features like advanced portfolio charting.

### Backend
- **Framework:** Python / FastAPI
- **Rationale:** Python handles financial logic, Decimal arithmetic, and heavy API orchestration gracefully. FastAPI provides automatic OpenAPI documentation generation (`/docs`), strong validation natively via Pydantic, and fast async capabilities which are perfect for a heavily I/O bound system (API polling and webhook listening).
- **Execution Layers:** The backend serves traffic via Uvicorn on port `8000`.

### Database
- **Provider:** Supabase (PostgreSQL)
- **Rationale:** Supabase delivers an instantly scalable PostgreSQL instance. It holds critical user records without the need to self-host or maintain complex database infrastructure.

---

## 3. API Integrations & Rationale

Wealy abstracts the complexity of financial compliance and orchestration through the following third-party integrations:

### 1. Clerk (Authentication & Identity)
- **Use Case:** Secure Email, Password, and 2FA authentication.
- **Rationale:** Building auth from scratch opens severe security vectors. Clerk handles password hashing, JWT minting, and brute-force mitigation securely.

### 2. Paystack (KYC & Compliance)
- **Use Case:** BVN (Bank Verification Number) Resolution.
- **Rationale:** Necessary to verify Nigerian identities. Paystack's endpoint checks the user's provided 11-digit BVN and returns the verified `first_name` and `last_name`, converting the user from "Tier 1 (Unverified)" to a "Verified" status. 

### 3. Flutterwave (Payments & Virtual Accounts)
- **Use Case:** Generating permanent NGN virtual accounts, webhooks for inbound transfers, and one-off deposits.
- **Rationale:** We use Flutterwave for creating a persistent bank account for each verified user. This account securely stores their deposits.

### 4. Alpha Vantage (Global Markets Data)
- **Use Case:** Polling real-time equity prices (e.g., AAPL, TSLA, S&P 500) and Currency FX (NGN -> USD).
- **Rationale:** Provides high-fidelity institutional stock data, allowing users to buy fractional investments with their local fiat.

---

## 4. Platform Features & Implementation Details

### 4.1 KYC Gatekeeper
An onboarding compliance engine. Before a user can perform significant money movements, they must submit their BVN. 
- **Tier 1:** Unverified. Extremely limited or zero deposit capabilities.
- **Tier 2:** Verified via Paystack BVN match. Unlocks Virtual Account generation.

### 4.2 Idempotency Shield
A middleware mechanism preventing double-debits or double-deposits. 
- Before firing a payment intent, Wealy generates a `uuid4` idempotency key.
- It inserts a `status="pending"` transaction into the Supabase database using this UUID as a unique constraint. If the user clicks "Pay" twice rapidly, the database rejects the duplicate UUID, preventing disaster.

### 4.3 Virtual Accounts & Polling Ledger
When a user is successfully verified,Wealy calls Flutterwave's `/virtual-account-numbers` endpoint to generate an isolated, permanent account number.
- **Ledger:** The system uses a continuous execution loop to poll incoming transactions for that specific virtual account or listens for webhooks (`charge.completed`, `transfer.completed`).
- **Accounting:** A user's wallet balance isn't explicitly saved. It is dynamically calculated by summing all `success` transactions (`type: DEPOSIT` minus `type: WITHDRAWAL` minus `type: DEBIT`).

### 4.4 Automated Investment Rebalancing
Users can browse a curated list of global assets (e.g., S&P 500 ETF, Apple). Upon selecting an asset to buy:
1. Wealy pulls the live price from Alpha Vantage.
2. It fetches the live NGN/USD exchange rate.
3. It writes a `DEBIT` to the `transactions` ledger for the fiat side.
4. It inserts an `INVESTMENT` record into the `portfolio` table, logging the symbol, units purchased, and average cost basis.

---

## 5. Compliance & Regulatory Strategy (Nigeria)

Given the Nigerian regulatory environment, Wealy's architecture and feature set were deliberately scoped to maintain strict compliance with both the **Central Bank of Nigeria (CBN)** and the **Securities and Exchange Commission (SEC Nigeria)**.

### 5.1 CBN Tiered KYC & Wallet Limits
Under CBN's Mobile Money and Tiered KYC framework, unverified users present anti-money laundering (AML) risks. 
- **Tier 1 Logic:** The system evaluates KYC status and restricts features. Although currently mocked in the frontend for UX speed, the backend enforces a CBN-aligned `TIER_1_MAX_SINGLE_DEPOSIT` logic on unverified user limits (max ₦50,000 per transaction).
- **Tier 2 Identification:** A user cannot unlock a dedicated Virtual Account for high-volume fiat routing without actively matching their Bank Verification Number (BVN) via the Paystack KYC gateway.

### 5.2 SEC Nigeria & Permitted Asset Classes
Due to SEC Nigeria's stringent warnings regarding digital platforms offering foreign equities, Wealy enforces strict asset class scoping:
- **Exclusion of High-Risk Instruments:** To remain compliant and avoid operating as an unlicensed exchange, Wealy explicitly scopes out direct crypto trading and leveraged retail FX.
- **Curated US Equities (Digital Sub-Broker Model):** By offering fractional shares of highly liquid, regulated global assets (like S&P 500 ETFs or Apple), Wealy mirrors a digital sub-broker architecture. The tradeable asset list in `main.py` is deliberately hardcoded (`_ASSETS`) to a vetted, highly compliant list instead of offering an unstructured global screener. 

---

## 6. End-to-End System Flow

The full user journey occurs strictly sequentially as governed by the `main.py` pipeline:

1. **Gate 1 (Auth):** User attempts logging in via the `/auth/login` endpoint using Clerk's backend SDK. 
2. **Gate 2 (Identity):** The application queries `profiles` in Supabase. If missing, prompts the user to enter their BVN to hit Paystack's endpoint.
3. **Gate 3 (Vault Generation):** Successful KYC causes Wealy to request a Flutterwave virtual account, logging the `account_number` into the verified profile.
4. **Gate 4 (Funding):** User sends money natively to their dedicated virtual account. The Flutterwave backend detects it, marks it as successful, matching the `tx_ref`.
5. **Gate 5 (Investing):** User clicks "Buy APPL". The backend makes a database atomic query checking if the dynamically calculated fiat balance covers the Alpha-vantage quoted USD/NGN converted price. 

## 7. Future Expansion Roadmap
- **MFA Layer:** Expanding Clerk to require OTP or physical security keys for large withdrawals.
- **Round-Up Savings:** Intercepting external user spending and investing the spare change into VOO.
- **Automated Rebalancing Engine:** If the portfolio breaches a 60% Stocks / 40% Cash drift, automatically triggering sell/buy actions to revert to baseline.
