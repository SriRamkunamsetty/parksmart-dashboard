import { useEffect, useState } from 'react';
import { AlertTriangle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CountdownTimerProps {
  expiryTime: Date;
  onExpire?: () => void;
}

export function CountdownTimer({ expiryTime, onExpire }: CountdownTimerProps) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    const update = () => {
      const diff = expiryTime.getTime() - Date.now();
      setRemaining(Math.max(0, diff));
      if (diff <= 0) onExpire?.();
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [expiryTime, onExpire]);

  const minutes = Math.floor(remaining / 60000);
  const seconds = Math.floor((remaining % 60000) / 1000);
  const isWarning = remaining > 0 && remaining < 3 * 60 * 1000; // < 3 min
  const isExpired = remaining === 0;
  const progress = Math.min(100, (remaining / (15 * 60 * 1000)) * 100);

  if (isExpired) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-destructive/10 text-destructive text-sm font-semibold">
        <AlertTriangle className="w-4 h-4" />
        Booking Expired
      </div>
    );
  }

  return (
    <div className={cn(
      'rounded-xl border p-4 space-y-3 transition-all',
      isWarning ? 'border-orange-400 bg-orange-50 animate-pulse-warn' : 'border-border bg-card'
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <Clock className={cn('w-4 h-4', isWarning ? 'text-orange-500' : 'text-primary')} />
          Time Remaining
        </div>
        {isWarning && (
          <span className="flex items-center gap-1 text-xs font-semibold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full">
            <AlertTriangle className="w-3 h-3" /> Expiring soon
          </span>
        )}
      </div>

      <div className={cn(
        'text-3xl font-display font-bold tabular-nums',
        isWarning ? 'text-orange-600' : 'text-foreground'
      )}>
        {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-1000',
            isWarning ? 'bg-orange-500' : 'bg-primary'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
