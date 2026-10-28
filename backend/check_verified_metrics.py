import sys
sys.path.insert(0, '.')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.placement_offer_service import placement_offer_service

DATABASE_URL = 'postgresql://edumatrix:edumatrix123@localhost:5432/edumatrix'
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

metrics = placement_offer_service.get_placement_accounting_metrics(db)
print('Verified Metrics:', metrics)

db.close()