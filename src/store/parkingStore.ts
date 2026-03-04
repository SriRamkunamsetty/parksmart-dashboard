import { create } from 'zustand';
import { Booking, ParkingSlot, User } from '../types/parking';

const BOOKING_DURATION_MS = 15 * 60 * 1000; // 15 minutes

const generateSlots = (): ParkingSlot[] => {
  const slots: ParkingSlot[] = [];
  const floors = ['A', 'B', 'C'];
  floors.forEach((floor) => {
    for (let i = 1; i <= 8; i++) {
      slots.push({
        id: `${floor}${i}`,
        number: `${floor}-${i.toString().padStart(2, '0')}`,
        floor,
        status: Math.random() > 0.6 ? 'occupied' : 'available',
      });
    }
  });
  return slots;
};

interface ParkingStore {
  currentUser: User | null;
  slots: ParkingSlot[];
  bookings: Booking[];
  login: (email: string, password: string, role: 'user' | 'admin') => boolean;
  logout: () => void;
  register: (name: string, email: string, password: string) => boolean;
  addBooking: (data: Omit<Booking, 'id' | 'bookingTime' | 'expiryTime' | 'status'>) => Booking;
  cancelBooking: (bookingId: string) => void;
  expireBooking: (bookingId: string) => void;
  /** Called by useSlotPolling to merge live API data while preserving reserved slots */
  syncSlotsFromApi: (apiSlots: ParkingSlot[]) => void;
}

const mockSlots = generateSlots();
mockSlots[2].status = 'reserved';
mockSlots[5].status = 'reserved';
mockSlots[10].status = 'reserved';

const mockAdminUser: User = { id: 'admin-1', name: 'Admin', email: 'admin@park.com', role: 'admin' };

export const useParkingStore = create<ParkingStore>((set, get) => ({
  currentUser: null,
  slots: mockSlots,
  bookings: [
    {
      id: 'b1',
      customerName: 'John Smith',
      phone: '555-0101',
      vehicleNumber: 'ABC-1234',
      slotId: 'A3',
      slotNumber: 'A-03',
      bookingTime: new Date(Date.now() - 5 * 60 * 1000),
      expiryTime: new Date(Date.now() + 10 * 60 * 1000),
      status: 'active',
    },
    {
      id: 'b2',
      customerName: 'Jane Doe',
      phone: '555-0202',
      vehicleNumber: 'XYZ-5678',
      slotId: 'B6',
      slotNumber: 'B-06',
      bookingTime: new Date(Date.now() - 20 * 60 * 1000),
      expiryTime: new Date(Date.now() - 5 * 60 * 1000),
      status: 'expired',
    },
  ],

  login: (email, _password, role) => {
    if (role === 'admin' && email === 'admin@park.com') {
      set({ currentUser: mockAdminUser });
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
      return true;
    }
    return false;
  },

  logout: () => set({ currentUser: null }),

  register: (name, email, _password) => {
    set({
      currentUser: { id: `user-${Date.now()}`, name, email, role: 'user' },
    });
    return true;
  },

  addBooking: (data) => {
    const now = new Date();
    const booking: Booking = {
      ...data,
      id: `b-${Date.now()}`,
      bookingTime: now,
      expiryTime: new Date(now.getTime() + BOOKING_DURATION_MS),
      status: 'active',
    };
    set((state) => ({
      bookings: [...state.bookings, booking],
      slots: state.slots.map((s) =>
        s.id === data.slotId ? { ...s, status: 'reserved' } : s
      ),
    }));
    return booking;
  },

  cancelBooking: (bookingId) => {
    const booking = get().bookings.find((b) => b.id === bookingId);
    if (!booking) return;
    set((state) => ({
      bookings: state.bookings.map((b) =>
        b.id === bookingId ? { ...b, status: 'cancelled' } : b
      ),
      slots: state.slots.map((s) =>
        s.id === booking.slotId ? { ...s, status: 'available' } : s
      ),
    }));
  },

  expireBooking: (bookingId) => {
    const booking = get().bookings.find((b) => b.id === bookingId);
    if (!booking) return;
    set((state) => ({
      bookings: state.bookings.map((b) =>
        b.id === bookingId ? { ...b, status: 'expired' } : b
      ),
      slots: state.slots.map((s) =>
        s.id === booking.slotId ? { ...s, status: 'available' } : s
      ),
    }));
  },

  /**
   * Merge API slot data. Slots that are locally 'reserved' (active bookings)
   * are never overridden by the API to preserve UI consistency.
   */
  syncSlotsFromApi: (apiSlots) => {
    const activeBookingSlotIds = new Set(
      get().bookings.filter(b => b.status === 'active').map(b => b.slotId)
    );
    set((state) => {
      // Build a map from the API response
      const apiMap = new Map(apiSlots.map(s => [s.id, s]));
      // If API returns different IDs/schema, replace entirely but protect reserved
      const useApiDirectly = apiSlots.length > 0 && apiMap.has(apiSlots[0].id);
      if (useApiDirectly) {
        return {
          slots: apiSlots.map(s =>
            activeBookingSlotIds.has(s.id) ? { ...s, status: 'reserved' as const } : s
          ),
        };
      }
      // Fallback: just update statuses on existing slots
      return {
        slots: state.slots.map(s => {
          const api = apiMap.get(s.id);
          if (!api) return s;
          if (activeBookingSlotIds.has(s.id)) return { ...s, status: 'reserved' as const };
          return { ...s, status: api.status };
        }),
      };
    });
  },
}));
