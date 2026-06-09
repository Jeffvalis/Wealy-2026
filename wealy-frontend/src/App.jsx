import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import Sidebar from './components/Sidebar';
import Auth from './components/Auth';
import Wallet from './components/Wallet';
import Verification from './components/Verification';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css';

// We extract the sub-routes logic so we can use `useLocation` hook
const AppContent = () => {
  const location = useLocation();
  const { user, loading } = useAuth();
  const isAuthPage = location.pathname === '/auth';

  if (loading) {
    return <div style={{height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center'}}>Loading Private Office...</div>;
  }

  if (!user && !isAuthPage) {
    return <Navigate to="/auth" replace />;
  }

  if (user && isAuthPage) {
    return <Navigate to="/" replace />;
  }

  if (isAuthPage) {
    return (
      <Routes>
        <Route path="/auth" element={<Auth />} />
      </Routes>
    );
  }

  return (
    <div className="page-container">
      <Sidebar />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/wallet" element={<Wallet />} />
          <Route path="/verification" element={<Verification />} />
        </Routes>
      </div>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;
