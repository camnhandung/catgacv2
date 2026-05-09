from typing import Optional
from datetime import datetime, date
from sqlmodel import Field, SQLModel, create_engine

# =========================
# 1. ĐƠN VỊ
# =========================
class Unit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    password: str
    role: str = Field(default="unit")


# =========================
# 2. VỌNG GÁC
# =========================
class GuardPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
# =========================
# 3. QUÂN SỐ
# =========================
class Officer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    phone_number: str = Field(index=True)
    unit_id: int = Field(foreign_key="unit.id")


# =========================
# 4. LỊCH GÁC TỔNG
# =========================
class MasterShift(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    guard_date: date
    shift_time: str

    post_id: int = Field(foreign_key="guardpost.id")
    unit_id: int = Field(foreign_key="unit.id")
# =========================
# 5. PHÂN CÔNG CHI TIẾT
# =========================
class ShiftAssignment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    master_shift_id: int = Field(foreign_key="mastershift.id")
    officer_id: int = Field(foreign_key="officer.id")


# =========================
# 6. BÁO CÁO VI PHẠM
# =========================
class IncidentReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    shift_id: int = Field(foreign_key="mastershift.id")

    report_type: str
    reporter_name: str
    reason: str = ""

    from datetime import timezone

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
# =========================
# KẾT NỐI SUPABASE
# =========================
import os

supabase_url = os.getenv("DATABASE_URL", "").strip()

if supabase_url.startswith("postgres://"):
    supabase_url = supabase_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

print("DATABASE_URL =", supabase_url)

engine = create_engine(
    supabase_url,
    echo=True,
    pool_pre_ping=True
)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
