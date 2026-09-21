/**
 * InsiEDR Plugin Development Reference Template
 * =============================================
 *
 * HOW TO BUILD AND REGISTER A NEW PLUGIN FOR THE TEAM:
 *
 * 1. Duplicate this directory or file into `src/plugins/<your-plugin-name>/`.
 * 2. Define your component below, utilizing `context` for shared telemetry.
 * 3. Register your plugin in `src/plugins/index.ts`:
 *
 *    ```ts
 *    import { MyNewPlugin } from './my-new-plugin/MyNewPlugin';
 *    import { Shield } from 'lucide-react';
 *
 *    pluginRegistry.register({
 *      id: 'my-new-plugin',
 *      name: 'Network Forensics',
 *      description: 'Deep-packet inspection and connection flow graphs',
 *      icon: Shield,
 *      component: MyNewPlugin,
 *      category: 'investigation',
 *      order: 3,
 *      badge: (ctx) => ctx.summary?.stats?.anomalies || undefined,
 *    });
 *    ```
 *
 * 4. Run `npm run build` to verify type safety. Your plugin will automatically appear
 *    in the top navigation bar with full access to live SSE telemetry!
 */

import React from 'react';
import type { PluginProps } from '../registry';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Terminal, Shield, RefreshCw } from 'lucide-react';

export const PluginTemplate: React.FC<PluginProps> = ({ context }) => {
  const { summary, isConnected, onOpenDrillDown, onRefresh } = context;

  return (
    <div className="space-y-5">
      {/* Plugin Header Card */}
      <Card
        title="Custom Plugin Title"
        subtitle="Operational purpose and active telemetry scope"
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Sync Telemetry
          </Button>
        }
      >
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-blue-600" />
            <span className="font-semibold text-slate-800">Connection Status:</span>
            <span className={isConnected ? 'text-emerald-600 font-semibold' : 'text-amber-600'}>
              {isConnected ? 'Real-Time SSE Connected' : 'Fallback Polling Active'}
            </span>
          </div>
          <div>
            <span className="text-slate-500">Monitored Fleet Hosts:</span>{' '}
            <span className="font-mono font-bold text-slate-900">
              {summary?.pc_status?.total_pcs || 0}
            </span>
          </div>
        </div>
      </Card>

      {/* Main Investigation Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="Module View 1" subtitle="Contextual data stream">
          <div className="text-xs text-slate-600 p-4">
            Render your custom visualizations, graphs, or data tables here.
          </div>
        </Card>

        <Card title="Module View 2" subtitle="Target action triggers">
          <div className="p-4 space-y-3">
            <p className="text-xs text-slate-600">
              Trigger deep-dive identity forensics by calling the shared action:
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={<Terminal className="w-3.5 h-3.5" />}
              onClick={() => onOpenDrillDown && onOpenDrillDown('example_user')}
            >
              Test Identity Investigation
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
