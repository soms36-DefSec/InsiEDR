import React, { useState, useEffect } from 'react';
import { TopNavbar } from './TopNavbar';
import { pluginRegistry } from '../../plugins/registry';
import type { EDRPlugin, PluginContextData } from '../../plugins/registry';
import { useRealTimeStream } from '../../hooks/useRealTimeStream';
import { exportFleetRiskCSV } from '../../services/api';
import type { EndpointRow, RiskEvent } from '../../types/telemetry';
import { getRiskLevel } from '../../utils/formatters';

export const AppLayout: React.FC = () => {
  const [plugins, setPlugins] = useState<EDRPlugin[]>(() => pluginRegistry.getAll());
  const [activePluginId, setActivePluginId] = useState('soc-matrix');

  const {
    summary,
    health,
    logs,
    connectionMode,
    autoRefresh,
    toggleAutoRefresh,
    refreshAll,
  } = useRealTimeStream();

  useEffect(() => {
    return pluginRegistry.subscribe(() => {
      setPlugins(pluginRegistry.getAll());
    });
  }, []);

  const activePlugin = plugins.find((p) => p.id === activePluginId) || plugins[0];

  const handleSelectCollector = () => {
    setActivePluginId('telemetry-explorer');
  };

  const handleExportCSV = () => {
    if (!summary?.agents) return;
    const now = Date.now();
    const latestRiskMap: Record<string, RiskEvent> = {};
    (summary.risk_events || []).forEach((ev) => {
      if (ev.username && !latestRiskMap[ev.username]) latestRiskMap[ev.username] = ev;
    });

    const rows: EndpointRow[] = summary.agents.map((agent) => {
      const user = agent.username_last_seen || '—';
      const hostname = agent.hostname || '—';
      const agentId = agent.agent_id || `${hostname}_${user}`;
      const risk = latestRiskMap[user] || latestRiskMap[hostname];
      const score = risk ? parseFloat(String(risk.risk_score || 0)) : 0;
      const isOnline =
        agent.status === 'active' ||
        (agent.last_seen_at && now - new Date(agent.last_seen_at).getTime() < 300000);

      return {
        agentId,
        hostname,
        user,
        score,
        level: getRiskLevel(score),
        isDecayed: false,
        scenarios: [],
        lastSeen: agent.last_seen_at,
        isOnline: Boolean(isOnline),
      };
    });

    exportFleetRiskCSV(rows);
  };

  const contextData: PluginContextData = {
    summary,
    health,
    logs,
    isConnected: connectionMode === 'sse',
    onSelectCollector: handleSelectCollector,
    onNavigatePlugin: (id) => setActivePluginId(id),
  };

  const ActiveComponent = activePlugin?.component;

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 flex flex-col">
      {/* Dark Navy Top Navigation Bar */}
      <TopNavbar
        plugins={plugins}
        activePluginId={activePluginId}
        onSelectPlugin={setActivePluginId}
        context={contextData}
        connectionMode={connectionMode}
        autoRefresh={autoRefresh}
        onToggleAutoRefresh={toggleAutoRefresh}
        onRefresh={refreshAll}
        onExportCSV={handleExportCSV}
      />

      {/* Main Content Canvas */}
      <main className="flex-1 overflow-y-auto px-6 py-5">
        <div className="max-w-[1700px] mx-auto space-y-5">
          {/* View Title & Description */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                {activePlugin?.name || 'SOC Matrix'}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {activePlugin?.description || 'Enterprise threat defense and endpoint intelligence'}
              </p>
            </div>
          </div>

          {/* Active Plugin View Content */}
          {ActiveComponent ? (
            <ActiveComponent context={contextData} />
          ) : (
            <div className="p-8 text-center text-slate-400 text-xs">
              No active security view loaded.
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
