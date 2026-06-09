import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ArrowUpRight, MessageSquare, Calendar, X, Bell } from 'lucide-react';
import './Dashboard.css';

// ── Asset catalogs per tab ─────────────────────────────────────────────────
const STOCKS_CATALOG = [
  { id: 'AAPL', name: 'Apple Inc.',        price: 189.20,  change: '-1.24%', changeType: 'negative' },
  { id: 'TSLA', name: 'Tesla Inc.',        price: 178.50,  change: '+3.45%', changeType: 'positive' },
  { id: 'MSFT', name: 'Microsoft Corp',    price: 405.12,  change: '+1.10%', changeType: 'positive' },
  { id: 'NVDA', name: 'Nvidia Corp',       price: 850.33,  change: '+2.50%', changeType: 'positive' },
  { id: 'AMZN', name: 'Amazon.com Inc.',   price: 175.00,  change: '+0.95%', changeType: 'positive' },
  { id: 'GOOGL',name: 'Alphabet Inc.',     price: 175.50,  change: '+0.60%', changeType: 'positive' },
  { id: 'META', name: 'Meta Platforms',    price: 490.00,  change: '+1.80%', changeType: 'positive' },
  { id: 'JPM',  name: 'JPMorgan Chase',    price: 200.00,  change: '+0.40%', changeType: 'positive' },
  { id: 'BAC',  name: 'Bank of America',   price: 37.50,   change: '-0.30%', changeType: 'negative' },
  { id: 'GLD',  name: 'SPDR Gold Shares',  price: 218.12,  change: '+2.15%', changeType: 'positive' },
];

const INDICES_CATALOG = [
  { id: 'SPY',  name: 'S&P 500 Index ETF', price: 520.00,  change: '+0.55%', changeType: 'positive', noTrade: true },
  { id: 'QQQ',  name: 'NASDAQ 100 ETF',    price: 440.00,  change: '+0.80%', changeType: 'positive', noTrade: true },
  { id: 'DIA',  name: 'Dow Jones ETF',     price: 390.00,  change: '+0.30%', changeType: 'positive', noTrade: true },
  { id: 'IWM',  name: 'Russell 2000 ETF',  price: 200.00,  change: '-0.20%', changeType: 'negative', noTrade: true },
  { id: 'VTI',  name: 'Vanguard Total Mkt',price: 245.00,  change: '+0.50%', changeType: 'positive', noTrade: true },
];

const ETFS_CATALOG = [
  { id: 'VOO',  name: 'Vanguard S&P 500',  price: 512.44,  change: '+0.82%', changeType: 'positive' },
  { id: 'ARKK', name: 'ARK Innovation',    price: 48.00,   change: '+2.10%', changeType: 'positive' },
  { id: 'SCHD', name: 'Schwab Dividend',   price: 77.00,   change: '+0.35%', changeType: 'positive' },
  { id: 'XLF',  name: 'Financial Select',  price: 41.00,   change: '+0.60%', changeType: 'positive' },
  { id: 'IAU',  name: 'iShares Gold ETF',  price: 40.00,   change: '+1.90%', changeType: 'positive' },
  { id: 'BITO', name: 'Bitcoin Strategy',  price: 26.00,   change: '+4.50%', changeType: 'positive' },
];

const fmtNGN = (amount) =>
  '₦' + Number(amount).toLocaleString('en-NG', { minimumFractionDigits: 2 });

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [balance, setBalance]           = useState(0);
  const [loading, setLoading]           = useState(true);
  const [activeTab, setActiveTab]       = useState('Stocks');
  const [holdings, setHoldings]         = useState({});   // symbol → total_units

  // Notification bell
  const [showBell, setShowBell]         = useState(false);
  const [recentTxs, setRecentTxs]       = useState([]);
  const bellRef                         = useRef(null);

  // Invest modal
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [investAmount, setInvestAmount]   = useState('');
  const [investing, setInvesting]         = useState(false);
  const [modalError, setModalError]       = useState('');

  // ── Helpers ────────────────────────────────────────────────────────────────
  const catalogForTab = () => {
    if (activeTab === 'Indices') return INDICES_CATALOG;
    if (activeTab === 'ETFs')    return ETFS_CATALOG;
    return STOCKS_CATALOG;
  };

  // Merge holdings into catalog and sort owned → most invested first
  const sortedAssets = () => {
    return catalogForTab()
      .map(a => ({
        ...a,
        totalUnits: holdings[a.id] ?? 0,
        totalValue: (holdings[a.id] ?? 0) * a.price,
      }))
      .sort((a, b) => b.totalValue - a.totalValue);
  };

  // ── Data fetching ──────────────────────────────────────────────────────────
  const fetchPortfolio = async (clerkId) => {
    try {
      const res  = await fetch(`http://localhost:8000/api/portfolio/${clerkId}`);
      const data = await res.json();
      const map  = {};
      (data.holdings || []).forEach(h => { map[h.symbol] = h.total_units; });
      setHoldings(map);
      return data.cash_balance || 0;
    } catch (err) {
      console.error('Portfolio fetch error:', err);
      return null;
    }
  };

  const fetchRecentTxs = async (clerkId) => {
    try {
      const res  = await fetch(`http://localhost:8000/api/transactions/${clerkId}`);
      const data = await res.json();
      setRecentTxs((data.transactions || []).slice(0, 4));
    } catch (err) {
      console.error('Tx fetch error:', err);
    }
  };

  useEffect(() => {
    if (user?.clerk_id) {
      fetchPortfolio(user.clerk_id).then(cash => {
        if (cash !== null) setBalance(cash);
        setLoading(false);
      });
      fetchRecentTxs(user.clerk_id);
    } else {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Close bell when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (bellRef.current && !bellRef.current.contains(e.target)) setShowBell(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Invest handler ─────────────────────────────────────────────────────────
  const handleInvest = async () => {
    if (!investAmount || isNaN(investAmount) || Number(investAmount) <= 0)
      return setModalError('Enter a valid NGN amount');
    setInvesting(true);
    setModalError('');
    try {
      const res  = await fetch('http://localhost:8000/api/market/buy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clerk_id:   user.clerk_id,
          symbol:     selectedAsset.id,
          amount_ngn: parseFloat(investAmount),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Investment failed');

      setSelectedAsset(null);
      setInvestAmount('');

      const newBalance = await fetchPortfolio(user.clerk_id);
      if (newBalance !== null) setBalance(newBalance);
      await fetchRecentTxs(user.clerk_id);

      alert(`✅ Bought ${parseFloat(data.units).toFixed(4)} units of ${selectedAsset.id} at $${data.price}!`);
    } catch (err) {
      setModalError(err.message);
    } finally {
      setInvesting(false);
    }
  };

  if (!user) return null;

  const displayedAssets = sortedAssets();

  return (
    <div className="dashboard-container animate-fade-in">

      {/* ── Notification Bell (top-right) ────────────────────────────── */}
      <div className="bell-wrapper" ref={bellRef}>
        <button className="bell-btn" onClick={() => setShowBell(v => !v)}>
          <Bell size={20} />
          {recentTxs.length > 0 && <span className="bell-dot" />}
        </button>

        {showBell && (
          <div className="bell-dropdown card">
            <div className="bell-title">Recent Activity</div>
            {recentTxs.length === 0 ? (
              <p className="bell-empty">No transactions yet</p>
            ) : (
              recentTxs.map((tx, i) => {
                const amt = parseFloat(tx.amount || 0);
                return (
                  <div key={i} className="bell-tx">
                    <span className={`bell-tx-icon ${amt >= 0 ? 'positive' : 'negative'}`}>
                      {amt >= 0 ? '↑' : '↓'}
                    </span>
                    <div className="bell-tx-meta">
                      <span className="bell-tx-type">{tx.type || '—'}</span>
                      <span className="bell-tx-status">{tx.status}</span>
                    </div>
                    <span className={`bell-tx-amount ${amt >= 0 ? 'positive' : 'negative'}`}>
                      {fmtNGN(Math.abs(amt))}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="dashboard-header">
        <div className="aum-section">
          <p className="section-label">TOTAL ASSETS UNDER MANAGEMENT</p>
          <div className="aum-value-row">
            <h2 className="aum-value">{fmtNGN(balance)}</h2>
            <span className="performance-badge positive">
              <ArrowUpRight size={16} />
              +12.4%
            </span>
          </div>
        </div>

        <div className="liquidity-card card">
          <p className="section-label">AVAILABLE LIQUIDITY</p>
          <h3 className="liquidity-value">{fmtNGN(balance)}</h3>
          <div className="action-buttons">
            <button className="btn-secondary btn-sm" onClick={() => navigate('/wallet')}>ADD FUNDS</button>
            <button className="btn-primary btn-sm"   onClick={() => navigate('/wallet')}>WITHDRAW</button>
          </div>
        </div>
      </header>

      {/* ── Main Grid ───────────────────────────────────────────────── */}
      <div className="dashboard-grid">
        <div className="main-column">
          <section className="market-section card">
            <div className="market-header">
              <h3>Traditional Market</h3>
              <div className="asset-tabs">
                {['Stocks', 'Indices', 'ETFs'].map(tab => (
                  <button
                    key={tab}
                    className={activeTab === tab ? 'active' : ''}
                    onClick={() => setActiveTab(tab)}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="asset-list">
              {displayedAssets.map(asset => (
                <div
                  key={asset.id}
                  className="asset-row"
                  onClick={() => !asset.noTrade && setSelectedAsset(asset)}
                  style={{ cursor: asset.noTrade ? 'default' : 'pointer', transition: 'background-color 0.2s' }}
                >
                  <div className="asset-icon">{asset.id}</div>
                  <div className="asset-info">
                    <h4>{asset.name}</h4>
                    <p>
                      {asset.totalUnits > 0
                        ? `${parseFloat(asset.totalUnits).toFixed(4)} units  ·  ≈ ${fmtNGN(asset.totalValue)}`
                        : '0 units'}
                    </p>
                  </div>
                  <div className="asset-chart-placeholder">
                    <div className={`mock-sparkline ${asset.changeType}`}></div>
                  </div>
                  <div className="asset-price">
                    <h4>${asset.price.toFixed(2)}</h4>
                    <p className={asset.changeType}>{asset.change}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="crypto-promo card banner-dark">
            <div className="promo-content">
              <h3>Unlock Digital Assets</h3>
              <p>Our institutional-grade crypto trading suite is arriving soon. Secure your spot in the early access program.</p>
            </div>
            <button className="btn-gold">CRYPTO EARLY ACCESS</button>
          </section>
        </div>

        <div className="side-column">
          <section className="allocation-section card">
            <h3>Allocation Mix</h3>
            <div className="donut-placeholder">
              <div className="donut-hole">
                <span className="label">Equities</span>
                <span className="value">65%</span>
              </div>
            </div>
            <div className="legend">
              <div className="legend-item"><span className="dot dot-equities"></span><span>Equities</span><span className="pct">65%</span></div>
              <div className="legend-item"><span className="dot dot-commodities"></span><span>Commodities</span><span className="pct">25%</span></div>
              <div className="legend-item"><span className="dot dot-cash"></span><span>Cash</span><span className="pct">10%</span></div>
            </div>
          </section>

          <section className="advisor-section card">
            <h3>Dedicated Advisor</h3>
            <div className="advisor-profile">
              <div className="avatar portrait-placeholder"></div>
              <div className="advisor-info">
                <h4>Julian Sterling</h4>
                <p>Senior Portfolio Strategist</p>
              </div>
            </div>
            <div className="advisor-actions">
              <button className="btn-secondary btn-full"><MessageSquare size={16}/> MESSAGE</button>
              <button className="btn-primary btn-full"><Calendar size={16}/> BOOK</button>
            </div>
          </section>
        </div>
      </div>

      {/* ── Invest Modal ────────────────────────────────────────────── */}
      {selectedAsset && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h3>Invest in {selectedAsset.name}</h3>
              <button
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--slate-400)' }}
                onClick={() => { setSelectedAsset(null); setModalError(''); setInvestAmount(''); }}
              >
                <X size={20} />
              </button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1rem' }}>
              <div style={{ padding: '1rem', background: 'var(--slate-800)', borderRadius: '8px', textAlign: 'center' }}>
                <span style={{ fontSize: '0.875rem', display: 'block', marginBottom: '0.25rem', color: 'var(--slate-400)' }}>Available Balance</span>
                <strong style={{ color: 'var(--slate-100)', fontSize: '1.25rem' }}>{fmtNGN(balance)}</strong>
              </div>

              {modalError && (
                <div style={{ color: '#ef4444', fontSize: '0.875rem', textAlign: 'center' }}>{modalError}</div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <label style={{ fontSize: '0.875rem', color: 'var(--slate-400)' }}>Amount to Invest (₦ NGN)</label>
                <input
                  type="number"
                  className="input-field"
                  placeholder="e.g. 50000"
                  value={investAmount}
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--slate-700)', background: 'var(--slate-800)', color: 'var(--slate-100)' }}
                  onChange={e => setInvestAmount(e.target.value)}
                />
              </div>

              <button
                className="btn-primary"
                onClick={handleInvest}
                disabled={investing}
                style={{ padding: '0.875rem', width: '100%', borderRadius: '8px', cursor: investing ? 'not-allowed' : 'pointer' }}
              >
                {investing ? 'Executing Trade...' : `Buy ${selectedAsset.id} with ₦`}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default Dashboard;
