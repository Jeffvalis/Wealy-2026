# Wealth Management TPM Portfolio - 15 Week Plan

## Month 1: Identity, Trust & Automated Mastery
**Focus:** Secure onboarding and mastering the "Agent-First" workflow in Antigravity.

### Week 1: Antigravity Bootcamp & Setup
**Goal:** Configure your AI-first workspace.
**Task:** Use Antigravity’s Terminal and Agent to scaffold your 15 project folders.
**Learning:** Learn how to use "Agent Prompts" to have Antigravity write your requirements.txt and initial main.py files autonomously.

### Week 2: Project 1 – The KYC "Gatekeeper" (Sign-up Logic)
**Goal:** Build the compliance engine for user entry.
**Task:** Command an Antigravity agent to create a Python logic gate that checks user input against CBN KYC tiers.

### Week 3: Project 2 – User Auth & Identity (Sign-in/Sign-up)
**Goal:** Secure user access.
**Task:** Use Antigravity to build a Sign-up/Sign-in function. Use bcrypt for password hashing and simulate a "Phone Number + OTP" flow.
**TPM Deliverable:** Write a PRD on why Multi-Factor Authentication (MFA) is critical for Cowrywise trust.

### Week 4: Project 3 – The Idempotent "Double-Debit" Shield
**Goal:** Ensure 100% payment accuracy.
**Task:** Have your agent build a middleware that checks for unique transaction_ids before updating a user's balance.

## Month 2: Payments, Pipes & Portfolios
**Focus:** The "Mechanics" of money—how users fund their accounts and invest.

### Week 5: Project 4 – The Wealth-Tech Database (Payment Processing)
**Goal:** Create the "Brain" of your payments system.
**Task:** Design a PostgreSQL/SQLite schema using Antigravity. Create tables for Users, Wallets, and Transactions.
**TPM Deliverable:** Create an Entity-Relationship (ER) Diagram showing how money flows from a "Bank Deposit" to a "Savings Stash."

### Week 6: Project 5 – The "Money In" Engine (Payment Processing)
**Goal:** Simulate moving money from a bank account to the platform.
**Task:** Build a Python function that simulates an API call to a payment gateway (e.g., Paystack/Stripe).
**Learning:** Handle "Pending" vs "Successful" transaction states.

### Week 7: Project 6 – API Aggregator (Index Funds & Stocks)
**Goal:** Connect your users to the world’s markets.
**Task:** Use Antigravity's Browser Agent to research documentation for a mock Investment API (like Alpaca or a local Mutual Fund provider). Build the "connector" that fetches real-time prices for an Index Fund.

### Week 8: Project 7 – Interest Accrual & Portfolio Rebalancing
**Goal:** Automate the growth of user wealth.
**Task:** Build the logic that applies daily interest (using the decimal module) and "rebalances" a user's portfolio if their stock-to-cash ratio gets out of whack.

## Month 3: The Capstone & Final Polish
**Focus:** Convergence. Putting all the pieces together into a single "Wealth App."

### Week 9: Project 8 – The "Round-Up" Savings Feature
**Goal:** A "sticky" product feature to drive user engagement.
**Task:** Build the logic that detects a transaction, rounds it up, and moves the "spare change" to a savings wallet.

### Week 10: Project 9 – The System Health Dashboard
**Goal:** Monitor your entire payment ecosystem.
**Task:** Build a script that summarizes total successful deposits, failed KYC attempts, and current "Assets Under Management" (AUM).

### Week 11: Project 10 – Capstone Integration (Part 1)
**Goal:** The "Wealth Management Application" core.
**Task:** Link your Auth, Payment Database, and Index Fund API into one single WealthManager class.
**Challenge:** Ask Antigravity to "Run a simulation of 100 users signing up, depositing money, and buying an Index Fund" to test your system.

### Week 12: Project 11 – Capstone Polish & Final Portfolio
**Goal:** Show your work to Cowrywise.
**Task:** Use Antigravity to generate clean documentation for your entire codebase.
**TPM Deliverable:** Create a final Case Study Notion Page that tells the story of how you built a scalable fintech from scratch.

## Month 4: High-Stakes Testing & Actionable Intel
**Focus:** Moving from "Code" to "System." Using real payment sandboxes (Paystack/Flutterwave) and market data to stress-test your wealth app.

### Week 13: The "Payment Gauntlet" (Live Sandbox Integration)
**Goal:** Move away from mock functions to actual API calls.
**The Build:** Use Antigravity to connect your 05_Money_In_Engine to the Paystack or Flutterwave Sandbox.
**The Test:** Trigger a real "Payment Initialized" event. Use the sandbox "Test Cards" to simulate a Successful Payment, a Declined Card, and a System Timeout.
**Actionable Info:** Log the "Time to Success." As a TPM, if your payment gateway takes >5 seconds to respond, you need to document a "User Loading Experience" strategy.

### Week 14: The "Market Crash" Stress Test
**Goal:** See how your Interest and Rebalancing engines handle "Bad Data."
**The Build:** Feed your 07_API_Aggregator a "dirty" data set (e.g., a stock price that drops 99% in one second or a negative interest rate).
**The Test:**
* Data Integrity Check: Does your Decimal math handle the 99% drop without rounding into a negative user balance?
* Circuit Breaker: Write a logic gate that "pauses" trading if the API returns a price that is 20% different from the last 5-minute average.
**Actionable Info:** This is Risk Mitigation. You are proving you can protect Cowrywise’s assets during a market anomaly.

### Week 15: The "Shadow Launch" (Actionable Metrics)
**Goal:** Run your Capstone project as if it were live with 100 "Ghost Users."
**The Build:** Write a script in Antigravity that automates 100 different user journeys simultaneously:
* 50 users sign up and save ₦5,000.
* 25 users sign up but fail KYC.
* 25 users try to withdraw more than they have.
**The Deliverable:** The "TPM Health Dashboard"
Create a report showing: KYC Conversion Rate, Average Transaction Latency, and Database Deadlocks (if any).
