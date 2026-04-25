import { useEffect, useState, useCallback, type CSSProperties } from 'react';
import api from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import type { Team, PlayerStat, TeamMatch } from '../types';
import { analyticsModules } from '../modules/registry';
import type { ModuleProps } from '../modules/types';

const s: Record<string, CSSProperties> = {
  page: { minHeight: '100vh', background: '#0f172a', padding: '2rem' },
  title: { color: '#e2e8f0', fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' },
};

export default function Analytics() {
  const { user } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState('');
  const [teamStats, setTeamStats] = useState<TeamMatch[]>([]);
  const [players, setPlayers] = useState<PlayerStat[]>([]);

  useEffect(() => {
    api.get<Team[]>('/api/dashboard/teams').then((r) => setTeams(r.data)).catch(() => {});
    api.get<PlayerStat[]>('/api/analytics/players').then((r) => setPlayers(r.data)).catch(() => {});
  }, []);

  const handleTeamChange = useCallback(async (teamId: string) => {
    setSelectedTeamId(teamId);
    if (!teamId) { setTeamStats([]); return; }
    try {
      const { data } = await api.get<TeamMatch[]>(`/api/analytics/team/${teamId}`);
      setTeamStats(data);
    } catch {
      setTeamStats([]);
    }
  }, []);

  const moduleProps: ModuleProps = {
    stats: null,
    matches: [],
    teams,
    players,
    selectedTeamId,
    teamStats,
    onTeamChange: handleTeamChange,
    user,
  };

  return (
    <div style={s.page}>
      <div style={s.title}>📊 Analytics</div>
      {analyticsModules.map(({ id, component: Module }) => (
        <Module key={id} {...moduleProps} />
      ))}
    </div>
  );
}
