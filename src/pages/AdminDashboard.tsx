import { useNavigate } from 'react-router-dom';
import { useParkingStore } from '@/store/parkingStore';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Car, LogOut, Users, CheckCircle, Clock, AlertCircle,
  Download, BarChart3, TrendingUp, UploadCloud, Video, RefreshCw,
  Play, Square, RotateCcw, Settings2, Edit3, Trash2, MapPin, MousePointerClick, Flame,
  Activity, Server, Cpu, HardDrive, Pause, XCircle, Layers
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    available: 'bg-green-100 text-green-700 border-green-200 hover:bg-green-100',
    occupied: 'bg-red-100 text-red-700 border-red-200 hover:bg-red-100',
    active: 'bg-green-100 text-green-700 border-green-200 hover:bg-green-100',
    expired: 'bg-red-100 text-red-700 border-red-200 hover:bg-red-100',
    cancelled: 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-100',
    processing: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    paused: 'bg-orange-100 text-orange-700 border-orange-200',
    completed: 'bg-green-100 text-green-700 border-green-200',
    error: 'bg-red-100 text-red-700 border-red-200',
  };
  return <Badge className={map[status] || map.cancelled}>{status.toUpperCase()}</Badge>;
};

export default function AdminDashboard() {
  const navigate = useNavigate();
  const {
    currentUser, slots, bookings, stats, isLoadingSlots, analysisStatus, ws,
    systemHealth, currentJob, activeJobId,
    logout, syncSlotsFromApi, syncStatsFromApi, syncAnalysisStatus, fetchSystemHealth, fetchBookings, connectWebSocket, updateSlot,
    pauseJob, resumeJob, cancelJob, reseedSlots
  } = useParkingStore();

  const [isUploading, setIsUploading] = useState(false);
  const [drawingSlot, setDrawingSlot] = useState<string | null>(null);
  const [points, setPoints] = useState<{ x: number, y: number }[]>([]);
  const [jobHistory, setJobHistory] = useState<any[]>([]);

  useEffect(() => {
    if (!currentUser || currentUser.role !== 'admin') {
      navigate('/');
      return;
    }
    connectWebSocket();
    syncSlotsFromApi();
    syncStatsFromApi();
    syncAnalysisStatus();
    fetchBookings();

    // Poll health and jobs
    fetchSystemHealth();
    fetchJobHistory();
    const intervalId = setInterval(() => {
      fetchSystemHealth();
      fetchJobHistory();
    }, 5000);

    return () => clearInterval(intervalId);
  }, [currentUser, navigate]);

  const triggerRefresh = () => {
    syncSlotsFromApi();
    syncStatsFromApi();
    syncAnalysisStatus();
    fetchJobHistory();
  };

  const fetchJobHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/jobs');
      if (res.ok) setJobHistory(await res.json());
    } catch { }
  };

  const handleStartAnalysis = async () => {
    try {
      await fetch('http://localhost:8000/start-analysis', { method: 'POST' });
      toast.success("Analysis started");
      setTimeout(triggerRefresh, 1000);
    } catch (e) {
      toast.error("Failed to start analysis");
    }
  };

  const handleStopAnalysis = async () => {
    try {
      await fetch('http://localhost:8000/stop-analysis', { method: 'POST' });
      toast.warning("Analysis stopped");
      setTimeout(triggerRefresh, 1000);
    } catch (e) {
      toast.error("Failed to stop analysis");
    }
  };

  const handleJobAction = async (action: 'pause' | 'resume' | 'cancel') => {
    if (!activeJobId) return;
    let success = false;
    if (action === 'pause') success = await pauseJob(activeJobId);
    if (action === 'resume') success = await resumeJob(activeJobId);
    if (action === 'cancel') success = await cancelJob(activeJobId);

    if (success) {
      toast.success(`Job ${action}d successfully`);
      setTimeout(triggerRefresh, 500);
    } else {
      toast.error(`Failed to ${action} job`);
    }
  };

  const handleResetSlots = async () => {
    const success = await reseedSlots();
    if (success) {
      toast.success("Parking slots reset to available");
    } else {
      toast.error("Failed to reset slots");
    }
  };

  const handleReseedSlots = async () => {
    const success = await reseedSlots();
    if (success) {
      toast.success("S1-S7 reseeded successfully");
    } else {
      toast.error("Failed to reseed slots");
    }
  };

  const handleDeleteSlot = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/slots/${id}`, { method: 'DELETE' });
      if (res.ok) {
        toast.success("Polygon removed and slot reset");
        if (drawingSlot === id) {
          setDrawingSlot(null);
          setPoints([]);
        }
        syncSlotsFromApi();
      }
    } catch (e) {
      toast.error("Failed to reset slot");
    }
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8000/upload-parking-video', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        toast.success("Video uploaded successfully. Parking analysis queued/started.");
        setTimeout(triggerRefresh, 2000);
      } else {
        const errData = await res.json();
        toast.error(errData.detail || errData.error || "Failed to upload video.");
      }
    } catch (err) {
      toast.error("Network error during upload.");
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleVideoClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!drawingSlot) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const scaleX = 960 / rect.width;
    const scaleY = 540 / rect.height;

    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    const newPoints = [...points, { x, y }];
    setPoints(newPoints);

    if (newPoints.length === 4) {
      const polyArray = newPoints.map(p => [p.x, p.y]);
      updateSlot(drawingSlot, { polygon: JSON.stringify(polyArray) }).then(success => {
        if (success) {
          toast.success(`Polygon saved to Database for slot ${drawingSlot}`);
          syncSlotsFromApi();
        } else {
          toast.error("Failed to save polygon");
        }
      });
      setDrawingSlot(null);
      setPoints([]);
    }
  };

  if (!currentUser || currentUser.role !== 'admin') return null;

  const occupancyRate = stats.total_slots > 0
    ? Math.round(((stats.occupied + stats.reserved) / stats.total_slots) * 100)
    : 0;

  const downloadCSV = () => {
    const headers = ['Name', 'Phone', 'Vehicle', 'Slot', 'Booking Time', 'Expiry Time', 'Status'];
    const rows = bookings.map(b => [
      b.customerName, b.phone, b.vehicleNumber, b.slotId,
      new Date(b.bookingTime).toLocaleString(), new Date(b.expiryTime).toLocaleString(), b.status,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',').replace(/"/g, '""')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'bookings.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const systemStats = [
    { label: 'CPU Usage', value: systemHealth ? `${(systemHealth.cpu_percent ?? 0).toFixed(1)}%` : '...', icon: Cpu, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200' },
    { label: 'Memory RAM', value: systemHealth ? `${(systemHealth.memory_percent ?? 0).toFixed(1)}%` : '...', icon: Server, color: 'text-indigo-600', bg: 'bg-indigo-50 border-indigo-200' },
    { label: 'Disk IO Storage', value: systemHealth ? `${(systemHealth.disk_percent ?? 0).toFixed(1)}%` : '...', icon: HardDrive, color: 'text-teal-600', bg: 'bg-teal-50 border-teal-200' },
    { label: 'Active Pipeline Jobs', value: systemHealth ? (systemHealth.active_workers ?? 0) : '...', icon: Activity, color: 'text-pink-600', bg: 'bg-pink-50 border-pink-200' },
    { label: 'Frame Queue Size', value: systemHealth ? (systemHealth.frame_queue_size ?? 0) : '...', icon: Layers, color: 'text-yellow-600', bg: 'bg-yellow-50 border-yellow-200' },
    { label: 'Process Uptime', value: systemHealth ? formatUptime(systemHealth.process_uptime ?? 0) : '...', icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
  ];

  return (
    <div className="min-h-screen bg-background pb-12">
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
            <Badge variant="outline" className={`gap-1 hidden sm:flex ${ws?.readyState === WebSocket.OPEN ? 'text-green-600 border-green-200 bg-green-50' : 'text-yellow-600 border-yellow-200 bg-yellow-50'}`}>
              WebSocket {ws?.readyState === WebSocket.OPEN ? 'Connected' : 'Connecting'}
            </Badge>
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

        {/* System Health Module */}
        <section className="bg-card rounded-2xl border border-border p-6 card-shadow">
          <h2 className="text-lg font-display font-bold text-foreground mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" /> System Health Dashboard
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            {systemStats.map(stat => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className={`rounded-2xl border p-4 ${stat.bg}`}>
                  <Icon className={`w-5 h-5 mb-2 ${stat.color}`} />
                  <p className={`text-2xl font-display font-bold ${stat.color}`}>{stat.value}</p>
                  <p className="text-xs text-muted-foreground mt-1 font-medium">{stat.label}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Video Processing Module */}
        <section className="bg-card rounded-2xl border border-border p-6 card-shadow flex flex-col gap-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-2 border-b border-border">
            <div>
              <h2 className="text-lg font-display font-bold text-foreground mb-2 flex items-center gap-2">
                <Video className="w-5 h-5 text-primary" /> Parking Video Analysis & Queue
              </h2>
              <p className="text-sm text-muted-foreground max-w-xl">
                Upload a <code>.mp4</code> video feed to trigger the Distributed YOLOv8 AI pipeline.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="relative group w-full md:w-auto">
                <Button disabled={isUploading} className="w-full gap-2 bg-primary hover:bg-primary/90 text-primary-foreground font-medium">
                  {isUploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4" />}
                  {isUploading ? 'Uploading...' : 'Queue New Video'}
                </Button>
                <input
                  type="file"
                  accept="video/mp4,video/avi"
                  onChange={handleVideoUpload}
                  disabled={isUploading}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                />
              </div>
              <Button onClick={handleResetSlots} variant="destructive" className="gap-2 font-medium">
                <RotateCcw className="w-4 h-4" /> Reset Status
              </Button>
              <Button onClick={handleReseedSlots} variant="outline" className="gap-2 font-medium border-primary/30 text-primary hover:bg-primary/5">
                <RefreshCw className="w-4 h-4" /> Reseed S1-S7
              </Button>
            </div>
          </div>

          {/* Processing Progress Card */}
          {currentJob && (
            <div className="bg-muted/30 rounded-xl border border-border p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <RefreshCw className={`w-5 h-5 ${currentJob.status === 'processing' ? 'text-blue-500 animate-spin' : 'text-orange-500'}`} />
                  <h3 className="font-display font-bold text-foreground">Pipeline Execution
                    <Badge variant="outline" className="ml-3 font-mono text-xs">{activeJobId?.split('-')[0]}</Badge>
                  </h3>
                </div>
                <div>{statusBadge(currentJob.status || analysisStatus)}</div>
              </div>

              <div className="w-full bg-secondary/50 rounded-full h-3 overflow-hidden border border-border">
                <div
                  className={`h-full transition-all duration-300 ${currentJob.status === 'processing' ? 'bg-primary' : 'bg-orange-500'}`}
                  style={{ width: `${currentJob.progress}%` }}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between text-sm">
                <div className="flex gap-6">
                  <div className="flex flex-col">
                    <span className="text-muted-foreground text-xs font-semibold uppercase">Frames Processed</span>
                    <span className="font-mono font-bold mt-1">{currentJob.processed_frames} / {currentJob.total_frames} (<span className="text-primary">{Math.round(currentJob.progress)}%</span>)</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground text-xs font-semibold uppercase">Detection Rate</span>
                    <span className="font-mono font-bold mt-1">{currentJob.fps} FPS</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground text-xs font-semibold uppercase">Est. Completion</span>
                    <span className="font-mono font-bold mt-1 text-blue-600">{currentJob.eta_seconds > 0 ? `${Math.ceil(currentJob.eta_seconds)} sec` : 'Calculating...'}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-muted-foreground text-xs font-semibold uppercase">Skip Limit</span>
                    <span className="font-mono font-bold mt-1 text-orange-600">x{currentJob.frame_skip_interval}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {currentJob.status === 'processing' && (
                    <Button variant="outline" size="sm" onClick={() => handleJobAction('pause')} className="gap-1.5 border-orange-200 text-orange-600 hover:bg-orange-50">
                      <Pause className="w-3.5 h-3.5" /> Suspend
                    </Button>
                  )}
                  {currentJob.status === 'paused' && (
                    <Button variant="outline" size="sm" onClick={() => handleJobAction('resume')} className="gap-1.5 border-blue-200 text-blue-600 hover:bg-blue-50">
                      <Play className="w-3.5 h-3.5" /> Resume
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => handleJobAction('cancel')} className="gap-1.5 border-red-200 text-red-600 hover:bg-red-50">
                    <XCircle className="w-3.5 h-3.5" /> Abort Job
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Developer Pipeline Diagnostics Panel */}
          {systemHealth && (
            <div className="bg-muted/30 rounded-xl border border-border p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <Settings2 className="w-5 h-5 text-purple-500" />
                <h3 className="font-display font-bold text-foreground">Pipeline Diagnostics</h3>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="bg-background rounded-lg p-4 border border-border flex flex-col">
                  <span className="text-muted-foreground text-xs font-semibold uppercase">Inference</span>
                  <span className="font-mono font-bold mt-1 text-purple-600">{systemHealth.inference_time_ms || 0} ms</span>
                </div>
                <div className="bg-background rounded-lg p-4 border border-border flex flex-col">
                  <span className="text-muted-foreground text-xs font-semibold uppercase">Decode</span>
                  <span className="font-mono font-bold mt-1 text-blue-600">{systemHealth.decode_time_ms || 0} ms</span>
                </div>
                <div className="bg-background rounded-lg p-4 border border-border flex flex-col">
                  <span className="text-muted-foreground text-xs font-semibold uppercase">Slot Eval</span>
                  <span className="font-mono font-bold mt-1 text-teal-600">{systemHealth.slot_eval_time_ms || 0} ms</span>
                </div>
                <div className="bg-background rounded-lg p-4 border border-border flex flex-col">
                  <span className="text-muted-foreground text-xs font-semibold uppercase">Queue Size</span>
                  <span className="font-mono font-bold mt-1 text-orange-600">{systemHealth.frame_queue_size || 0}</span>
                </div>
                <div className="bg-background rounded-lg p-4 border border-border flex flex-col">
                  <span className="text-muted-foreground text-xs font-semibold uppercase">Skip Interval</span>
                  <span className="font-mono font-bold mt-1 text-pink-600">x{systemHealth.frame_skip_interval || 12}</span>
                </div>
              </div>
            </div>
          )}

          {/* Fallback old controls just in case */}
          {!currentJob && analysisStatus !== 'processing' && (
            <div className="flex items-center gap-3">
              <Button onClick={handleStartAnalysis} variant="secondary" className="gap-2">
                <Play className="w-4 h-4 text-emerald-600" /> Start Default Feed
              </Button>
              <Button onClick={handleStopAnalysis} variant="secondary" className="gap-2">
                <Square className="w-4 h-4 text-rose-600" /> Stop Feeds
              </Button>
            </div>
          )}
        </section>

        {(analysisStatus === 'processing' || analysisStatus === 'paused') && (
          <section className="bg-card rounded-2xl border border-border p-6 card-shadow flex flex-col items-center justify-center relative">
            <h3 className="font-display font-bold text-foreground mb-4 w-full text-left flex items-center gap-2 justify-between">
              <div className="flex items-center gap-2"><Video className="w-5 h-5 text-primary" /> Live Detection Stream</div>
              {drawingSlot && <Badge className="bg-blue-100 text-blue-700 animate-pulse border-blue-300">Configuration Tool Active: Click Point {points.length + 1}/4 for {drawingSlot}</Badge>}
            </h3>

            <div className={`w-full max-w-4xl bg-black rounded-lg overflow-hidden flex items-center justify-center min-h-[400px] relative ${drawingSlot ? 'cursor-crosshair ring-4 ring-blue-500 rounded-lg' : ''}`}>
              <img
                src="http://localhost:8000/video-feed"
                alt="Live Parking Feed MJPEG"
                className="w-full max-h-[600px] object-contain"
                onClick={handleVideoClick}
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />

              {drawingSlot && points.map((p, i) => (
                <div key={i} className="absolute w-4 h-4 rounded-full bg-red-500 border-2 border-white transform -translate-x-1/2 -translate-y-1/2 z-10"
                  style={{ left: `${(p.x / 960) * 100}%`, top: `${(p.y / 540) * 100}%` }}>
                  <span className="absolute -top-5 -left-1 text-white text-xs font-bold bg-black/50 px-1 rounded">{i + 1}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Processing History Table */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-bold text-foreground flex items-center gap-2">
              <RefreshCw className="w-5 h-5 text-primary" /> AI Video Processing History
            </h2>
          </div>
          <div className="bg-card rounded-2xl border border-border card-shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Job ID</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">File Name</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Date</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Frames</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Video Duration</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {jobHistory.map((h, i) => (
                    <tr key={h.id} className={`border-b border-border/60 hover:bg-muted/30 transition-colors ${i % 2 === 0 ? '' : 'bg-muted/10'}`}>
                      <td className="py-3 px-4 font-mono text-xs">{h.job_id.split('-')[0]}</td>
                      <td className="py-3 px-4 font-medium">{h.video_name}</td>
                      <td className="py-3 px-4 text-muted-foreground">{new Date(h.created_at).toLocaleString()}</td>
                      <td className="py-3 px-4 font-mono">{h.total_frames}</td>
                      <td className="py-3 px-4">{Math.round(h.duration_seconds)}s</td>
                      <td className="py-3 px-4">{statusBadge(h.status)}</td>
                    </tr>
                  ))}
                  {jobHistory.length === 0 && (
                    <tr><td colSpan={6} className="py-8 text-center text-muted-foreground italic">No processing history recorded</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Slot Grid Map & Bookings Table (Existing components compressed slightly below) */}
        <section>
          <div className="flex items-center justify-between mb-4 mt-8">
            <h2 className="text-lg font-display font-bold text-foreground flex items-center gap-2">
              <MapPin className="w-5 h-5 text-primary" /> Slot Configuration & Editor
            </h2>
          </div>
          <div className="bg-card rounded-2xl border border-border card-shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Slot ID</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Status</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap"><Flame className="w-4 h-4 inline-block text-orange-500 mr-1" /> Heatmap Count</th>
                    <th className="text-left py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Polygon Configured</th>
                    <th className="text-right py-3 px-4 font-semibold text-muted-foreground whitespace-nowrap">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {slots.map((s, i) => (
                    <tr key={s.id} className={`border-b border-border/60 hover:bg-muted/30 transition-colors ${i % 2 === 0 ? '' : 'bg-muted/10'}`}>
                      <td className="py-3 px-4 font-medium text-foreground">{s.id} ({s.number})</td>
                      <td className="py-3 px-4">{statusBadge(s.status)}</td>
                      <td className="py-3 px-4 font-mono font-semibold text-orange-600">{s.heatmap_count || 0}</td>
                      <td className="py-3 px-4">
                        {s.polygon_configured ? <Badge variant="outline" className="text-green-600 bg-green-50">Yes</Badge> : <Badge variant="outline" className="text-red-500 bg-red-50">No</Badge>}
                      </td>
                      <td className="py-3 px-4 flex justify-end gap-2">
                        <Button
                          variant={drawingSlot === s.id ? "default" : "outline"}
                          size="sm"
                          onClick={() => { setDrawingSlot(drawingSlot === s.id ? null : s.id); setPoints([]); }}
                          className="gap-1.5"
                        >
                          <MousePointerClick className="w-3.5 h-3.5" />
                          {drawingSlot === s.id ? "Cancel Draw" : "Draw Polygon"}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteSlot(s.id)} className="text-destructive hover:bg-destructive/10 hover:text-destructive">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

      </main>
    </div >
  );
}
