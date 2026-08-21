from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum


class ConflictType(str, enum.Enum):
    TIME_OVERLAP = "time_overlap"
    SAME_DAY = "same_day"
    SAME_TIME = "same_time"


class DutyConflict(Base):
    __tablename__ = "duty_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    duty_id_1 = Column(Integer, ForeignKey("exam_duties.id"), nullable=False)
    duty_id_2 = Column(Integer, ForeignKey("exam_duties.id"), nullable=False)
    conflict_type = Column(Enum(ConflictType), nullable=False)
    resolved = Column(Integer, default=0)

    # Relationships
    lecturer = relationship("User", foreign_keys=[lecturer_id])
    duty1 = relationship("ExamDuty", foreign_keys=[duty_id_1])
    duty2 = relationship("ExamDuty", foreign_keys=[duty_id_2])