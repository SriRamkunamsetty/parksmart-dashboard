import { cn } from '@/lib/utils';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { ApiStatus } from '@/hooks/useSlotPolling';

interface Props {
  status: ApiStatus;
  lastUpdated: Date | null;
}

export function ApiStatusBadge({ status, lastUpdated }: Props) {
  return (
    <div className="flex items-center gap-2">
      {status === 'live' && (
        <span className="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-100 border border-green-300 px-2.5 py-1 rounded-full">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-600" />
          </span>
          <Wifi className="w-3 h-3" />
          LIVE · {lastUpdated?.toLocaleTimeString()}
        </span>
      )}
      {status === 'offline' && (
        <span className="flex items-center gap-1.5 text-xs font-semibold text-yellow-700 bg-yellow-100 border border-yellow-300 px-2.5 py-1 rounded-full">
          <WifiOff className="w-3 h-3" />
          API Offline · Mock Data
        </span>
      )}
      {status === 'connecting' && (
        <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground bg-muted border border-border px-2.5 py-1 rounded-full">
          <Loader2 className="w-3 h-3 animate-spin" />
          Connecting…
        </span>
      )}
    </div>
  );
}
