import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { CreditCard, ArrowDownLeft, ArrowUpRight, Copy } from 'lucide-react';
import './Wallet.css';

const fmtNGN = (amount) =>
  '₦' + Number(amount || 0).toLocaleString('en-NG', { minimumFractionDigits: 2 });

const Wallet = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab]       = useState('deposit');
  const [amount, setAmount]             = useState('');
  const [withdrawAmt, setWithdrawAmt]   = useState('');
  const [bankCode, setBankCode]         = useState('');
  const [accNumber, setAccNumber]       = useState('');
  const [balance, setBalance]           = useState(0);
  const [profile, setProfile]           = useState(null);
  const [recentTxs, setRecentTxs]       = useState([]);
  const [loading, setLoading]           = useState(false);
  const [wLoading, setWLoading]         = useState(false);
  const [copied, setCopied]             = useState(false);
  const [verifying, setVerifying]       = useState(null); // tx idempotency_key being verified

  const refreshBalance = () => {
    fetch(`http://localhost:8000/api/profile/${user.clerk_id}`)
      .then(r => r.json())
      .then(d => setBalance(d.wallet_balance || 0))
      .catch(console.error);
    fetch(`http://localhost:8000/api/transactions/${user.clerk_id}`)
      .then(r => r.json())
      .then(d => setRecentTxs((d.transactions || []).slice(0, 5)))
      .catch(console.error);
  };

  const verifyDeposit = async (txRef) => {
    setVerifying(txRef);
    try {
      const res  = await fetch('http://localhost:8000/api/wallet/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clerk_id: user.clerk_id, tx_ref: txRef }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Verification failed');
      alert(data.message);
      refreshBalance();
    } catch (err) {
      alert(err.message);
    } finally {
      setVerifying(null);
    }
  };

  useEffect(() => {
    if (!user?.clerk_id) return;

    // Fetch balance + profile
    fetch(`http://localhost:8000/api/profile/${user.clerk_id}`)
      .then(r => r.json())
      .then(d => {
        setBalance(d.wallet_balance || 0);
        setProfile(d.profile || null);
      })
      .catch(console.error);

    // Fetch recent transactions
    fetch(`http://localhost:8000/api/transactions/${user.clerk_id}`)
      .then(r => r.json())
      .then(d => setRecentTxs((d.transactions || []).slice(0, 5)))
      .catch(console.error);
  }, [user]);

  const copyAccNumber = () => {
    const acc = profile?.account_number;
    if (!acc) return;
    navigator.clipboard.writeText(acc).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleDeposit = async () => {
    const amt = parseFloat(amount);
    if (!amt || amt < 1000) return alert('Minimum deposit is ₦1,000');
    setLoading(true);
    try {
      const res  = await fetch('http://localhost:8000/api/wallet/deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clerk_id: user.clerk_id, amount: amt }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Deposit failed');
      if (data.payment_link) window.open(data.payment_link, '_blank');
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async () => {
    const amt = parseFloat(withdrawAmt);
    if (!amt || amt <= 0) return alert('Enter a valid NGN amount');
    if (!bankCode || !accNumber) return alert('Please fill in bank code and account number');
    setWLoading(true);
    try {
      const res  = await fetch('http://localhost:8000/api/wallet/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clerk_id:       user.clerk_id,
          amount:         amt,
          bank_code:      bankCode,
          account_number: accNumber,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Withdrawal failed');
      alert(`✅ Withdrawal of ${fmtNGN(amt)} initiated successfully!`);
      setBalance(b => b - amt);
      setWithdrawAmt(''); setBankCode(''); setAccNumber('');
    } catch (err) {
      alert(err.message);
    } finally {
      setWLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className="dashboard-container animate-fade-in">
      <header className="page-header">
        <h1>Wallet Operations</h1>
        <p>Manage your liquidity, deposits, and bank transfers</p>
      </header>

      <div className="wallet-grid">
        {/* ── Left: Deposit / Withdraw form ── */}
        <div className="wallet-main card">
          <div className="wallet-tabs">
            <button className={activeTab === 'deposit'  ? 'active' : ''} onClick={() => setActiveTab('deposit')}>
              Deposit Funds
            </button>
            <button className={activeTab === 'withdraw' ? 'active' : ''} onClick={() => setActiveTab('withdraw')}>
              Withdraw
            </button>
          </div>

          <div className="tab-content">
            {/* ═══ DEPOSIT ═══ */}
            {activeTab === 'deposit' && (
              <div className="form-flow">
                <h3>Fund your Private Office</h3>

                <div className="form-group">
                  <label>AMOUNT (NGN)</label>
                  <input
                    type="number"
                    placeholder="e.g. 50000"
                    min="1000"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                  />
                  <span className="balance-hint">Min deposit: ₦1,000</span>
                </div>

                <div className="payment-methods">
                  <label>FUNDING SOURCE</label>
                  <div className="method-option selected">
                    <div className="method-info">
                      <CreditCard size={20} />
                      <div>
                        <h4>Card or Mobile Money</h4>
                        <p>Instant processing via Flutterwave</p>
                      </div>
                    </div>
                    <div className="radio-circle active"></div>
                  </div>
                  <div className="method-option" title="Complete KYC to get your virtual account">
                    <div className="method-info">
                      <ArrowDownLeft size={20} />
                      <div>
                        <h4>Virtual Bank Transfer</h4>
                        <p>
                          {profile?.account_number
                            ? `${profile.account_number} · ${profile.bank_name}`
                            : 'Complete KYC to generate account'}
                        </p>
                      </div>
                    </div>
                    <div className="radio-circle"></div>
                  </div>
                </div>

                <button
                  className="btn-primary w-full btn-large"
                  onClick={handleDeposit}
                  disabled={loading}
                >
                  {loading ? 'Processing...' : 'Continue to Payment Gateway'}
                </button>
              </div>
            )}

            {/* ═══ WITHDRAW ═══ */}
            {activeTab === 'withdraw' && (
              <div className="form-flow">
                <h3>Withdraw Liquidity</h3>

                <div className="form-group">
                  <label>AMOUNT (NGN)</label>
                  <input
                    type="number"
                    placeholder="e.g. 10000"
                    value={withdrawAmt}
                    onChange={e => setWithdrawAmt(e.target.value)}
                  />
                  <span className="balance-hint">Available: {fmtNGN(balance)}</span>
                </div>

                <div className="form-group">
                  <label>DESTINATION BANK CODE</label>
                  <input
                    type="text"
                    placeholder="e.g. 044 (Access Bank)"
                    value={bankCode}
                    onChange={e => setBankCode(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label>ACCOUNT NUMBER</label>
                  <input
                    type="text"
                    placeholder="10-digit bank account number"
                    value={accNumber}
                    onChange={e => setAccNumber(e.target.value)}
                  />
                </div>

                <button
                  className="btn-primary w-full btn-large"
                  onClick={handleWithdraw}
                  disabled={wLoading}
                >
                  {wLoading ? 'Processing...' : 'Initiate Transfer'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Balance + Recent transfers ── */}
        <div className="wallet-side">
          <div className="card balance-card">
            <p className="section-label">LIQUID BALANCE</p>
            <h2 className="aum-value" style={{ fontSize: '2rem' }}>{fmtNGN(balance)}</h2>

            {profile?.account_number && (
              <div className="account-details" style={{ marginTop: '1.5rem' }}>
                <p className="section-label">DEDICATED VIRTUAL ACCOUNT</p>
                <div className="account-box">
                  <div>
                    <h4>{profile.bank_name}</h4>
                    <p className="acc-num">{profile.account_number}</p>
                  </div>
                  <button className="btn-icon" onClick={copyAccNumber} title="Copy account number">
                    <Copy size={16} />
                    {copied && <span style={{ fontSize: '0.75rem', marginLeft: '4px' }}>Copied!</span>}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="card transaction-mini">
            <h3>Recent Transfers</h3>
            {recentTxs.length === 0 ? (
              <p style={{ color: 'var(--color-text-muted)', fontsize: '0.875rem', padding: '1rem 0' }}>
                No transfers yet
              </p>
            ) : (
              <div className="transfer-list">
                {recentTxs.map((tx, i) => {
                  const amt = parseFloat(tx.amount || 0);
                  const isIn = amt >= 0;
                  return (
                    <div key={i} className="transfer-item">
                      <div className={`transfer-icon ${isIn ? 'in' : 'out'}`}>
                        {isIn ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}
                      </div>
                      <div className="transfer-details">
                        <h4>{tx.type || 'Transfer'}</h4>
                        <p>{tx.status}</p>
                      </div>
                      <div className={`transfer-amount ${isIn ? 'positive' : ''}`}>
                        {isIn ? '+' : ''}{fmtNGN(Math.abs(amt))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Wallet;
