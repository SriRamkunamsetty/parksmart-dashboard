import { useEffect, useRef, useState } from 'react';
import { ParkingSlot } from '@/types/parking';

const FALLBACK_SLOTS: ParkingSlot[] = [
  { id: '1', number: 'A-01', floor: 'A', status: 'available' },
  { id: '2', number: 'A-02', floor: 'A', status: 'occupied' },
  { id: '3', number: 'A-03', floor: 'A', status: 'available' },
  { id: '4', number: 'A-04', floor: 'A', status: 'reserved' },
];

export type ApiStatus = 'connecting' | 'live' | 'offline';

/**
 * Polls GET /slots every 5 seconds.
 * Falls back gracefully to mock data if the endpoint is unreachable.
 * The API is expected to return: Array<{ id: string; slot: string; status: 'available'|'reserved'|'occupied' }>
 */
export function useSlotPolling(
  onSlotsUpdate: (slots: ParkingSlot[]) => void
): { apiStatus: ApiStatus; lastUpdated: Date | null } {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('connecting');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const hasConnectedOnce = useRef(false);

  useEffect(() => {
    let mounted = true;

    const fetchSlots = async () => {
      try {
        const res = await fetch('/slots', { signal: AbortSignal.timeout(4000) });
        if (!res.ok) throw new Error('non-200');
        const data: Array<{ id: string; slot?: string; number?: string; floor?: string; status: ParkingSlot['status'] }> = await res.json();

        if (!mounted) return;

        // Normalise API response → ParkingSlot
        const slots: ParkingSlot[] = data.map((d, i) => ({
          id: d.id ?? String(i + 1),
          number: d.number ?? d.slot ?? `S-${String(i + 1).padStart(2, '0')}`,
          floor: d.floor ?? (i < 8 ? 'A' : i < 16 ? 'B' : 'C'),
          status: d.status,
        }));

        onSlotsUpdate(slots);
        setApiStatus('live');
        setLastUpdated(new Date());
        hasConnectedOnce.current = true;
      } catch {
        if (!mounted) return;
        // Only switch to offline after first failed attempt on an initial connect attempt
        setApiStatus(hasConnectedOnce.current ? 'offline' : 'offline');
        if (!hasConnectedOnce.current) {
          // Use store's existing mock slots — don't override with tiny fallback
          hasConnectedOnce.current = true;
        }
      }
    };

    fetchSlots();
    const interval = setInterval(fetchSlots, 5000);
    return () => { mounted = false; clearInterval(interval); };
  }, [onSlotsUpdate]);

  return { apiStatus, lastUpdated };
}
