import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useParkingStore } from '@/store/parkingStore';
import { ParkingGrid } from '@/components/parking/ParkingGrid';
import { BookingForm } from '@/components/parking/BookingForm';
import { CountdownTimer } from '@/components/parking/CountdownTimer';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Car, LogOut, MapPin, Calendar, XCircle, PlusCircle } from 'lucide-react';
import { ParkingSlot } from '@/types/parking';

export default function UserDashboard() {
  const navigate = useNavigate();
  const { currentUser, slots, bookings, logout, cancelBooking, expireBooking } = useParkingStore();
  const [selectedSlot, setSelectedSlot] = useState<ParkingSlot | null>(null);
  const [bookingOpen, setBookingOpen] = useState(false);

  if (!currentUser) { navigate('/'); return null; }

  const myBookings = bookings.filter(b => b.customerName === currentUser.name || true).filter(b => b.status === 'active');
  const available = slots.filter(s => s.status === 'available').length;
  const reserved = slots.filter(s => s.status === 'reserved').length;
  const occupied = slots.filter(s => s.status === 'occupied').length;

  const statusBadge = (status: string) => {
    if (status === 'active') return <Badge className="bg-green-100 text-green-700 border-green-300 hover:bg-green-100">Active</Badge>;
    if (status === 'expired') return <Badge className="bg-red-100 text-red-700 border-red-300 hover:bg-red-100">Expired</Badge>;
    if (status === 'cancelled') return <Badge className="bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-100">Cancelled</Badge>;
    return null;
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-hero)' }}>
              <Car className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <span className="font-display font-bold text-foreground">ParkSmart</span>
              <span className="text-xs text-muted-foreground ml-2">User Portal</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground hidden sm:block">Hi, <strong className="text-foreground">{currentUser.name}</strong></span>
            <Button variant="outline" size="sm" onClick={() => { logout(); navigate('/'); }} className="gap-2">
              <LogOut className="w-4 h-4" /> Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Available', value: available, color: 'bg-green-50 border-green-200', text: 'text-green-700', dot: 'bg-green-500' },
            { label: 'Reserved', value: reserved, color: 'bg-yellow-50 border-yellow-200', text: 'text-yellow-700', dot: 'bg-yellow-500' },
            { label: 'Occupied', value: occupied, color: 'bg-red-50 border-red-200', text: 'text-red-700', dot: 'bg-red-500' },
          ].map(stat => (
            <div key={stat.label} className={`rounded-2xl border p-4 card-shadow ${stat.color}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2.5 h-2.5 rounded-full ${stat.dot}`} />
                <span className={`text-xs font-semibold uppercase tracking-wider ${stat.text}`}>{stat.label}</span>
              </div>
              <p className={`text-3xl font-display font-bold ${stat.text}`}>{stat.value}</p>
            </div>
          ))}
        </div>

        {/* Active Bookings */}
        {myBookings.length > 0 && (
          <section>
            <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-primary" /> My Active Bookings
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              {myBookings.map(booking => (
                <div key={booking.id} className="bg-card rounded-2xl border border-border p-5 card-shadow space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <MapPin className="w-4 h-4 text-primary" />
                        <span className="font-display font-bold text-xl text-foreground">{booking.slotNumber}</span>
                        {statusBadge(booking.status)}
                      </div>
                      <p className="text-sm text-muted-foreground">Vehicle: <strong className="text-foreground">{booking.vehicleNumber}</strong></p>
                      <p className="text-sm text-muted-foreground">Booked: {booking.bookingTime.toLocaleTimeString()}</p>
                    </div>
                  </div>

                  <CountdownTimer
                    expiryTime={booking.expiryTime}
                    onExpire={() => expireBooking(booking.id)}
                  />

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => cancelBooking(booking.id)}
                    className="w-full gap-2 text-destructive border-destructive/30 hover:bg-destructive/10"
                  >
                    <XCircle className="w-4 h-4" /> Cancel Booking
                  </Button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Parking Grid */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-bold text-foreground flex items-center gap-2">
              <Car className="w-5 h-5 text-primary" /> Parking Slots
            </h2>
            <Button
              onClick={() => setBookingOpen(true)}
              className="gap-2 font-semibold"
              style={{ background: 'var(--gradient-hero)', border: 'none' }}
            >
              <PlusCircle className="w-4 h-4" /> Book a Slot
            </Button>
          </div>
          <div className="bg-card rounded-2xl border border-border p-6 card-shadow">
            <ParkingGrid
              slots={slots}
              onSlotSelect={slot => { setSelectedSlot(slot); setBookingOpen(true); }}
              selectedSlotId={selectedSlot?.id}
            />
          </div>
        </section>
      </main>

      {/* Booking Dialog */}
      <Dialog open={bookingOpen} onOpenChange={setBookingOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display">Book a Parking Slot</DialogTitle>
          </DialogHeader>
          <BookingForm
            slots={slots}
            selectedSlot={selectedSlot}
            onSuccess={() => { setBookingOpen(false); setSelectedSlot(null); }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
