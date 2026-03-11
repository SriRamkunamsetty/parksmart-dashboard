import logging
import json
from datetime import datetime, timezone
from database import SessionLocal
from models import SystemEvent

# Configure standard logging to console
# We use a format that works even if 'category' is missing from the extra dict
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s"
)

def log_event(category: str, message: str, meta_data: dict = None):
    """
    Centralized structured logging with persistence and console output.
    Categories: startup, worker, stream, detection, slot_state, system
    """
    # Console output with category prefix
    print(f"[{category.upper()}] {message}")

    # Persistence to DB
    db = SessionLocal()
    try:
        event = SystemEvent(
            event_type=category,
            message=message,
            meta_data=json.dumps(meta_data) if meta_data else None,
            timestamp=datetime.now(timezone.utc) # Fixed: models.py uses timestamp
        )
        db.add(event)
        db.commit()
    except Exception as e:
        # Standard logging as fallback
        logging.error(f"Failed to persist log event {category}: {e}")
    finally:
        db.close()
