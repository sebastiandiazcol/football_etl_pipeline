import { useState, useEffect, useCallback, type CSSProperties, type FormEvent } from 'react';
import api from '../hooks/useApi';
import { PipelineRun } from '../types';

const s: Record<string, CSSProperties> = {
  container: { background: '#1e293b', borderRadius: '12px', padding: '1.5rem', marginTop: '2rem' },
  title: { color: '#38bdf8', fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' },
  form: { display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' as const },
  fieldGroup: { display: 'flex', flexDirection: 'column' as const, gap: '0.25rem' },
  label: { color: '#94a3b8', fontSize: '0.8rem' },
  input: {
    background: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '6px',
    padding: '8px 12px',
    color: '#e2e8f0',
    width: '120px',
  },
  btn: {
    background: '#0ea5e9',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 20px',
    color: '#fff',
    fontWeight: 600,
    cursor: 'pointer',
  },
  table: { width: '100%', borderCollapse: 'collapse' as const, marginTop: '1.5rem', fontSize: '0.85rem' },
  th: { color: '#64748b', padding: '8px 12px', textAlign: 'left' as const, borderBottom: '1px solid #334155' },
  td: { color: '#cbd5e1', padding: '8px 12px', borderBottom: '1px solid #1e293b' },
};

const statusColor: Record<string, string> = {
  pending: '#fbbf24',
  running: '#38bdf8',
  completed: '#4ade80',
  failed: '#f87171',
};

export default function PipelineRunner() {
  const [teamId, setTeamId] = useState('');
  const [maxMatches, setMaxMatches] = useState('10');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [runs, setRuns] = useState<PipelineRun[]>([]);

  const fetchRuns = useCallback(async () => {
    try {
      const { data } = await api.get<PipelineRun[]>('/api/pipeline/runs');
      setRuns(data);
    } catch {
      // Silently ignore
    }
  }, []);

  useEffect(() => {
    fetchRuns();
    const interval = setInterval(fetchRuns, 5000);
    return () => clearInterval(interval);
  }, [fetchRuns]);

  const handleRun = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (!teamId) {
      setError('Team ID is required');
      return;
    }
    setLoading(true);
    try {
      await api.post('/api/pipeline/run', {
        team_id: parseInt(teamId),
        max_matches: parseInt(maxMatches) || 10,
      });
      await fetchRuns();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start pipeline';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={s.container}>
      <div style={s.title}>⚙️ Pipeline Runner</div>
      <form style={s.form} onSubmit={handleRun}>
        <div style={s.fieldGroup}>
          <label style={s.label}>Team ID</label>
          <input
            style={s.input}
            type="number"
            value={teamId}
            onChange={(e) => setTeamId(e.target.value)}
            placeholder="e.g. 42"
          />
        </div>
        <div style={s.fieldGroup}>
          <label style={s.label}>Max Matches</label>
          <input
            style={s.input}
            type="number"
            value={maxMatches}
            onChange={(e) => setMaxMatches(e.target.value)}
            min="1"
            max="100"
          />
        </div>
        <button style={s.btn} type="submit" disabled={loading}>
          {loading ? 'Starting…' : '▶ Run ETL'}
        </button>
      </form>
      {error && <div style={{ color: '#f87171', marginTop: '0.5rem', fontSize: '0.85rem' }}>{error}</div>}

      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Run ID</th>
            <th style={s.th}>Team</th>
            <th style={s.th}>Matches</th>
            <th style={s.th}>Status</th>
            <th style={s.th}>Started</th>
            <th style={s.th}>Finished</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td style={s.td}>{run.id.substring(0, 8)}…</td>
              <td style={s.td}>{run.team_id}</td>
              <td style={s.td}>{run.max_matches}</td>
              <td style={{ ...s.td, color: statusColor[run.status] ?? '#94a3b8', fontWeight: 600 }}>
                {run.status}
              </td>
              <td style={s.td}>{new Date(run.started_at).toLocaleString()}</td>
              <td style={s.td}>{run.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}</td>
            </tr>
          ))}
          {runs.length === 0 && (
            <tr>
              <td colSpan={6} style={{ ...s.td, textAlign: 'center', color: '#475569' }}>
                No pipeline runs yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
