/**
 * Módulo Pipeline Runner (solo admin)
 * Envuelve el componente PipelineRunner existente para integrarlo
 * en el sistema de módulos. No necesita datos de ModuleProps.
 */
import PipelineRunner from '../components/PipelineRunner';
import type { ModuleProps } from './types';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function PipelineRunnerModule(_props: ModuleProps) {
  return <PipelineRunner />;
}
