import json
import datetime
from database import engine, SessionLocal, Base
from models import ParkingSlot

def init_db():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

def seed_slots():
    print("Checking for existing parking slots...")
    db = SessionLocal()
    try:
        # Check if table is already seeded
        if db.query(ParkingSlot).count() > 0:
            print("Slots already exist in database. Skipping seeding.")
            return

        print("Seeding demo parking slots S1-S7...")
        # 960x540 design space polygons
        polygons = {
            "S1": [[50, 100], [200, 100], [200, 250], [50, 250]],
            "S2": [[220, 100], [370, 100], [370, 250], [220, 250]],
            "S3": [[390, 100], [540, 100], [540, 250], [390, 250]],
            "S4": [[560, 100], [710, 100], [710, 250], [560, 250]],
            "S5": [[50, 300], [200, 300], [200, 450], [50, 450]],
            "S6": [[220, 300], [370, 300], [370, 450], [220, 450]],
            "S7": [[390, 300], [540, 300], [540, 450], [390, 450]],
        }

        for slot_id, poly in polygons.items():
            print(f"Creating slot {slot_id}...")
            new_slot = ParkingSlot(
                id=slot_id,
                number=slot_id[1:],
                status="available",
                polygon=json.dumps(poly),
                polygon_configured=1,
                last_status_change_at=datetime.datetime.utcnow()
            )
            db.add(new_slot)
        
        db.commit()
        print("Seeding complete.")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    seed_slots()
