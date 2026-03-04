import { useState } from 'react';
import { ParkingSlot } from '@/types/parking';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CheckCircle } from 'lucide-react';

interface BookingFormProps {
  slots: ParkingSlot[];
  selectedSlot?: ParkingSlot | null;
  onSuccess: () => void;
}

export function BookingForm({ slots, selectedSlot, onSuccess }: BookingFormProps) {
  const { addBooking, currentUser } = useParkingStore();
  const [form, setForm] = useState({
    customerName: currentUser?.name || '',
    phone: '',
    vehicleNumber: '',
    slotId: selectedSlot?.id || '',
  });
  const [submitted, setSubmitted] = useState(false);

  const availableSlots = slots.filter(s => s.status === 'available');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const slot = slots.find(s => s.id === form.slotId);
    if (!slot) return;
    addBooking({
      customerName: form.customerName,
      phone: form.phone,
      vehicleNumber: form.vehicleNumber,
      slotId: slot.id,
      slotNumber: slot.number,
    });
    setSubmitted(true);
    setTimeout(() => {
      onSuccess();
    }, 1500);
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center animate-bounce">
          <CheckCircle className="w-8 h-8 text-green-600" />
        </div>
        <h3 className="text-xl font-display font-bold text-foreground">Booking Confirmed!</h3>
        <p className="text-muted-foreground text-sm text-center">Your slot has been reserved for 15 minutes.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="customerName">Customer Name</Label>
        <Input
          id="customerName"
          placeholder="John Smith"
          value={form.customerName}
          onChange={e => setForm(f => ({ ...f, customerName: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="phone">Phone Number</Label>
        <Input
          id="phone"
          placeholder="+1 (555) 000-0000"
          value={form.phone}
          onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="vehicleNumber">Vehicle Number</Label>
        <Input
          id="vehicleNumber"
          placeholder="ABC-1234"
          value={form.vehicleNumber}
          onChange={e => setForm(f => ({ ...f, vehicleNumber: e.target.value }))}
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>Parking Slot</Label>
        <Select
          value={form.slotId}
          onValueChange={v => setForm(f => ({ ...f, slotId: v }))}
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
        disabled={!form.slotId}
      >
        Confirm Booking
      </Button>
    </form>
  );
}
