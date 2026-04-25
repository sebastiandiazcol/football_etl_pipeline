import { Link, useNavigate } from 'react-router-dom';
import { type CSSProperties } from 'react';
import { useAuth } from '../hooks/useAuth';

const styles: Record<string, CSSProperties> = {
  nav: {
    background: 'linear-gradient(90deg, #0f172a 0%, #1e293b 100%)',
    borderBottom: '1px solid #334155',
    padding: '0 2rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '60px',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    color: '#38bdf8',
    fontWeight: 700,
    fontSize: '1.1rem',
    textDecoration: 'none',
  },
  links: {
    display: 'flex',
    alignItems: 'center',
    gap: '1.5rem',
  },
  link: {
    color: '#94a3b8',
    textDecoration: 'none',
    fontSize: '0.9rem',
    transition: 'color 0.2s',
  },
  userSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
  },
  badge: {
    padding: '2px 8px',
    borderRadius: '9999px',
    fontSize: '0.75rem',
    fontWeight: 600,
    background: '#0ea5e9',
    color: '#fff',
  },
  logoutBtn: {
    background: 'transparent',
    border: '1px solid #475569',
    color: '#94a3b8',
    padding: '4px 12px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.85rem',
  },
};

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <nav style={styles.nav}>
      <Link to="/dashboard" style={styles.logo}>
        ⚽ Football Analytics
      </Link>
      <div style={styles.links}>
        <Link to="/dashboard" style={styles.link}>Dashboard</Link>
        <Link to="/analytics" style={styles.link}>Analytics</Link>
        {user?.role === 'admin' && (
          <Link to="/dashboard#pipeline" style={styles.link}>Pipeline</Link>
        )}
      </div>
      {user && (
        <div style={styles.userSection}>
          <span style={{ color: '#e2e8f0', fontSize: '0.85rem' }}>{user.email}</span>
          <span style={{
            ...styles.badge,
            background: user.role === 'admin' ? '#dc2626' : '#0ea5e9',
          }}>
            {user.role}
          </span>
          <button style={styles.logoutBtn} onClick={handleLogout}>Logout</button>
        </div>
      )}
    </nav>
  );
}
