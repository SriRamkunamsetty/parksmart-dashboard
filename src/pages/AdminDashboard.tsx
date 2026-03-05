import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ParkingGrid } from '@/components/parking/ParkingGrid';
import { ApiStatusBadge } from '@/components/parking/ApiStatusBadge';
import { useSlotPolling } from '@/hooks/useSlotPolling';
import {
  Car, LogOut, Users, CheckCircle, Clock, AlertCircle,
  Download, BarChart3, TrendingUp, RefreshCw, Upload, Video, Loader2,
} from 'lucide-react';
import { ParkingSlot } from '@/types/parking';

type UploadStatus = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

const uploadStatusConfig: Record<UploadStatus, { label: string; color: string }> = {
  idle:      { label: 'Waiting for video upload',                                      color: 'text-muted-foreground' },
  uploading: { label: 'Uploading video...',                                             color: 'text-yellow-600' },
  analyzing: { label: 'Parking analysis started...',                                   color: 'text-blue-600' },
  done:      { label: 'Parking video uploaded successfully. Analysis started.',         color: 'text-green-600' },
  error:     { label: 'Upload failed. Please check the server and try again.',          color: 'text-destructive' },
};

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
  const { currentUser, slots, bookings, logout, syncSlotsFromApi } = useParkingStore();

  const handleSlotsUpdate = useCallback((s: ParkingSlot[]) => syncSlotsFromApi(s), [syncSlotsFromApi]);
  const { apiStatus, lastUpdated } = useSlotPolling(handleSlotsUpdate);

  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!currentUser || currentUser.role !== 'admin') { navigate('/'); return null; }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file) setUploadStatus('idle');
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploadStatus('uploading');
    setUploadProgress(0);

    // Simulate progress ticks while uploading
    const progressInterval = setInterval(() => {
      setUploadProgress(prev => Math.min(prev + 10, 90));
    }, 200);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch('http://localhost:8000/upload-parking-video', {
        method: 'POST',
        body: formData,
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (!res.ok) throw new Error('Server error');

      setUploadStatus('analyzing');
      setTimeout(() => setUploadStatus('done'), 1500);
    } catch {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setUploadStatus('error');
    }
  };

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
    const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'parkings_bookings.csv'; a.click();
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
            <ApiStatusBadge status={apiStatus} lastUpdated={lastUpdated} />
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
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">{total} total slots</span>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <RefreshCw className="w-3 h-3" /> every 5s
              </span>
            </div>
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

        {/* Parking Video Analysis */}
        <section>
          <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
            <Video className="w-5 h-5 text-primary" /> Parking Video Analysis
          </h2>
          <div className="bg-card rounded-2xl border border-border p-6 card-shadow space-y-5">
            {/* File input */}
            <div className="space-y-1.5">
              <label className="text-sm font-semibold text-foreground">Upload Parking Video</label>
              <div
                className="flex items-center gap-3 p-3 rounded-xl border-2 border-dashed border-border bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Upload className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {selectedFile ? selectedFile.name : 'Choose a .mp4 file…'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Upload a parking lot video to automatically detect occupied parking slots.
                  </p>
                </div>
                {selectedFile && (
                  <span className="text-xs text-muted-foreground shrink-0">
                    {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
                  </span>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            {/* Upload button + status row */}
            <div className="flex flex-col sm:flex-row sm:items-center gap-4">
              <Button
                onClick={handleUpload}
                disabled={!selectedFile || uploadStatus === 'uploading' || uploadStatus === 'analyzing'}
                className="gap-2 font-medium"
              >
                {(uploadStatus === 'uploading' || uploadStatus === 'analyzing')
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Upload className="w-4 h-4" />}
                Upload &amp; Analyze Parking
              </Button>

              {/* Status indicator */}
              <div className="flex items-center gap-2">
                {(uploadStatus === 'uploading' || uploadStatus === 'analyzing') && (
                  <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
                )}
                <span className={`text-sm font-medium ${uploadStatusConfig[uploadStatus].color}`}>
                  {uploadStatusConfig[uploadStatus].label}
                </span>
              </div>
            </div>

            {/* Progress bar — visible during upload/analysis/done */}
            {uploadStatus !== 'idle' && uploadStatus !== 'error' && (
              <div className="space-y-1.5">
                <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>
                    {uploadStatus === 'done' ? 'Slot grid will update automatically every 5s' : 'Processing…'}
                  </span>
                  <span>{uploadProgress}%</span>
                </div>
              </div>
            )}

            {/* Helper note when done */}
            {uploadStatus === 'done' && (
              <div className="flex items-start gap-2 p-3 rounded-xl bg-green-500/10 border border-green-500/20">
                <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
                <p className="text-xs text-green-700 dark:text-green-400 leading-relaxed">
                  Analysis is running. The parking slot grid below refreshes every 5 seconds and will reflect detected slot statuses automatically.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Parking Grid */}
        <section>
          <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
            <Car className="w-5 h-5 text-primary" /> Live Parking Slot Monitor
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
              <Download className="w-4 h-4" /> Export CSV
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
