import { useState } from 'react';
import { ParkingSlot } from '@/types/parking';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CheckCircle, Loader2 } from 'lucide-react';

interface BookingFormProps {
  slots: ParkingSlot[];
  selectedSlot?: ParkingSlot | null;
  onSuccess: () => void;
}

export function BookingForm({ slots, selectedSlot, onSuccess }: BookingFormProps) {
  const { bookSlot, currentUser } = useParkingStore();
  const [form, setForm] = useState({
    name: currentUser?.name || '',
    phone: currentUser?.email || '', // Using email placeholder for phone temporarily to fit demo mock
    vehicle_number: '',
    slot_id: selectedSlot?.id || '',
  });
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const availableSlots = slots.filter(s => s.status === 'available');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const slot = slots.find(s => s.id === form.slot_id);
    if (!slot) return;
    setLoading(true);
    const success = await bookSlot(form);
    setLoading(false);
    if (success) {
      setSubmitted(true);
      setTimeout(() => {
        onSuccess();
      }, 1500);
    }
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center animate-bounce">
          <CheckCircle className="w-8 h-8 text-green-600" />
        </div>
        <h3 className="text-xl font-display font-bold text-foreground">Booking Confirmed!</h3>
        <p className="text-muted-foreground text-sm text-center">Your slot has been reserved for 10 minutes.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="name">Customer Name</Label>
        <Input
          id="name"
          placeholder="John Smith"
          value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="phone">Phone Number (Required for History check)</Label>
        <Input
          id="phone"
          placeholder="+1 (555) 000-0000"
          value={form.phone}
          onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="vehicle_number">Vehicle Number</Label>
        <Input
          id="vehicle_number"
          placeholder="ABC-1234"
          value={form.vehicle_number}
          onChange={e => setForm(f => ({ ...f, vehicle_number: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>Parking Slot</Label>
        <Select
          value={form.slot_id}
          onValueChange={v => setForm(f => ({ ...f, slot_id: v }))}
          required
        >
          <SelectTrigger>
            <SelectValue placeholder="Select a slot" />
          </SelectTrigger>
          <SelectContent>
            {availableSlots.map(slot => (
              <SelectItem key={slot.id} value={slot.id}>
                {slot.number} — Floor {slot.floor}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Booking Time</Label>
        <Input value={new Date().toLocaleString()} readOnly className="bg-muted text-muted-foreground" />
      </div>
      <Button
        type="submit"
        className="w-full h-11 font-semibold"
        style={{ background: 'var(--gradient-hero)', border: 'none' }}
        disabled={!form.slot_id || loading}
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Confirm Booking'}
      </Button>
    </form>
  );
}
