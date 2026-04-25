/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║               REGISTRO DE MÓDULOS DEL DASHBOARD             ║
 * ╠══════════════════════════════════════════════════════════════╣
 * ║  Para agregar un nuevo módulo:                               ║
 * ║  1. Crea tu archivo en src/modules/MiNuevoModulo.tsx         ║
 * ║     - Exporta un componente que reciba `ModuleProps`         ║
 * ║  2. Importa tu módulo aquí (líneas de import de abajo)       ║
 * ║  3. Añade un objeto { id, component } al array que quieras   ║
 * ║     - dashboardModules  → aparece en /dashboard              ║
 * ║     - analyticsModules  → aparece en /analytics              ║
 * ║  4. ¡Listo! No hace falta tocar ningún otro archivo.         ║
 * ╚══════════════════════════════════════════════════════════════╝
 */

import type { ModuleDefinition } from './types';

// ─── Importa tus módulos aquí ────────────────────────────────────
import StatsCardsModule from './StatsCardsModule';
import GoalsBarChartModule from './GoalsBarChartModule';
import GoalsTrendModule from './GoalsTrendModule';
import RecentMatchesModule from './RecentMatchesModule';
import PipelineRunnerModule from './PipelineRunnerModule';

import TeamPerformanceModule from './TeamPerformanceModule';
import ExportControlsModule from './ExportControlsModule';
import TopPlayersModule from './TopPlayersModule';
// ─────────────────────────────────────────────────────────────────

/**
 * Módulos que aparecen en la página /dashboard.
 * El orden de la lista es el orden de renderizado.
 */
export const dashboardModules: ModuleDefinition[] = [
  { id: 'stats-cards',     component: StatsCardsModule },
  { id: 'goals-bar-chart', component: GoalsBarChartModule },
  { id: 'goals-trend',     component: GoalsTrendModule },
  { id: 'recent-matches',  component: RecentMatchesModule },
  // Solo visible para admins:
  { id: 'pipeline-runner', component: PipelineRunnerModule, requiredRole: 'admin' },
];

/**
 * Módulos que aparecen en la página /analytics.
 * El orden de la lista es el orden de renderizado.
 */
export const analyticsModules: ModuleDefinition[] = [
  { id: 'team-performance', component: TeamPerformanceModule },
  { id: 'export-controls',  component: ExportControlsModule },
  { id: 'top-players',      component: TopPlayersModule },
];
