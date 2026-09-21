/**
 * InsiEDR Plugin Bootstrapper
 * ===========================
 *
 * Architectural Role:
 *   Central registry bootstrapper called during application startup (`src/main.tsx`).
 *   Registers all available security plugins in their configured display order.
 *
 * To Add a New Plugin:
 *   1. Import your plugin component.
 *   2. Call `pluginRegistry.register({...})` with a unique ID, icon, category, and order.
 */

import { pluginRegistry } from './registry';
import { SocMatrixPlugin } from './soc-matrix/SocMatrixPlugin';
import { TelemetryExplorerPlugin } from './telemetry-explorer/TelemetryExplorerPlugin';
import { ShieldAlert, Terminal } from 'lucide-react';

export function initializePlugins(): void {
  // 1. SOC Matrix Plugin: Primary operational posture and machine learning telemetry
  pluginRegistry.register({
    id: 'soc-matrix',
    name: 'SOC Matrix',
    description: 'Fleet posture, live threat feed, and behavioral machine learning',
    icon: ShieldAlert,
    component: SocMatrixPlugin,
    category: 'monitoring',
    badge: (ctx) => {
      const crit = ctx.summary?.risk_counts.critical || 0;
      return crit > 0 ? crit : undefined;
    },
    order: 1,
  });

  // 2. Telemetry Explorer Plugin: Raw event stream forensics and virtualized payload inspection
  pluginRegistry.register({
    id: 'telemetry-explorer',
    name: 'Telemetry Explorer',
    description: 'Raw event stream, payload inspector, and virtualized log analysis',
    icon: Terminal,
    component: TelemetryExplorerPlugin,
    category: 'investigation',
    order: 2,
  });
}

export * from './registry';
