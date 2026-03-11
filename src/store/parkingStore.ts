import { create } from 'zustand';
import { Booking, ParkingSlot, User } from '../types/parking';

export interface SystemHealth {
  status: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  active_workers: number;
  process_uptime: number;
  active_job_id: string | null;
  frame_queue_size: number;
  frame_skip_interval: number;
  decode_time_ms?: number;
  inference_time_ms?: number;
  slot_eval_time_ms?: number;
}

export interface JobProgress {
  progress: number;
  processed_frames: number;
  total_frames: number;
  fps: number;
  eta_seconds: number;
  frame_skip_interval: number;
  status?: string;
}

interface ParkingStore {
  currentUser: User | null;
  slots: ParkingSlot[];
  bookings: Booking[];
  stats: {
    total_slots: number;
    available: number;
    reserved: number;
    occupied: number;
  };
  isLoadingSlots: boolean;
  analysisStatus: 'idle' | 'processing' | 'paused';

  systemHealth: SystemHealth | null;
  currentJob: JobProgress | null;
  activeJobId: string | null;

  ws: WebSocket | null;

  login: (email: string, password: string, role: 'user' | 'admin') => boolean;
  logout: () => void;
  register: (name: string, email: string, password: string) => boolean;

  bookSlot: (data: any) => Promise<boolean>;
  cancelBooking: (bookingId: number) => Promise<boolean>;
  fetchBookings: (phone?: string) => Promise<void>;

  syncSlotsFromApi: (signal?: AbortSignal) => Promise<void>;
  syncStatsFromApi: () => Promise<void>;
  syncAnalysisStatus: () => Promise<void>;
  fetchSystemHealth: () => Promise<void>;

  connectWebSocket: () => void;
  updateSlot: (slotId: string, updates: Partial<ParkingSlot>) => Promise<boolean>;

  // Job controls
  pauseJob: (jobId: string) => Promise<boolean>;
  resumeJob: (jobId: string) => Promise<boolean>;
  cancelJob: (jobId: string) => Promise<boolean>;
  reseedSlots: () => Promise<boolean>;
}

const mockAdminUser: User = { id: 'admin-1', name: 'Admin', email: 'admin@park.com', role: 'admin' };
const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

export const useParkingStore = create<ParkingStore>((set, get) => ({
  currentUser: null,
  slots: [],
  bookings: [],
  stats: {
    total_slots: 0,
    available: 0,
    reserved: 0,
    occupied: 0,
  },
  isLoadingSlots: false,
  analysisStatus: 'idle',
  systemHealth: null,
  currentJob: null,
  activeJobId: null,
  ws: null,

  login: (email, _password, role) => {
    if (role === 'admin' && email === 'admin@park.com') {
      set({ currentUser: mockAdminUser });
      get().fetchBookings();
      return true;
    }
    if (role === 'user' && email) {
      set({
        currentUser: {
          id: `user-${Date.now()}`,
          name: email.split('@')[0],
          email,
          role: 'user',
        },
      });
      get().fetchBookings(email);
      return true;
    }
    return false;
  },

  logout: () => set({ currentUser: null, bookings: [] }),
  register: (name, email, _password) => {
    set({ currentUser: { id: `user-${Date.now()}`, name, email, role: 'user' } });
    return true;
  },

  bookSlot: async (data) => {
    try {
      const res = await fetch(`${API_URL}/book-slot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        await get().fetchBookings();
        return true;
      }
      return false;
    } catch { return false; }
  },

  cancelBooking: async (bookingId) => {
    try {
      const res = await fetch(`${API_URL}/cancel-booking/${bookingId}`, { method: 'POST' });
      if (res.ok) {
        await get().fetchBookings();
        return true;
      }
      return false;
    } catch { return false; }
  },

  fetchBookings: async (phone?: string) => {
    try {
      let url = `${API_URL}/bookings`;
      if (phone) url = `${API_URL}/booking-history?phone=${encodeURIComponent(phone)}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        set({ bookings: data });
      }
    } catch (e) { console.error(e); }
  },

  updateSlot: async (slotId, updates) => {
    try {
      const res = await fetch(`${API_URL}/api/slots/${slotId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      return res.ok;
    } catch { return false; }
  },

  syncSlotsFromApi: async (signal) => {
    try {
      set({ isLoadingSlots: true });
      const response = await fetch(`${API_URL}/api/slots`, { signal });
      if (!response.ok) throw new Error('API failed');
      const data = await response.json();
      set({ slots: data });
    } catch (error: any) {
      if (error.name === 'AbortError') return;
      console.warn('Slot sync failed', error);
    } finally {
      if (!signal?.aborted) set({ isLoadingSlots: false });
    }
  },

  syncStatsFromApi: async () => {
    try {
      const response = await fetch(`${API_URL}/api/slots/stats`); // Updated to match consolidated router if needed, or keeping legacy
      if (!response.ok) {
        // Fallback to slot-stats if the prefix hasn't been moved yet
        const fb = await fetch(`${API_URL}/slot-stats`);
        if (fb.ok) { set({ stats: await fb.json() }); return; }
      }
      const data = await response.json();
      set({ stats: data });
    } catch (error) { console.warn('Stats sync failed', error); }
  },

  syncAnalysisStatus: async () => {
    try {
      const response = await fetch(`${API_URL}/analysis-status`);
      if (response.ok) {
        const data = await response.json();
        set({
          analysisStatus: data.status as 'idle' | 'processing' | 'paused',
          activeJobId: data.active_job
        });
      }
    } catch (error) { }
  },

  fetchSystemHealth: async () => {
    try {
      const response = await fetch(`${API_URL}/api/system/health`);
      if (response.ok) {
        const data = await response.json();
        set({ systemHealth: data });
      }
    } catch (error) { }
  },

  pauseJob: async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/pause`, { method: 'POST' });
      if (res.ok) {
        set((state) => ({ currentJob: state.currentJob ? { ...state.currentJob, status: 'paused' } : null, analysisStatus: 'paused' }));
        return true;
      }
    } catch { }
    return false;
  },

  resumeJob: async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/resume`, { method: 'POST' });
      if (res.ok) {
        set((state) => ({ currentJob: state.currentJob ? { ...state.currentJob, status: 'processing' } : null, analysisStatus: 'processing' }));
        return true;
      }
    } catch { }
    return false;
  },

  cancelJob: async (jobId) => {
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/cancel`, { method: 'POST' });
      if (res.ok) {
        set({ currentJob: null, analysisStatus: 'idle', activeJobId: null });
        await get().syncAnalysisStatus();
        return true;
      }
    } catch { }
    return false;
  },

  reseedSlots: async () => {
    try {
      const res = await fetch(`${API_URL}/api/slots/reseed`, { method: 'POST' });
      if (res.ok) {
        await get().syncSlotsFromApi();
        await get().syncStatsFromApi();
        return true;
      }
    } catch { }
    return false;
  },

  connectWebSocket: () => {
    const { ws } = get();
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const newWs = new WebSocket(WS_URL);
    newWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'slot_update') {
          const { slots } = get();
          const updatedSlots = slots.map(s => s.id === data.slot_id ? { ...s, status: data.status } : s);
          const stats = {
            total_slots: updatedSlots.length,
            available: updatedSlots.filter(s => s.status === 'available').length,
            reserved: updatedSlots.filter(s => s.status === 'reserved').length,
            occupied: updatedSlots.filter(s => s.status === 'occupied').length,
          };
          set({ slots: updatedSlots, stats });
        } else if (data.event === 'reload_slots') {
          get().syncSlotsFromApi();
          get().syncStatsFromApi();
        } else if (data.event === 'video_progress') {
          set({
            currentJob: { ...data.payload, status: 'processing' },
            analysisStatus: 'processing',
            activeJobId: data.job_id
          });
        } else if (data.event === 'job_complete' || data.event === 'job_error' || data.event === 'job_cancelled') {
          set({ currentJob: null, analysisStatus: 'idle', activeJobId: null });
          get().syncAnalysisStatus(); // Refresh cleanly
        }
      } catch (e) { console.error(e); }
    };
    newWs.onclose = () => { setTimeout(() => get().connectWebSocket(), 3000); };
    set({ ws: newWs });
  }
}));
