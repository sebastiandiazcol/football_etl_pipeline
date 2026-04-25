import type { CSSProperties } from 'react';
import type { ModuleProps } from './types';

const s: Record<string, CSSProperties> = {
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' },
  title: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' },
  th: { color: '#64748b', padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #334155' },
  td: { color: '#cbd5e1', padding: '8px 12px', borderBottom: '1px solid #1e293b' },
};

export default function TopPlayersModule({ players }: ModuleProps) {
  return (
    <div style={s.card}>
      <div style={s.title}>Top Players by xG</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={s.table as React.CSSProperties}>
          <thead>
            <tr>
              <th style={s.th as React.CSSProperties}>#</th>
              <th style={s.th as React.CSSProperties}>Player ID</th>
              <th style={s.th as React.CSSProperties}>Matches</th>
              <th style={s.th as React.CSSProperties}>Total xG</th>
              <th style={s.th as React.CSSProperties}>Total Shots</th>
              <th style={s.th as React.CSSProperties}>Total Goals</th>
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
                <td colSpan={6} style={{ ...s.td, textAlign: 'center', color: '#475569' }}>
                  No player data available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
