import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const s: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem',
  },
  card: {
    background: '#1e293b',
    borderRadius: '16px',
    padding: '2.5rem',
    width: '100%',
    maxWidth: '420px',
    boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
  },
  logo: {
    textAlign: 'center' as const,
    marginBottom: '2rem',
  },
  emoji: { fontSize: '3rem', display: 'block', marginBottom: '0.5rem' },
  title: { color: '#38bdf8', fontSize: '1.5rem', fontWeight: 700, margin: 0 },
  subtitle: { color: '#64748b', fontSize: '0.875rem', marginTop: '0.25rem' },
  tabRow: { display: 'flex', marginBottom: '1.5rem', background: '#0f172a', borderRadius: '8px', padding: '4px' },
  tab: (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: '8px',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: 600,
    background: active ? '#0ea5e9' : 'transparent',
    color: active ? '#fff' : '#64748b',
    transition: 'all 0.2s',
  }),
  field: { marginBottom: '1rem' },
  label: { display: 'block', color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.4rem' },
  input: {
    width: '100%',
    background: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#e2e8f0',
    fontSize: '0.95rem',
    boxSizing: 'border-box' as const,
    outline: 'none',
  },
  btn: {
    width: '100%',
    background: 'linear-gradient(90deg, #0ea5e9, #38bdf8)',
    border: 'none',
    borderRadius: '8px',
    padding: '12px',
    color: '#fff',
    fontWeight: 700,
    fontSize: '1rem',
    cursor: 'pointer',
    marginTop: '0.5rem',
  },
  error: {
    background: '#450a0a',
    border: '1px solid #dc2626',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#fca5a5',
    fontSize: '0.875rem',
    marginBottom: '1rem',
  },
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [mfaRequired, setMfaRequired] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await login(email, password, mfaRequired ? totpCode : undefined);
      if (result.mfaRequired) {
        setMfaRequired(true);
        setLoading(false);
        return;
      }
      navigate('/dashboard');
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Login failed';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { default: api } = await import('../hooks/useApi');
      await api.post('/auth/register', { email, password, full_name: fullName || undefined });
      // Auto-login after register
      const result = await login(email, password);
      if (!result.mfaRequired) navigate('/dashboard');
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Registration failed';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>
          <span style={s.emoji}>⚽</span>
          <h1 style={s.title}>Football Analytics</h1>
          <p style={s.subtitle}>Sign in to your dashboard</p>
        </div>

        <div style={s.tabRow}>
          <button style={s.tab(tab === 'login')} onClick={() => { setTab('login'); setError(''); }}>
            Sign In
          </button>
          <button style={s.tab(tab === 'register')} onClick={() => { setTab('register'); setError(''); }}>
            Register
          </button>
        </div>

        {error && <div style={s.error}>{error}</div>}

        {tab === 'login' ? (
          <form onSubmit={handleLogin}>
            <div style={s.field}>
              <label style={s.label}>Email</label>
              <input style={s.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Password</label>
              <input style={s.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="••••••••" />
            </div>
            {mfaRequired && (
              <div style={s.field}>
                <label style={s.label}>Authenticator Code</label>
                <input style={s.input} type="text" value={totpCode} onChange={(e) => setTotpCode(e.target.value)} placeholder="6-digit code" maxLength={6} />
              </div>
            )}
            <button style={s.btn} type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister}>
            <div style={s.field}>
              <label style={s.label}>Full Name (optional)</label>
              <input style={s.input} type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Email</label>
              <input style={s.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" />
            </div>
            <div style={s.field}>
              <label style={s.label}>Password</label>
              <input style={s.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="Min 8 chars, upper, lower, digit, special" />
            </div>
            <button style={s.btn} type="submit" disabled={loading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
