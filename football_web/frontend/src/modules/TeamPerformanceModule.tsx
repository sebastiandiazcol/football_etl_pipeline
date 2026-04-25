import type { CSSProperties, ChangeEvent } from 'react';
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
import type { ModuleProps } from './types';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Title, Tooltip, Legend);

const s: Record<string, CSSProperties> = {
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' },
  title: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
  select: { background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '8px 14px', color: '#e2e8f0', fontSize: '0.9rem', marginBottom: '1.5rem', display: 'block' },
};

const chartOptions = {
  responsive: true,
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#334155' } },
  },
};

export default function TeamPerformanceModule({ teams, selectedTeamId, teamStats, onTeamChange }: ModuleProps) {
  const handleChange = (e: ChangeEvent<HTMLSelectElement>) => onTeamChange(e.target.value);

  const lineData = {
    labels: teamStats.map((_, i) => `Match ${i + 1}`),
    datasets: [
      { label: 'Goals For', data: teamStats.map((m) => m.goals_for), borderColor: '#4ade80', tension: 0.3, fill: false },
      { label: 'xG', data: teamStats.map((m) => m.xg_for), borderColor: '#38bdf8', tension: 0.3, fill: false },
    ],
  };

  return (
    <div style={s.card}>
      <div style={s.title}>Team Performance Over Time</div>
      <select style={s.select} value={selectedTeamId} onChange={handleChange}>
        <option value="">— Select a team —</option>
        {teams.map((t) => (
          <option key={t.team_id} value={String(t.team_id)}>
            {t.team_name ?? `Team ${t.team_id}`}
          </option>
        ))}
      </select>
      {selectedTeamId && (
        teamStats.length > 0 ? (
          <Line data={lineData} options={chartOptions} />
        ) : (
          <div style={{ color: '#475569' }}>No data for this team.</div>
        )
      )}
    </div>
  );
}
