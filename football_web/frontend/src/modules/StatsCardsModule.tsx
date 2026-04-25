import type { CSSProperties } from 'react';
import type { ModuleProps } from './types';

const s: Record<string, CSSProperties> = {
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' },
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.25rem' },
  label: { color: '#64748b', fontSize: '0.8rem', marginBottom: '0.5rem' },
  value: { color: '#38bdf8', fontSize: '1.75rem', fontWeight: 700 },
};

export default function StatsCardsModule({ stats }: ModuleProps) {
  const items = [
    { label: 'Total Matches', value: stats?.total_matches ?? '—' },
    { label: 'Total Teams', value: stats?.total_teams ?? '—' },
    { label: 'BTTS %', value: stats ? `${stats.btts_percentage}%` : '—' },
    { label: 'Over 2.5 %', value: stats ? `${stats.over25_percentage}%` : '—' },
    { label: 'Avg Goals/Match', value: stats?.avg_goals_per_match ?? '—' },
  ];

  return (
    <div style={s.grid}>
      {items.map(({ label, value }) => (
        <div key={label} style={s.card}>
          <div style={s.label}>{label}</div>
          <div style={s.value}>{String(value)}</div>
        </div>
      ))}
    </div>
  );
}
