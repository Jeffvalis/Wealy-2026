import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, AlertCircle, CheckCircle2 } from 'lucide-react';
import './Wallet.css'; // Reusing some base styles

const Verification = () => {
  const { user, updateProfile } = useAuth();
  const [bvn, setBvn] = useState('');
  const [status, setStatus] = useState('pending'); // pending, submitted, verified
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (bvn.length === 11) {
      setStatus('submitted');
      
      try {
        const res = await fetch('http://localhost:8000/api/kyc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ clerk_id: user.clerk_id, email: user.email, bvn })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Verification failed');
        
        // Update context to reflect KYC success and new VA
        updateProfile(data.profile);
        setStatus('verified');
      } catch (err) {
        setStatus('pending');
        setError(err.message);
      }
    }
  };

  if (!user) return <div style={{padding: '5rem', textAlign: 'center'}}>Please log in to verify your identity.</div>;

  return (
    <div className="dashboard-container animate-fade-in">
      <header className="page-header">
        <h1>Identity Verification</h1>
        <p>Regulatory compliance for processing large transactions.</p>
      </header>

      <div className="card" style={{ maxWidth: '600px' }}>
        {status === 'pending' && (
          <div className="form-flow">
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', color: 'var(--color-primary)' }}>
              <ShieldCheck size={32} />
              <div>
                <h3 style={{ marginBottom: '0.25rem' }}>Secure BVN Check</h3>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
                  To comply with apex banking regulations, please enter your Bank Verification Number.
                  This does not give us access to your bank accounts.
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>11-DIGIT BVN</label>
                <input 
                  type="text" 
                  placeholder="00000000000" 
                  maxLength={11}
                  value={bvn}
                  onChange={(e) => setBvn(e.target.value.replace(/\D/g, ''))}
                  required
                />
              </div>
              <button type="submit" className="btn-primary w-full btn-large mt-4">Verify Identity</button>
            </form>
            
            {error && <div style={{ color: 'var(--color-danger)', marginTop: '1rem', fontSize: '0.9rem' }}>{error}</div>}
            
            <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: 'var(--color-bg-light)', borderRadius: '8px', display: 'flex', gap: '0.75rem' }}>
               <AlertCircle size={20} color="var(--color-text-muted)" />
               <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>We use AES-256 military-grade encryption to securely transmit your data to Paystack for real-time verification.</p>
            </div>
          </div>
        )}

        {status === 'submitted' && (
          <div style={{ textAlign: 'center', padding: '4rem 2rem' }}>
            <div className="spinner" style={{ margin: '0 auto 1.5rem' }}></div>
            <h3>Verifying against global registries...</h3>
            <p style={{ color: 'var(--color-text-muted)', marginTop: '0.5rem' }}>This usually takes a few seconds.</p>
          </div>
        )}

        {status === 'verified' && (
          <div style={{ textAlign: 'center', padding: '4rem 2rem' }}>
            <CheckCircle2 size={64} color="var(--color-success)" style={{ margin: '0 auto 1.5rem' }} />
            <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '2rem' }}>Verification Complete</h3>
            <p style={{ color: 'var(--color-text-muted)', marginTop: '0.5rem', marginBottom: '2rem' }}>
              Your profile has been upgraded to Wealth Tier: Elite. You now have full access to deposit and withdrawal capabilities.
            </p>
            <button className="btn-primary" onClick={() => window.location.href = '/wallet'}>Proceed to Wallet</button>
          </div>
        )}
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .spinner {
          width: 40px; height: 40px;
          border: 3px solid rgba(0,0,0,0.1);
          border-radius: 50%;
          border-top-color: var(--color-primary);
          animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .mt-4 { margin-top: 1.5rem; }
      `}} />
    </div>
  );
};

export default Verification;
