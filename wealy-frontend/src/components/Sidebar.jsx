import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Briefcase, ListOrdered, Wallet, ShieldCheck, Bitcoin, HelpCircle, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Sidebar.css';

const Sidebar = () => {
  const location = useLocation();
  const { logout } = useAuth();

  const navItems = [
    { name: 'Portfolio', path: '/', icon: Briefcase },
    { name: 'Wallet', path: '/wallet', icon: Wallet },
    { name: 'Verification', path: '/verification', icon: ShieldCheck },
  ];

  return (
    <aside className="sidebar">
      <div className="brand-section">
        <h1 className="brand-title">Private Office</h1>
        <p className="wealth-tier">WEALTH TIER: ELITE</p>
      </div>

      <nav className="nav-menu">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link 
              to={item.path} 
              key={item.name} 
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} className="nav-icon" />
              <span>{item.name}</span>
            </Link>
          );
        })}

        <div className="nav-item disabled">
          <Bitcoin size={20} className="nav-icon" />
          <span>Crypto</span>
          <span className="badge-soon">SOON</span>
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className="user-plan">
          <button className="btn-primary w-full shadow-lg">Upgrade Plan</button>
        </div>
        
        <Link to="/help" className="nav-item">
          <HelpCircle size={20} className="nav-icon" />
          <span>Help Center</span>
        </Link>
        <button className="nav-item btn-logout" onClick={() => logout()}>
          <LogOut size={20} className="nav-icon" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
