import type { CSSProperties } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import type { ModuleProps } from './types';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const s: Record<string, CSSProperties> = {
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.25rem', marginBottom: '2rem' },
  title: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
};

const chartOptions = {
  responsive: true,
  plugins: { legend: { labels: { color: '#94a3b8' } } },
  scales: {
    x: { ticks: { color: '#64748b' }, grid: { color: '#1e293b' } },
    y: { ticks: { color: '#64748b' }, grid: { color: '#334155' } },
  },
};

export default function GoalsBarChartModule({ matches }: ModuleProps) {
  const teamGoals: Record<number, number> = {};
  matches.forEach((m) => {
    teamGoals[m.team_id] = (teamGoals[m.team_id] ?? 0) + m.goals_for;
  });
  const top10 = Object.entries(teamGoals)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);

  const data = {
    labels: top10.map(([id]) => `Team ${id}`),
    datasets: [{ label: 'Goals', data: top10.map(([, g]) => g), backgroundColor: '#0ea5e9' }],
  };

  return (
    <div style={s.card}>
      <div style={s.title}>Goals by Team (Top 10)</div>
      <Bar data={data} options={chartOptions} />
    </div>
  );
}
