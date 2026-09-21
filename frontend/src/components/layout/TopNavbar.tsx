import React, { useState } from 'react';
import type { EDRPlugin, PluginContextData } from '../../plugins/registry';
import { Button } from '../ui/Button';
import { RefreshCw, Download, Cpu, Monitor, ChevronDown, FileSpreadsheet, FileCode, ShieldAlert } from 'lucide-react';
import { triggerServerExport } from '../../services/api';

export interface TopNavbarProps {
  plugins: EDRPlugin[];
  activePluginId: string;
  onSelectPlugin: (id: string) => void;
  context: PluginContextData;
  connectionMode: 'sse' | 'polling' | 'disconnected';
  autoRefresh: boolean;
  onToggleAutoRefresh: () => void;
  onRefresh: () => Promise<void>;
  onExportCSV: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  plugins,
  activePluginId,
  onSelectPlugin,
  context,
  connectionMode,
  autoRefresh,
  onToggleAutoRefresh,
  onRefresh,
  onExportCSV,
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const summary = context.summary;
  const health = context.health;
  const pcStatus = summary?.pc_status;
  const modelPipeline = health?.model_pipeline || 'ready';

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setTimeout(() => setIsRefreshing(false), 400);
    }
  };

  return (
    <nav className="bg-[#0b1329] text-slate-200 border-b border-slate-800 sticky top-0 z-40 select-none shadow-sm">
      <div className="max-w-[1700px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand & Logo */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold text-sm tracking-tight shadow-sm shadow-blue-500/30">
            IE
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-white tracking-tight">InsiEDR</span>
            </div>
            <div className="text-[10px] text-slate-400 font-medium tracking-wide leading-none mt-0.5">
              Insider Threat Detection
            </div>
          </div>
        </div>

        {/* Navigation Tabs in Top Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1">
          {plugins.map((plugin) => {
            const isActive = plugin.id === activePluginId;
            const Icon = plugin.icon;
            const badgeVal = plugin.badge ? plugin.badge(context) : null;

            return (
              <button
                key={plugin.id}
                onClick={() => onSelectPlugin(plugin.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'bg-slate-800 text-white shadow-xs border border-slate-700/60'
                    : 'text-slate-300 hover:bg-slate-800/60 hover:text-white border border-transparent'
                }`}
              >
                <Icon
                  className={`w-3.5 h-3.5 ${isActive ? 'text-blue-400' : 'text-slate-400'}`}
                />
                <span>{plugin.name}</span>
                {badgeVal !== null && badgeVal !== undefined && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                      typeof badgeVal === 'number' && badgeVal > 0
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {badgeVal}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Right Section: Fleet Status & Action Controls */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Fleet Status Pill */}
          <div className="hidden lg:flex items-center gap-2.5 px-3 py-1.5 rounded-md bg-slate-900/90 border border-slate-800 text-xs">
            <div className="flex items-center gap-1.5 text-slate-300" title="Fleet PCs Online / Total">
              <Monitor className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-semibold text-emerald-400">
                {pcStatus ? pcStatus.online_pcs : '—'}
              </span>
              <span className="text-slate-500">/</span>
              <span className="text-slate-400">{pcStatus ? pcStatus.total_pcs : '—'}</span>
            </div>

            <span className="w-px h-3.5 bg-slate-800" />

            <div className="flex items-center gap-1.5 text-slate-300" title="Model Inference Pipeline">
              <Cpu className="w-3.5 h-3.5 text-blue-400" />
              <span
                className={`font-semibold uppercase text-[10px] ${
                  modelPipeline === 'ready' ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {modelPipeline}
              </span>
            </div>
          </div>

          {/* Real-time Stream Status */}
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md border border-slate-800 bg-slate-900/90 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                connectionMode === 'sse'
                  ? 'bg-emerald-400 animate-pulse-subtle'
                  : connectionMode === 'polling'
                  ? 'bg-amber-400'
                  : 'bg-slate-500'
              }`}
            />
            <span className="text-slate-300 text-[11px] font-medium hidden sm:inline">
              {connectionMode === 'sse'
                ? 'Stream Active'
                : autoRefresh
                ? 'Polling 3s'
                : 'Paused'}
            </span>
            <button
              onClick={onToggleAutoRefresh}
              className="text-[10px] font-bold text-blue-400 hover:text-blue-300 cursor-pointer"
            >
              {autoRefresh ? 'Pause' : 'Resume'}
            </button>
          </div>

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-md bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>


          {/* Export Dropdown */}
          <div className="relative">
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowExportMenu((prev) => !prev)}
              icon={<Download className="w-3.5 h-3.5 text-white" />}
              className="bg-blue-600 hover:bg-blue-500 border-blue-600 text-white font-semibold flex items-center gap-1.5"
            >
              <span>Export</span>
              <ChevronDown className="w-3 h-3 text-blue-200" />
            </Button>

            {showExportMenu && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowExportMenu(false)}
                />
                <div className="absolute right-0 mt-2 w-60 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50 py-1.5 text-xs">
                  <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Quick Exports
                  </div>
                  <button
                    onClick={() => {
                      onExportCSV();
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                    <span>Fleet Risk Summary (CSV)</span>
                  </button>

                  <div className="my-1 border-t border-slate-800" />
                  <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Server Streaming Exports
                  </div>
                  <button
                    onClick={() => {
                      triggerServerExport('logs', 'csv');
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Stream All Logs (CSV)</span>
                  </button>
                  <button
                    onClick={() => {
                      triggerServerExport('threats', 'csv');
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <ShieldAlert className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                    <span>Stream Threat Detections (CSV)</span>
                  </button>
                  <button
                    onClick={() => {
                      triggerServerExport('logs', 'json');
                      setShowExportMenu(false);
                    }}
                    className="w-full text-left px-3 py-2 text-slate-200 hover:bg-slate-800 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <FileCode className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span>Stream Logs (NDJSON)</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};
