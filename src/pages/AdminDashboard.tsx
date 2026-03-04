import { useNavigate } from 'react-router-dom';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ParkingGrid } from '@/components/parking/ParkingGrid';
import {
  Car, LogOut, Users, CheckCircle, Clock, AlertCircle,
  Download, BarChart3, TrendingUp,
} from 'lucide-react';

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    active: 'bg-green-100 text-green-700 border-green-200 hover:bg-green-100',
    expired: 'bg-red-100 text-red-700 border-red-200 hover:bg-red-100',
    cancelled: 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-100',
    occupied: 'bg-blue-100 text-blue-700 border-blue-200 hover:bg-blue-100',
  };
  return <Badge className={map[status] || map.cancelled}>{status}</Badge>;
};

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { currentUser, slots, bookings, logout } = useParkingStore();

  if (!currentUser || currentUser.role !== 'admin') { navigate('/'); return null; }

  const total = slots.length;
  const available = slots.filter(s => s.status === 'available').length;
  const reserved = slots.filter(s => s.status === 'reserved').length;
  const occupied = slots.filter(s => s.status === 'occupied').length;
  const occupancyRate = Math.round(((occupied + reserved) / total) * 100);

  const downloadCSV = () => {
    const headers = ['Name', 'Phone', 'Vehicle', 'Slot', 'Booking Time', 'Expiry Time', 'Status'];
    const rows = bookings.map(b => [
      b.customerName, b.phone, b.vehicleNumber, b.slotNumber,
      b.bookingTime.toLocaleString(), b.expiryTime.toLocaleString(), b.status,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'bookings.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const stats = [
    { label: 'Total Slots', value: total, icon: BarChart3, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
    { label: 'Available', value: available, icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50 border-green-200' },
    { label: 'Reserved', value: reserved, icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-50 border-yellow-200' },
    { label: 'Occupied', value: occupied, icon: Car, color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
    { label: 'Occupancy Rate', value: `${occupancyRate}%`, icon: TrendingUp, color: 'text-primary', bg: 'bg-primary/5 border-primary/20' },
    { label: 'Total Bookings', value: bookings.length, icon: Users, color: 'text-purple-600', bg: 'bg-purple-50 border-purple-200' },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-hero)' }}>
              <Car className="w-5 h-5 text-primary-foreground" />
            </div>
            <div>
              <span className="font-display font-bold text-foreground">ParkSmart</span>
              <span className="text-xs text-muted-foreground ml-2">Admin Dashboard</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="gap-1.5 text-primary border-primary/30 bg-primary/5">
              <AlertCircle className="w-3 h-3" /> Admin
            </Badge>
            <Button variant="outline" size="sm" onClick={() => { logout(); navigate('/'); }} className="gap-2">
              <LogOut className="w-4 h-4" /> Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Stats */}
        <div>
          <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" /> Analytics Overview
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {stats.map(stat => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className={`rounded-2xl border p-4 card-shadow ${stat.bg}`}>
                  <Icon className={`w-5 h-5 mb-2 ${stat.color}`} />
                  <p className={`text-2xl font-display font-bold ${stat.color}`}>{stat.value}</p>
                  <p className="text-xs text-muted-foreground mt-1 font-medium">{stat.label}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Occupancy bar */}
        <div className="bg-card rounded-2xl border border-border p-5 card-shadow">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-semibold text-foreground">Slot Occupancy</h3>
            <span className="text-sm text-muted-foreground">{total} total slots</span>
          </div>
          <div className="w-full h-4 rounded-full overflow-hidden bg-muted flex">
            <div
              className="h-full bg-red-500 transition-all duration-500"
              style={{ width: `${(occupied / total) * 100}%` }}
              title={`Occupied: ${occupied}`}
            />
            <div
              className="h-full bg-yellow-400 transition-all duration-500"
              style={{ width: `${(reserved / total) * 100}%` }}
              title={`Reserved: ${reserved}`}
            />
            <div
              className="h-full bg-green-500 transition-all duration-500"
              style={{ width: `${(available / total) * 100}%` }}
              title={`Available: ${available}`}
            />
          </div>
          <div className="flex gap-6 mt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Occupied ({occupied})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-yellow-400" /> Reserved ({reserved})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-green-500" /> Available ({available})</span>
          </div>
        </div>

        {/* Parking Grid */}
        <section>
          <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
            <Car className="w-5 h-5 text-primary" /> Parking Slot Monitor
          </h2>
          <div className="bg-card rounded-2xl border border-border p-6 card-shadow">
            <ParkingGrid slots={slots} />
          </div>
        </section>

        {/* Bookings Table */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-bold text-foreground flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" /> All Bookings
            </h2>
            <Button onClick={downloadCSV} variant="outline" className="gap-2 font-medium">
              <Download className="w-4 h-4" /> Export Excel
            </Button>
          </div>

          <div className="bg-card rounded-2xl border border-border card-shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    {['Name', 'Phone', 'Vehicle No.', 'Slot', 'Booking Time', 'Expiry Time', 'Status'].map(h => (
                      <th key={h} className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b, i) => (
                    <tr key={b.id} className={`border-b border-border/60 hover:bg-muted/30 transition-colors ${i % 2 === 0 ? '' : 'bg-muted/10'}`}>
                      <td className="py-3 px-4 font-medium text-foreground">{b.customerName}</td>
                      <td className="py-3 px-4 text-muted-foreground">{b.phone}</td>
                      <td className="py-3 px-4 font-mono text-sm font-semibold">{b.vehicleNumber}</td>
                      <td className="py-3 px-4">
                        <span className="px-2.5 py-1 bg-primary/10 text-primary text-xs font-bold rounded-lg">{b.slotNumber}</span>
                      </td>
                      <td className="py-3 px-4 text-muted-foreground whitespace-nowrap">{b.bookingTime.toLocaleString()}</td>
                      <td className="py-3 px-4 text-muted-foreground whitespace-nowrap">{b.expiryTime.toLocaleString()}</td>
                      <td className="py-3 px-4">{statusBadge(b.status)}</td>
                    </tr>
                  ))}
                  {bookings.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-muted-foreground">No bookings yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
