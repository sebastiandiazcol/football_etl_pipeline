import type { CSSProperties } from 'react';
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

export default function GoalsTrendModule({ matches }: ModuleProps) {
  const data = {
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
    <div style={s.card}>
      <div style={s.title}>Goals Trend (Recent Matches)</div>
      <Line data={data} options={chartOptions} />
    </div>
  );
}
