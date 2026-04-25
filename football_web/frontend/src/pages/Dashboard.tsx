import { useEffect, useState, type CSSProperties } from 'react';
import api from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import type { DashboardStats, TeamMatch } from '../types';
import { dashboardModules } from '../modules/registry';
import type { ModuleProps } from '../modules/types';

const s: Record<string, CSSProperties> = {
  page: { minHeight: '100vh', background: '#0f172a', padding: '2rem' },
  header: { marginBottom: '2rem' },
  greeting: { color: '#e2e8f0', fontSize: '1.5rem', fontWeight: 700 },
  sub: { color: '#64748b', fontSize: '0.9rem', marginTop: '0.25rem' },
};

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [matches, setMatches] = useState<TeamMatch[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<DashboardStats>('/api/dashboard/stats').then((r) => setStats(r.data)).catch(() => {}),
      api.get<TeamMatch[]>('/api/dashboard/recent-matches').then((r) => setMatches(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const moduleProps: ModuleProps = {
    stats,
    matches,
    teams: [],
    players: [],
    selectedTeamId: '',
    teamStats: [],
    onTeamChange: () => {},
    user,
  };

  const visibleModules = dashboardModules.filter(
    (m) => !m.requiredRole || user?.role === m.requiredRole,
  );

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div style={s.greeting}>
          Welcome back{user?.full_name ? `, ${user.full_name}` : ''} 👋
        </div>
        <div style={s.sub}>Football Analytics Dashboard • {new Date().toLocaleDateString()}</div>
      </div>

      {loading ? (
        <div style={{ color: '#38bdf8' }}>Loading data…</div>
      ) : (
        visibleModules.map(({ id, component: Module }) => (
          <Module key={id} {...moduleProps} />
        ))
      )}
    </div>
  );
}
