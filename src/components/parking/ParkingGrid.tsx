import { ParkingSlot } from '@/types/parking';
import { Car, CheckCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ParkingGridProps {
  slots: ParkingSlot[];
  onSlotSelect?: (slot: ParkingSlot) => void;
  selectedSlotId?: string;
}

const statusConfig = {
  available: {
    label: 'Available',
    icon: CheckCircle,
    className: 'slot-available border-2 cursor-pointer hover:scale-105 hover:shadow-slot',
  },
  reserved: {
    label: 'Reserved',
    icon: Clock,
    className: 'slot-reserved border-2 cursor-not-allowed',
  },
  occupied: {
    label: 'Occupied',
    icon: Car,
    className: 'slot-occupied border-2 cursor-not-allowed',
  },
};

export function ParkingGrid({ slots, onSlotSelect, selectedSlotId }: ParkingGridProps) {
  const floors = [...new Set(slots.map(s => s.floor))];

  return (
    <div className="space-y-6">
      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-sm">
        {Object.entries(statusConfig).map(([status, config]) => (
          <div key={status} className="flex items-center gap-2">
            <div className={cn('w-4 h-4 rounded border-2', `slot-${status}`)} />
            <span className="text-muted-foreground font-medium">{config.label}</span>
          </div>
        ))}
      </div>

      {floors.map(floor => (
        <div key={floor}>
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center font-bold">{floor}</span>
            Floor {floor}
          </h3>
          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2.5">
            {slots
              .filter(s => s.floor === floor)
              .map(slot => {
                const config = statusConfig[slot.status];
                const Icon = config.icon;
                const isSelected = selectedSlotId === slot.id;

                return (
                  <button
                    key={slot.id}
                    type="button"
                    onClick={() => slot.status === 'available' && onSlotSelect?.(slot)}
                    className={cn(
                      'relative rounded-xl p-2.5 flex flex-col items-center gap-1 transition-all duration-200 select-none',
                      config.className,
                      isSelected && 'ring-2 ring-primary ring-offset-2 scale-105 shadow-slot'
                    )}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-xs font-bold leading-none">{slot.number}</span>
                    {isSelected && (
                      <span className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 bg-primary rounded-full border-2 border-background" />
                    )}
                  </button>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}
