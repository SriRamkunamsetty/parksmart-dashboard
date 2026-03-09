# Smart Parking Monitoring and Booking System

## Description
This system uses Computer Vision (YOLOv8) and FastAPI to analyze CCTV parking lot footage and determine parking slot availability in real-time.

The application provides:
- Admin tools for configuring parking slots using polygon coordinates
- Real-time parking monitoring
- Customer parking slot booking
- WebSocket-based real-time updates
- Heatmap analytics for slot usage

The system detects vehicles in video streams and determines slot occupancy using polygon intersection and centroid logic.

## Tech Stack

### Frontend
- React
- Vite
- TypeScript
- TailwindCSS
- Zustand state management
- WebSockets

### Backend
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- APScheduler

### AI / Computer Vision
- YOLOv8 (Ultralytics)
- OpenCV

### Other Tools
- Python Virtual Environment
- Node.js
- npm
- MJPEG video streaming

## Core Features

### AI Parking Detection
The system analyzes CCTV footage using YOLOv8.

Detected vehicle classes:
- Car
- Motorcycle
- Bus
- Truck

Parking slot occupancy is determined using:
- Centroid inside polygon
- Intersection Over Union (IoU > 0.25)

Temporal smoothing ensures a vehicle must be detected for 3 consecutive frames before confirming occupancy.

### Detection Worker System
The backend includes a `DetectionManager` that spawns multiple `CameraWorker` threads.

Responsibilities:
- Read frames from video streams
- Run YOLO detection
- Evaluate parking slot occupancy
- Update database
- Broadcast WebSocket events

Detection runs every few frames to optimize performance.

### Real-Time WebSocket Updates
Slot status updates are broadcast to all connected clients.

Example event:
```json
{
  "event": "slot_update",
  "slot_id": 12,
  "status": "occupied",
  "timestamp": "ISO_TIME"
}
```
Frontend dashboards update instantly without polling.

### Admin Dashboard
Admin interface allows:
- Live CCTV monitoring
- Parking slot polygon configuration
- Slot editing and deletion
- Heatmap analytics of slot usage

Admins define parking slots by clicking 4 points on the video frame to create polygon coordinates.

### Customer Dashboard
Customers can:
- View live parking slot availability
- Book available slots
- Cancel bookings
- View booking history

Slot colors:
- 🟢 **Green** → Vacant
- 🟡 **Yellow** → Reserved
- 🔴 **Red** → Occupied

### Booking System
Slot lifecycle:
`Vacant` → `Reserved` → `Occupied`

Reservations expire automatically after 10 minutes if the vehicle does not arrive.
A background scheduler checks for expired reservations.

## System Architecture

### Architecture Flow

```text
CCTV Camera
      ↓
CameraWorker (YOLO Detection)
      ↓
Slot Occupancy Engine
      ↓
SQLite Database
      ↓
FastAPI API Server
      ↓
WebSocket Broadcast
      ↓
React Frontend
```

- **CameraWorker**: Captures video frames and runs YOLOv8 inference. Calculates polygon intersection and centroid tracking.
- **Slot Occupancy Engine**: Applies temporal smoothing (3 consecutive detections) and maintains slot states.
- **FastAPI API Server**: Provides REST endpoints for slot management, booking operations, and state querying.
- **WebSocket Broadcast**: Dispatches JSON events globally to all connected clients instantly.
- **React Frontend**: Subscribes to WebSockets to dynamically re-render maps and UI without polling.

## Database Schema

### Users
- `id`
- `name`
- `email`
- `password_hash`
- `role`
- `created_at`

### ParkingSlots
- `id`
- `slot_number`
- `polygon`
- `status`
- `heatmap_count`
- `last_updated`

### Bookings
- `id`
- `user_id`
- `slot_id`
- `status`
- `booking_time`
- `expiry_time`

## Installation Guide

### Clone Project
```bash
git clone <repo>
cd parking-ai-system
```

### Backend Setup
```bash
cd backend
python -m venv venv
```

Activate virtual environment:
- **Windows**: `venv\Scripts\activate`
- **Mac/Linux**: `source venv/bin/activate`

```bash
pip install -r requirements.txt
```

Start backend:
```bash
uvicorn main:app --reload
```

- Backend runs on: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: `http://localhost:5173`

## Running the System

1. Start backend server
2. Start frontend dev server
3. Open Admin Dashboard (`/admin`)
4. Configure parking slot polygons
5. Upload parking video feed
6. Monitor slot occupancy in real time

Customers can then open the Customer Dashboard (`/dashboard`) and book parking slots interactively.

## Project Structure

```text
parking-ai-system
│
├── backend
│   ├── main.py
│   ├── worker.py
│   ├── models.py
│   ├── routes
│   │   ├── booking.py
│   │   ├── slots.py
│   │   └── auth.py
│
├── frontend
│   ├── src
│   │   ├── pages
│   │   │   ├── AdminDashboard.tsx
│   │   │   └── UserDashboard.tsx
│   │   ├── store
│   │   └── components
│
└── database
    └── parking.db
```
