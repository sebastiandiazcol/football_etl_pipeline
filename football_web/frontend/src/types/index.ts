export interface User {
  id: number;
  email: string;
  full_name?: string;
  role: 'admin' | 'viewer';
  is_active: boolean;
  mfa_enabled: boolean;
}

export interface TeamMatch {
  id: number;
  match_id: number;
  team_id: number;
  opponent_id: number;
  date_key: number;
  goals_for: number;
  goals_against: number;
  match_result: string;
  is_btts: number;
  is_over_2_5: number;
  xg_for: number;
  points: number;
}

export interface DashboardStats {
  total_matches: number;
  total_teams: number;
  btts_percentage: number;
  over25_percentage: number;
  avg_goals_per_match: number;
}

export interface PipelineRun {
  id: string;
  team_id: number;
  max_matches: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  finished_at?: string;
  error?: string;
  triggered_by?: string;
}

export interface PlayerStat {
  player_id: number;
  total_xg: number;
  total_shots: number;
  total_goals: number;
  matches_played: number;
}

export interface Team {
  team_id: number;
  team_name: string;
}
