/**
 * InsiEDR Executive KPI Metric Grid
 * ==================================
 *
 * Architectural Role:
 *   High-level executive telemetry summary rendering 7 critical SOC metrics:
 *   1. Total Fleet PCs (Online / Offline endpoint breakdown)
 *   2. Critical Risk count (Urgent threshold >= 85.0)
 *   3. High Risk Users count (Threshold 60.0 - 84.9)
 *   4. Medium Risk count (Threshold 35.0 - 59.9)
 *   5. Low / Baseline count (Nominal < 35.0)
 *   6. Total Risk Events Logged (Aggregate database events)
 *   7. Model Pipeline Status (Dual-phase RVFL + XGBoost engine readiness)
 *
 * Interactivity:
 *   Risk level cards are clickable, triggering drilldown filtering on the fleet table.
 */

import React from 'react';
import type { DashboardSummary, SystemHealth } from '../../types/telemetry';
import { ShieldAlert, ShieldCheck, Monitor, AlertTriangle, Activity, Cpu } from 'lucide-react';

export interface KpiGridProps {
  summary: DashboardSummary | null;
  health: SystemHealth | null;
  onFilterLevel?: (level: string) => void;
}

export const KpiGrid: React.FC<KpiGridProps> = ({ summary, health, onFilterLevel }) => {
  const pc = summary?.pc_status || { total_pcs: 0, online_pcs: 0, offline_pcs: 0 };
  const rc = summary?.risk_counts || { critical: 0, high: 0, medium: 0, low: 0 };
  const totalEvents = summary?.total_risk_events || summary?.stats?.risk_events || 0;
  const modelStatus = health?.model_pipeline || 'ready';

  const kpis = [
    {
      label: 'Total Fleet PCs',
      value: pc.total_pcs,
      icon: <Monitor className="w-4 h-4 text-slate-500" />,
      sub: `${pc.online_pcs} online · ${pc.offline_pcs} offline`,
      border: 'border-l-slate-400',
    },
    {
      label: 'Critical Risk',
      value: rc.critical,
      icon: <ShieldAlert className="w-4 h-4 text-rose-600" />,
      sub: 'Immediate action required',
      textColor: rc.critical > 0 ? 'text-rose-700 font-bold' : 'text-slate-900',
      border: 'border-l-rose-500',
      clickable: true,
      filter: 'CRITICAL',
    },
    {
      label: 'High Risk Users',
      value: rc.high,
      icon: <AlertTriangle className="w-4 h-4 text-orange-600" />,
      sub: 'Elevated anomaly score',
      textColor: rc.high > 0 ? 'text-orange-700 font-bold' : 'text-slate-900',
      border: 'border-l-orange-500',
      clickable: true,
      filter: 'HIGH',
    },
    {
      label: 'Medium Risk',
      value: rc.medium,
      icon: <AlertTriangle className="w-4 h-4 text-amber-600" />,
      sub: 'Potential deviation',
      textColor: rc.medium > 0 ? 'text-amber-800' : 'text-slate-900',
      border: 'border-l-amber-400',
      clickable: true,
      filter: 'MEDIUM',
    },
    {
      label: 'Low / Baseline',
      value: rc.low,
      icon: <ShieldCheck className="w-4 h-4 text-emerald-600" />,
      sub: 'Operating within bounds',
      textColor: 'text-emerald-700',
      border: 'border-l-emerald-500',
      clickable: true,
      filter: 'LOW',
    },
    {
      label: 'Risk Events Logged',
      value: totalEvents.toLocaleString(),
      icon: <Activity className="w-4 h-4 text-blue-600" />,
      sub: 'Correlated telemetry',
      border: 'border-l-blue-500',
    },
    {
      label: 'Model Pipeline',
      value: modelStatus.toUpperCase().replace(/_/g, ' '),
      icon: <Cpu className="w-4 h-4 text-indigo-600" />,
      sub: 'Dual-phase RVFL + XGBoost',
      textColor: modelStatus === 'ready' ? 'text-emerald-700' : 'text-amber-700',
      border: 'border-l-indigo-500',
      isText: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3.5">
      {kpis.map((kpi, idx) => (
        <div
          key={idx}
          onClick={() => kpi.clickable && onFilterLevel && onFilterLevel(kpi.filter || '')}
          className={`bg-white rounded-lg border border-slate-200 border-l-4 ${kpi.border} p-3.5 shadow-xs transition-all ${
            kpi.clickable ? 'hover:shadow-sm hover:border-slate-300 cursor-pointer' : ''
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-slate-500 tracking-tight uppercase">
              {kpi.label}
            </span>
            {kpi.icon}
          </div>
          <div className={`text-xl font-bold mt-1.5 tracking-tight ${kpi.textColor || 'text-slate-900'}`}>
            {kpi.value}
          </div>
          <div className="text-[10px] text-slate-400 mt-1 truncate">{kpi.sub}</div>
        </div>
      ))}
    </div>
  );
};
