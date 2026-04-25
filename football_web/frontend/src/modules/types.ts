/**
 * Módulo del Dashboard — tipos compartidos
 *
 * Cada módulo recibe `ModuleProps` con todos los datos disponibles.
 * No necesita hacer sus propias llamadas a la API (salvo excepciones como
 * PipelineRunner que gestiona su propio estado).
 *
 * Para crear un nuevo módulo:
 *   1. Crea `src/modules/MiModulo.tsx` que exporte un componente
 *      `(props: ModuleProps) => JSX.Element`
 *   2. Añade una línea en `src/modules/registry.ts`
 *   ¡Eso es todo!
 */

import { DashboardStats, TeamMatch, Team, PlayerStat, User } from '../types';

export interface ModuleProps {
  // Estadísticas globales
  stats: DashboardStats | null;
  // Partidos recientes
  matches: TeamMatch[];
  // Lista de equipos
  teams: Team[];
  // Estadísticas de jugadores
  players: PlayerStat[];
  // Selector de equipo (usado en Analytics)
  selectedTeamId: string;
  teamStats: TeamMatch[];
  onTeamChange: (teamId: string) => void;
  // Usuario autenticado
  user: User | null;
}

export interface ModuleDefinition {
  /** Identificador único del módulo (slug). */
  id: string;
  /** Componente React que renderiza el módulo. */
  component: React.ComponentType<ModuleProps>;
  /**
   * Si se especifica, solo los usuarios con ese rol verán el módulo.
   * Omitir para que lo vean todos.
   */
  requiredRole?: 'admin' | 'viewer';
}
