/**
 * InsiEDR Real-Time Telemetry & SSE Streaming Hook
 * =================================================
 *
 * Architectural Role:
 *   Serves as the reactive pulse of the entire frontend application. Manages
 *   dual-channel Server-Sent Events (SSE) connections to the FastAPI ASGI server:
 *     1. `/api/v1/stream/threats`: Pushes real-time correlated threat detections.
 *     2. `/api/v1/stream/agents`: Pushes endpoint status & registration changes.
 *
 * Resilience & Adaptive Polling (Self-Healing Architecture):
 *   - Primary Mode (SSE): Real-time server push. When active, background polling is
 *     throttled to a gentle 30-second cadence to reduce unnecessary network load.
 *   - Fallback Mode (Polling): If SSE fails (e.g. proxy blocks event-stream, offline),
 *     automatically falls back to 3-second responsive polling until SSE reconnects.
 *   - Keepalive Compatibility: Backend emits `: ping <timestamp>\n\n` comments every
 *     15 seconds; the browser EventSource parser ignores comments natively while
 *     keeping the TCP socket alive through intermediate firewalls.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { DashboardSummary, SystemHealth, RiskEvent, TelemetryLog } from '../types/telemetry';
import { fetchDashboardSummary, fetchHealth, fetchTelemetry } from '../services/api';

export interface UseRealTimeStreamReturn {
  /** Complete fleet telemetry overview and risk severity counts */
  summary: DashboardSummary | null;
  /** Backend pipeline health: database, ML models, task queue depth */
  health: SystemHealth | null;
  /** Recent raw telemetry logs for the telemetry explorer */
  logs: TelemetryLog[];
  /** Ephemeral list of live threat alerts received via SSE */
  liveThreats: RiskEvent[];
  /** True when SSE connection is actively open and receiving events */
  isConnected: boolean;
  /** Active transmission mode: 'sse' (real-time push), 'polling' (fallback), or 'disconnected' */
  connectionMode: 'sse' | 'polling' | 'disconnected';
  /** Timestamp of the most recent successful data refresh */
  lastUpdated: Date | null;
  /** True during initial telemetry fetch */
  isLoading: boolean;
  /** Error message if telemetry retrieval failed */
  error: string | null;
  /** True if periodic background synchronization is enabled */
  autoRefresh: boolean;
  /** Toggles background synchronization on or off */
  toggleAutoRefresh: () => void;
  /** Manually triggers an immediate full refresh of all telemetry and health */
  refreshAll: () => Promise<void>;
  /** Refreshes raw logs with optional domain and username filters */
  refreshLogs: (collector?: string | null, username?: string | null) => Promise<void>;
}

export function useRealTimeStream(): UseRealTimeStreamReturn {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [logs, setLogs] = useState<TelemetryLog[]>([]);
  const [liveThreats, setLiveThreats] = useState<RiskEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionMode, setConnectionMode] = useState<'sse' | 'polling' | 'disconnected'>('polling');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const threatEventSourceRef = useRef<EventSource | null>(null);
  const agentEventSourceRef = useRef<EventSource | null>(null);
  const pollingTimerRef = useRef<number | null>(null);

  /**
   * Refetches full dashboard state and backend health concurrently.
   * Silently catches non-fatal health errors so UI remains operational even if ML is cold.
   */
  const refreshAll = useCallback(async () => {
    try {
      setError(null);
      const [summaryRes, healthRes] = await Promise.all([
        fetchDashboardSummary(),
        fetchHealth().catch(() => ({ status: 'unknown', model_pipeline: 'ready' })),
      ]);
      setSummary(summaryRes);
      setHealth(healthRes);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('[InsiEDR Telemetry] Sync failed:', err);
      setError(err instanceof Error ? err.message : 'Telemetry sync failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Refetches raw telemetry log events for the Telemetry Explorer view.
   */
  const refreshLogs = useCallback(async (collector?: string | null, username?: string | null) => {
    try {
      const res = await fetchTelemetry(50, 0, collector, username);
      if (res.ok && res.logs) {
        setLogs(res.logs);
      }
    } catch (err) {
      console.error('[InsiEDR Telemetry] Log sync failed:', err);
    }
  }, []);

  const toggleAutoRefresh = useCallback(() => {
    setAutoRefresh((prev) => !prev);
  }, []);

  /**
   * SSE Stream Lifecycle:
   * Establishes persistent EventSource listeners on `/api/v1/stream/threats`
   * and `/api/v1/stream/agents`. Cleans up connections on unmount.
   */
  useEffect(() => {
    try {
      // 1. Threats Channel: Correlated risk events & rule violations
      const threatsEs = new EventSource('/api/v1/stream/threats');
      threatEventSourceRef.current = threatsEs;

      threatsEs.onopen = () => {
        setIsConnected(true);
        setConnectionMode('sse');
      };

      threatsEs.addEventListener('threat_alert', (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data);
          const newAlert: RiskEvent = {
            username: payload.username || 'unknown',
            hostname: payload.hostname,
            risk_score: payload.risk_score || 0,
            summary: payload.summary,
            correlated_signals_json: payload.correlated_signals_json || payload,
            created_at: new Date().toISOString(),
          };
          setLiveThreats((prev) => [newAlert, ...prev.slice(0, 49)]);
          refreshAll();
        } catch (err) {
          console.error('[InsiEDR SSE] Failed to parse threat alert payload:', err);
        }
      });

      threatsEs.onerror = () => {
        setIsConnected(false);
        setConnectionMode('polling');
      };

      // 2. Agents Channel: Endpoint heartbeat and status changes
      const agentsEs = new EventSource('/api/v1/stream/agents');
      agentEventSourceRef.current = agentsEs;

      agentsEs.addEventListener('agent_status', () => {
        refreshAll();
      });

      agentsEs.onerror = () => {
        // Quiet fallback; threats stream error handler handles connectionMode toggle
      };
    } catch {
      setConnectionMode('polling');
    }

    return () => {
      if (threatEventSourceRef.current) {
        threatEventSourceRef.current.close();
        threatEventSourceRef.current = null;
      }
      if (agentEventSourceRef.current) {
        agentEventSourceRef.current.close();
        agentEventSourceRef.current = null;
      }
    };
  }, [refreshAll]);

  // Initial load on component mount
  useEffect(() => {
    refreshAll();
    refreshLogs();
  }, [refreshAll, refreshLogs]);

  /**
   * Adaptive Polling Loop:
   * - Fallback Mode ('polling'): Polls every 3,000ms for responsive updates when SSE is down.
   * - Active SSE Mode ('sse'): Relaxes to 30,000ms safety sync, eliminating server request flooding.
   */
  useEffect(() => {
    if (!autoRefresh) {
      if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);
      return;
    }

    const pollIntervalMs = connectionMode === 'sse' ? 30000 : 3000;

    pollingTimerRef.current = window.setInterval(() => {
      refreshAll();
    }, pollIntervalMs);

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [autoRefresh, connectionMode, refreshAll]);

  return {
    summary,
    health,
    logs,
    liveThreats,
    isConnected,
    connectionMode,
    lastUpdated,
    isLoading,
    error,
    autoRefresh,
    toggleAutoRefresh,
    refreshAll,
    refreshLogs,
  };
}
