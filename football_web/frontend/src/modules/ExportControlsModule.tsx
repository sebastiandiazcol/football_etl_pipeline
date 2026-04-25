import type { CSSProperties } from 'react';
import api from '../hooks/useApi';
import type { ModuleProps } from './types';

const s: Record<string, CSSProperties> = {
  wrapper: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' },
  btn: { background: '#0ea5e9', border: 'none', borderRadius: '8px', padding: '8px 18px', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' },
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function ExportControlsModule(_props: ModuleProps) {
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

  return (
    <div style={s.wrapper}>
      <button style={s.btn} onClick={() => handleExport('teams')}>⬇ Export Teams CSV</button>
      <button style={s.btn} onClick={() => handleExport('players')}>⬇ Export Players CSV</button>
    </div>
  );
}
