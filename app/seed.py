from app.database import SessionLocal
from app.models import HCP

SAMPLE_HCPS = [
    {"name": "Dr. Sharma", "specialty": "Oncology", "institution": "Apollo Hospitals"},
    {"name": "Dr. Mehta", "specialty": "Cardiology", "institution": "Fortis Healthcare"},
    {"name": "Dr. Iyer", "specialty": "Endocrinology", "institution": "AIIMS Delhi"},
    {"name": "Dr. Khan", "specialty": "Neurology", "institution": "Max Healthcare"},
    {"name": "Dr. Rao", "specialty": "Oncology", "institution": "Tata Memorial Hospital"},
]


def seed_hcps():
    db = SessionLocal()
    try:
        if db.query(HCP).count() > 0:
            return
        for item in SAMPLE_HCPS:
            db.add(HCP(**item))
        db.commit()
    finally:
        db.close()
