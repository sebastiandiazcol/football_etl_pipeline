import { useEffect, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import api from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import { DashboardStats, TeamMatch } from '../types';
import PipelineRunner from '../components/PipelineRunner';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend);

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#0f172a', padding: '2rem' },
  header: { marginBottom: '2rem' },
  greeting: { color: '#e2e8f0', fontSize: '1.5rem', fontWeight: 700 },
  sub: { color: '#64748b', fontSize: '0.9rem', marginTop: '0.25rem' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' },
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.25rem' },
  cardLabel: { color: '#64748b', fontSize: '0.8rem', marginBottom: '0.5rem' },
  cardValue: { color: '#38bdf8', fontSize: '1.75rem', fontWeight: 700 },
  section: { marginBottom: '2rem' },
  sectionTitle: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
  chartsRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' },
  chartCard: { background: '#1e293b', borderRadius: '12px', padding: '1.25rem' },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: '0.85rem' },
  th: { color: '#64748b', padding: '8px 12px', textAlign: 'left' as const, borderBottom: '1px solid #334155' },
  td: { color: '#cbd5e1', padding: '8px 12px', borderBottom: '1px solid #1e293b' },
};

const resultColor: Record<string, string> = { W: '#4ade80', D: '#fbbf24', L: '#f87171' };

const chartOptions = {
  responsive: true,
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#334155' } },
  },
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

  // Build goals per team (top 10)
  const teamGoals: Record<number, number> = {};
  matches.forEach((m) => {
    teamGoals[m.team_id] = (teamGoals[m.team_id] ?? 0) + m.goals_for;
  });
  const top10 = Object.entries(teamGoals)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  const barData = {
    labels: top10.map(([id]) => `Team ${id}`),
    datasets: [{ label: 'Goals', data: top10.map(([, g]) => g), backgroundColor: '#0ea5e9' }],
  };

  const lineData = {
    labels: matches.map((_, i) => `#${i + 1}`),
    datasets: [
      {
        label: 'Total Goals',
        data: matches.map((m) => m.goals_for + m.goals_against),
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56,189,248,0.1)',
        tension: 0.3,
        fill: true,
      },
    ],
  };

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
        <>
          <div style={s.statsGrid}>
            {[
              { label: 'Total Matches', value: stats?.total_matches ?? '—' },
              { label: 'Total Teams', value: stats?.total_teams ?? '—' },
              { label: 'BTTS %', value: stats ? `${stats.btts_percentage}%` : '—' },
              { label: 'Over 2.5 %', value: stats ? `${stats.over25_percentage}%` : '—' },
              { label: 'Avg Goals/Match', value: stats?.avg_goals_per_match ?? '—' },
            ].map(({ label, value }) => (
              <div key={label} style={s.card}>
                <div style={s.cardLabel}>{label}</div>
                <div style={s.cardValue}>{String(value)}</div>
              </div>
            ))}
          </div>

          <div style={s.chartsRow}>
            <div style={s.chartCard}>
              <div style={s.sectionTitle}>Goals by Team (Top 10)</div>
              <Bar data={barData} options={chartOptions} />
            </div>
            <div style={s.chartCard}>
              <div style={s.sectionTitle}>Goals Trend (Recent Matches)</div>
              <Line data={lineData} options={chartOptions} />
            </div>
          </div>

          <div style={s.card}>
            <div style={s.sectionTitle}>Recent Matches</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Date</th>
                    <th style={s.th}>Team</th>
                    <th style={s.th}>Opponent</th>
                    <th style={s.th}>GF</th>
                    <th style={s.th}>GA</th>
                    <th style={s.th}>Result</th>
                    <th style={s.th}>xG</th>
                    <th style={s.th}>Pts</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m, i) => (
                    <tr key={i}>
                      <td style={s.td}>{m.date_key}</td>
                      <td style={s.td}>{m.team_id}</td>
                      <td style={s.td}>{m.opponent_id}</td>
                      <td style={s.td}>{m.goals_for}</td>
                      <td style={s.td}>{m.goals_against}</td>
                      <td style={{ ...s.td, color: resultColor[m.match_result] ?? '#94a3b8', fontWeight: 700 }}>
                        {m.match_result}
                      </td>
                      <td style={s.td}>{m.xg_for?.toFixed(2) ?? '—'}</td>
                      <td style={s.td}>{m.points}</td>
                    </tr>
                  ))}
                  {matches.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ ...s.td, textAlign: 'center', color: '#475569' }}>
                        No match data available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {user?.role === 'admin' && <PipelineRunner />}
        </>
      )}
    </div>
  );
}
