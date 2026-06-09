import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './Transactions.css';

const Transactions = () => {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.clerk_id) {
      fetch(`http://localhost:8000/api/transactions/${user.clerk_id}`)
        .then(res => res.json())
        .then(data => {
          setTransactions(data.transactions || []);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }
  }, [user]);

  if (loading) return <div className="page-container" style={{padding: '5rem', color: 'var(--slate-400)'}}>Loading transaction history...</div>;

  return (
    <div className="transactions-container animate-fade-in">
      <header className="page-header">
        <h1>Transaction History</h1>
        <p>A complete ledger of your deposits, withdrawals, and asset purchases.</p>
      </header>

      <div className="card">
        {(!transactions || transactions.length === 0) ? (
          <div className="empty-state">
            <span style={{fontSize: '3rem', opacity: 0.5}}>🕒</span>
            <p>No transactions found.</p>
          </div>
        ) : (
          <div className="tx-list">
            {transactions.map((tx, idx) => {
              const amount = parseFloat(tx.amount || 0);
              const isPositive = amount > 0;
              const isPending = tx.status === 'pending';
              
              return (
                <div key={tx.id || idx} className="tx-row">
                  <div className={`tx-icon ${isPositive ? 'positive' : 'negative'}`}>
                    {isPositive ? '↗' : '↘'}
                  </div>
                  <div className="tx-details">
                    <h4>{tx.type || 'Unknown'}</h4>
                    <p>{tx.idempotency_key || 'No Ref'} • {tx.currency || 'NGN'}</p>
                  </div>
                  <div className="tx-status">
                    {isPending ? (
                      <span className="badge-pending">⏳ Pending</span>
                    ) : (
                      <span className="badge-success">✅ Success</span>
                    )}
                  </div>
                  <div className={`tx-amount ${isPositive ? 'positive' : 'negative'}`}>
                    {isPositive ? '+' : ''}${Math.abs(amount).toLocaleString('en-US', {minimumFractionDigits: 2})}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Transactions;
