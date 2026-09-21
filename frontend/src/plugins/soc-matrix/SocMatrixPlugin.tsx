/**
 * InsiEDR SOC Matrix Plugin
 * =========================
 *
 * Architectural Role:
 *   Primary operational dashboard module. Synthesizes endpoint fleet posture,
 *   live threat telemetry, heuristic domain scores, and behavioral machine learning.
 *
 * Visual Layout Hierarchy:
 *   1. KpiGrid: Fleet host counts, critical/high/medium risk counts, and ML pipeline health.
 *   2. Main Grid:
 *      - Left: Live Threat Feed (ephemeral detections & CERT scenario violations).
 *      - Right: Attack Surface Breakdown & Chronological Risk Timeline charts.
 *   3. UserRiskTable: Deduplicated endpoint fleet matrix with scenario badges and 30-min decay.
 *   4. DrillDownDrawer: Deep-dive behavioral assessment for selected user/endpoint.
 */

import React, { useState } from 'react';
import type { PluginProps } from '../registry';
import { KpiGrid } from '../../components/soc/KpiGrid';
import { ThreatFeed } from '../../components/soc/ThreatFeed';
import { ChartsSection } from '../../components/soc/ChartsSection';
import { UserRiskTable } from '../../components/soc/UserRiskTable';
import { DrillDownDrawer } from '../../components/soc/DrillDownDrawer';
import { Card } from '../../components/ui/Card';
import { Download } from 'lucide-react';
import { triggerServerExport } from '../../services/api';

export const SocMatrixPlugin: React.FC<PluginProps> = ({ context }) => {
  const { summary, health, onOpenDrillDown } = context;
  const [drillUser, setDrillUser] = useState<string | null>(null);
  const [drillHostname, setDrillHostname] = useState<string | null>(null);

  /**
   * Opens the deep behavioral assessment drawer for an endpoint identity.
   * Also cascades to the optional root context handler.
   */
  const handleSelectEndpoint = (user: string, host?: string) => {
    setDrillUser(user);
    setDrillHostname(host || null);
    if (onOpenDrillDown) onOpenDrillDown(user, host);
  };

  const handleCloseDrillDown = () => {
    setDrillUser(null);
    setDrillHostname(null);
  };

  return (
    <div className="space-y-5">
      {/* KPI Cards Grid */}
      <KpiGrid summary={summary} health={health} />

      {/* Main Grid: Threat Feed (Left) & Charts (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Real-time Live Threat Feed */}
        <div className="lg:col-span-1">
          <Card
            title="Recent Threat Telemetry Feed"
            subtitle="Real-time correlated detections & heuristics"
            action={
              <button
                onClick={() => triggerServerExport('threats', 'csv')}
                className="flex items-center gap-1.5 px-2 py-1 text-[11px] font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 rounded border border-blue-200 transition-colors cursor-pointer"
                title="Stream all threat detections from server to CSV"
              >
                <Download className="w-3 h-3" />
                <span>Export Threats</span>
              </button>
            }
          >
            <ThreatFeed
              events={summary?.risk_events || []}
              onSelectThreat={handleSelectEndpoint}
            />
          </Card>
        </div>

        {/* Security Visualizations */}
        <div className="lg:col-span-2">
          <ChartsSection
            riskCounts={summary?.risk_counts || null}
            riskEvents={summary?.risk_events || []}
          />
        </div>
      </div>

      {/* Endpoint Fleet Risk Table */}
      <UserRiskTable
        agents={summary?.agents || []}
        riskEvents={summary?.risk_events || []}
        selectedUser={drillUser}
        onSelectEndpoint={handleSelectEndpoint}
      />

      {/* Deep-Dive Investigation Drawer */}
      <DrillDownDrawer
        username={drillUser}
        hostname={drillHostname}
        onClose={handleCloseDrillDown}
      />
    </div>
  );
};
