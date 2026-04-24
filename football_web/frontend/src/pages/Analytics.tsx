import { useEffect, useState, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import api from '../hooks/useApi';
import { Team, PlayerStat, TeamMatch } from '../types';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend);

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: '#0f172a', padding: '2rem' },
  title: { color: '#e2e8f0', fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' },
  controls: { display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap' as const },
  select: { background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '8px 14px', color: '#e2e8f0', fontSize: '0.9rem' },
  exportBtn: { background: '#0ea5e9', border: 'none', borderRadius: '8px', padding: '8px 18px', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' },
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' },
  sectionTitle: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: '0.85rem' },
  th: { color: '#64748b', padding: '8px 12px', textAlign: 'left' as const, borderBottom: '1px solid #334155' },
  td: { color: '#cbd5e1', padding: '8px 12px', borderBottom: '1px solid #1e293b' },
};

const chartOptions = {
  responsive: true,
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#334155' } },
  },
};

export default function Analytics() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [teamStats, setTeamStats] = useState<TeamMatch[]>([]);
  const [players, setPlayers] = useState<PlayerStat[]>([]);

  useEffect(() => {
    api.get<Team[]>('/api/dashboard/teams').then((r) => setTeams(r.data)).catch(() => {});
    api.get<PlayerStat[]>('/api/analytics/players').then((r) => setPlayers(r.data)).catch(() => {});
  }, []);

  const fetchTeamStats = useCallback(async (teamId: string) => {
    if (!teamId) return;
    try {
      const { data } = await api.get<TeamMatch[]>(`/api/analytics/team/${teamId}`);
      setTeamStats(data);
    } catch {
      setTeamStats([]);
    }
  }, []);

  const handleTeamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setSelectedTeam(id);
    fetchTeamStats(id);
  };

  const handleExport = async (type: 'teams' | 'players') => {
    try {
      const resp = await api.get(`/api/analytics/export/${type}`, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${type}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Ignore
    }
  };

  const lineData = {
    labels: teamStats.map((_, i) => `Match ${i + 1}`),
    datasets: [
      {
        label: 'Goals For',
        data: teamStats.map((m) => m.goals_for),
        borderColor: '#4ade80',
        tension: 0.3,
        fill: false,
      },
      {
        label: 'xG',
        data: teamStats.map((m) => m.xg_for),
        borderColor: '#38bdf8',
        tension: 0.3,
        fill: false,
      },
    ],
  };

  return (
    <div style={s.page}>
      <div style={s.title}>📊 Analytics</div>

      <div style={s.controls}>
        <select style={s.select} value={selectedTeam} onChange={handleTeamChange}>
          <option value="">— Select a team —</option>
          {teams.map((t) => (
            <option key={t.team_id} value={String(t.team_id)}>
              {t.team_name ?? `Team ${t.team_id}`}
            </option>
          ))}
        </select>
        <button style={s.exportBtn} onClick={() => handleExport('teams')}>⬇ Export Teams CSV</button>
        <button style={s.exportBtn} onClick={() => handleExport('players')}>⬇ Export Players CSV</button>
      </div>

      {selectedTeam && (
        <div style={s.card}>
          <div style={s.sectionTitle}>Team Performance Over Time</div>
          {teamStats.length > 0 ? (
            <Line data={lineData} options={chartOptions} />
          ) : (
            <div style={{ color: '#475569' }}>No data for this team.</div>
          )}
        </div>
      )}

      <div style={s.card}>
        <div style={s.sectionTitle}>Top Players by xG</div>
        <div style={{ overflowX: 'auto' }}>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>#</th>
                <th style={s.th}>Player ID</th>
                <th style={s.th}>Matches</th>
                <th style={s.th}>Total xG</th>
                <th style={s.th}>Total Shots</th>
                <th style={s.th}>Total Goals</th>
              </tr>
            </thead>
            <tbody>
              {players.map((p, i) => (
                <tr key={p.player_id}>
                  <td style={s.td}>{i + 1}</td>
                  <td style={s.td}>{p.player_id}</td>
                  <td style={s.td}>{p.matches_played}</td>
                  <td style={{ ...s.td, color: '#38bdf8', fontWeight: 600 }}>{p.total_xg?.toFixed(2) ?? '—'}</td>
                  <td style={s.td}>{p.total_shots ?? '—'}</td>
                  <td style={s.td}>{p.total_goals ?? '—'}</td>
                </tr>
              ))}
              {players.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ ...s.td, textAlign: 'center', color: '#475569' }}>No player data available</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
