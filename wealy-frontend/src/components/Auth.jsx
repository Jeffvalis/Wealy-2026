import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

const Auth = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [accessKey, setAccessKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      await login(email, accessKey);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container animate-fade-in">
      <div className="auth-hero">
        <div className="hero-content">
          <div className="brand-logo">Wealy</div>
          <h1 className="hero-title">
            The architecture of<br />your digital legacy<br />starts here.
          </h1>
          <p className="hero-subtitle">
            Access your Private Office and manage global<br />
            assets with the precision of high-end editorial<br />
            banking.
          </p>
        </div>
        
        <div className="security-badges">
          <div className="badge-item">
            <span className="badge-label">SECURITY STANDARD</span>
            <span className="badge-value"><Shield size={14} /> AES-256 Encrypted</span>
          </div>
          <div className="badge-item">
            <span className="badge-label">GLOBAL ACCESS</span>
            <span className="badge-value">Wealth Tier: Elite</span>
          </div>
        </div>
      </div>

      <div className="auth-panel">
        <div className="auth-form-wrapper">
          <div className="auth-header">
            <h2>Enter your office</h2>
            <p>Sign in to manage your digital wealth portfolio.</p>
          </div>

          <div className="sso-options">
            <button className="btn-sso">
              <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg" alt="Google" className="sso-icon" />
              Continue with Google
            </button>
            <button className="btn-sso">
              <img src="https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg" alt="Apple" className="sso-icon" />
              Continue with Apple
            </button>
            <button className="btn-sso">
              <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft" className="sso-icon" />
              Continue with Microsoft
            </button>
          </div>

          <div className="divider">
            <span>OR VIA EMAIL</span>
          </div>

          <form onSubmit={handleLogin} className="email-form">
            <div className="form-group">
              <label>WORK EMAIL</label>
              <input 
                type="email" 
                placeholder="name@company.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <div className="form-group">
              <div className="label-row">
                <label>ACCESS KEY</label>
                <a href="#" className="forgot-link">Forgot?</a>
              </div>
              <input 
                type="password" 
                placeholder="••••••••" 
                value={accessKey}
                onChange={(e) => setAccessKey(e.target.value)}
                required
              />
            </div>

            {error && <div className="error-message" style={{color: 'var(--color-danger)', fontSize: '0.875rem', marginTop: '-0.5rem'}}>{error}</div>}

            <button type="submit" className="btn-primary w-full btn-large" disabled={loading}>
              {loading ? 'Authenticating...' : 'Enter Private Office'}
            </button>
          </form>

          <div className="auth-footer">
            <p className="signup-prompt">Don't have an invitation? <a href="#">Request access</a></p>
            <div className="legal-links">
              <a href="#">PRIVACY POLICY</a>
              <a href="#">SECURITY DISCLOSURE</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Auth;
