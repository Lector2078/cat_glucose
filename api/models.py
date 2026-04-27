import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ReadingSource(str, enum.Enum):
    manual = "manual"
    import_file = "import"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ParseStatus(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"


class Cat(Base):
    __tablename__ = "cats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    readings = relationship("GlucoseReading", back_populates="cat", cascade="all, delete-orphan")


class GlucoseReading(Base):
    __tablename__ = "glucose_readings"
    __table_args__ = (
        UniqueConstraint("cat_id", "reading_at", "glucose_value", name="uq_dedup_reading"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cat_id: Mapped[int] = mapped_column(ForeignKey("cats.id"), nullable=False, index=True)
    reading_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    glucose_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="mg/dL", nullable=False)
    context: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[ReadingSource] = mapped_column(Enum(ReadingSource), default=ReadingSource.manual, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    cat = relationship("Cat", back_populates="readings")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), default=ImportStatus.pending, nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    rows = relationship("ImportRow", back_populates="job", cascade="all, delete-orphan")


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"), nullable=False, index=True)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    parse_status: Mapped[ParseStatus] = mapped_column(Enum(ParseStatus), nullable=False)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("ImportJob", back_populates="rows")
