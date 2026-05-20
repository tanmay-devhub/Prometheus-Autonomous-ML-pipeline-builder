import json
import math
from typing import Any, Dict, Optional
from datetime import datetime

from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, Session

from regression.config import DATABASE_URL


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        return str(obj)

    def iterencode(self, o, _one_shot=False):
        return super().iterencode(self._sanitize(o), _one_shot)

    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._sanitize(v) for v in obj]
        return obj


Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class JobRecord(Base):
    __tablename__ = "regression_jobs"
    job_id = Column(String, primary_key=True)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(engine)


def save_job(job_id: str, state: Dict[str, Any]):
    with Session(engine) as session:
        record = session.get(JobRecord, job_id)
        state_json = json.dumps(state, cls=_SafeEncoder)
        if record:
            record.state_json = state_json
            record.updated_at = datetime.utcnow()
        else:
            record = JobRecord(job_id=job_id, state_json=state_json)
            session.add(record)
        session.commit()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with Session(engine) as session:
        record = session.get(JobRecord, job_id)
        if not record:
            return None
        return json.loads(record.state_json)


def list_jobs() -> list:
    with Session(engine) as session:
        records = session.query(JobRecord).order_by(JobRecord.created_at.desc()).limit(50).all()
        return [{"job_id": r.job_id, "created_at": str(r.created_at)} for r in records]
