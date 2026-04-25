import type { CSSProperties } from 'react';
import type { ModuleProps } from './types';

const s: Record<string, CSSProperties> = {
  card: { background: '#1e293b', borderRadius: '12px', padding: '1.25rem', marginBottom: '2rem' },
  title: { color: '#94a3b8', fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' },
  th: { color: '#64748b', padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #334155' },
  td: { color: '#cbd5e1', padding: '8px 12px', borderBottom: '1px solid #1e293b' },
};

const resultColor: Record<string, string> = { W: '#4ade80', D: '#fbbf24', L: '#f87171' };

export default function RecentMatchesModule({ matches }: ModuleProps) {
  return (
    <div style={s.card}>
      <div style={s.title}>Recent Matches</div>
      <div style={{ overflowX: 'auto' }}>
        <table style={s.table as React.CSSProperties}>
          <thead>
            <tr>
              <th style={s.th as React.CSSProperties}>Date</th>
              <th style={s.th as React.CSSProperties}>Team</th>
              <th style={s.th as React.CSSProperties}>Opponent</th>
              <th style={s.th as React.CSSProperties}>GF</th>
              <th style={s.th as React.CSSProperties}>GA</th>
              <th style={s.th as React.CSSProperties}>Result</th>
              <th style={s.th as React.CSSProperties}>xG</th>
              <th style={s.th as React.CSSProperties}>Pts</th>
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
  );
}
