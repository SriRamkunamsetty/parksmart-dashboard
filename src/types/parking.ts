export type SlotStatus = 'available' | 'reserved' | 'occupied';
export type UserRole = 'user' | 'admin';

export interface ParkingSlot {
  id: string;
  number: string;
  status: SlotStatus;
  floor: string;
  polygon?: string;
  polygon_configured?: boolean;
  heatmap_count?: number;
}

export interface Booking {
  id: string;
  customerName: string;
  phone: string;
  vehicleNumber: string;
  slotId: string;
  slotNumber: string;
  bookingTime: Date;
  expiryTime: Date;
  status: 'active' | 'expired' | 'cancelled' | 'occupied';
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}
