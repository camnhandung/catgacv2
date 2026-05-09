from datetime import datetime, date
from sqlalchemy import func
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import date
import calendar
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import (
    engine,
    Unit,
    GuardPost,
    MasterShift,
    Officer,
    ShiftAssignment,
    IncidentReport
)
from datetime import datetime
import pytz

# Lấy giờ hiện tại theo múi giờ Việt Nam
vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
vancouver_now = datetime.now(vn_tz)

# Gửi biến này lên Supabase thay vì để Database tự tạo timestamp

app = FastAPI(title="Hệ thống Điều hành Cắt gác CQTM", version="3.1")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
def get_session():
    with Session(engine) as session:
        yield session
# ==========================================
# TRANG CHỦ CQTM
# ==========================================

@app.get("/")
def home():
    return FileResponse("static/index.html")

# --- 1. XÁC THỰC ---
class LoginRequest(BaseModel):
    name: str
    password: str

@app.post("/api/login")
def login(req: LoginRequest, session: Session = Depends(get_session)):
    unit = session.exec(select(Unit).where(Unit.name == req.name.lower(), Unit.password == req.password)).first()
    if not unit: raise HTTPException(401, "Sai Phiên hiệu hoặc Mật khẩu!")
    return {"id": unit.id, "name": unit.name.upper(), "role": unit.role}

# --- 2. QUẢN LÝ ĐƠN VỊ ---
class UnitCreate(BaseModel):
    name: str
    password: str

@app.post("/api/units")
def create_unit(unit: UnitCreate, session: Session = Depends(get_session)):
    if session.exec(select(Unit).where(Unit.name == unit.name)).first(): raise HTTPException(400, "Đơn vị đã tồn tại!")
    session.add(Unit(name=unit.name, password=unit.password, role="unit"))
    session.commit()
    return {"message": f"Đã thêm đơn vị {unit.name.upper()}"}

@app.get("/api/units")
def get_all_units(session: Session = Depends(get_session)):
    return session.exec(select(Unit)).all()

@app.delete("/api/units/{unit_id}")
def delete_unit(unit_id: int, session: Session = Depends(get_session)):
    unit = session.get(Unit, unit_id)
    if unit.role == 'admin': raise HTTPException(400, "Không thể xóa CQTM!")
    try:
        session.delete(unit)
        session.commit()
        return {"message": "Đã xóa đơn vị"}
    except: raise HTTPException(400, "Đơn vị đang có ca gác!")

@app.put("/api/units/{unit_id}/password")
def update_unit_password(unit_id: int, data: dict, session: Session = Depends(get_session)):
    unit = session.get(Unit, unit_id)
    unit.password = data.get("password")
    session.add(unit)
    session.commit()
    return {"message": "Đã đổi mật khẩu thành công!"}

# --- 3. QUẢN LÝ VỌNG GÁC ---
class GuardPostCreate(BaseModel):
    name: str

@app.post("/api/guard-posts")
def create_guard_post(post: GuardPostCreate, session: Session = Depends(get_session)):
    if session.exec(select(GuardPost).where(GuardPost.name == post.name)).first(): raise HTTPException(400, "Vọng này đã có!")
    session.add(GuardPost(name=post.name))
    session.commit()
    return {"message": f"Đã thiết lập Vọng: {post.name}"}

@app.get("/api/guard-posts")
def get_all_guard_posts(session: Session = Depends(get_session)):
    return session.exec(select(GuardPost)).all()

@app.delete("/api/guard-posts/{post_id}")
def delete_post(post_id: int, session: Session = Depends(get_session)):
    try:
        session.delete(session.get(GuardPost, post_id))
        session.commit()
        return {"message": "Đã hủy bỏ vọng"}
    except: raise HTTPException(400, "Vọng đang có lịch!")

# --- 4. CẮT GÁC (ADMIN) & XEM LỊCH SỬ ---
class MasterShiftCreate(BaseModel):
    guard_date: date
    shift_time: str
    post_id: int
    unit_id: int

@app.post("/api/master-shifts/bulk")
def create_bulk_master_shifts(shifts: List[MasterShiftCreate], session: Session = Depends(get_session)):
    for shift in shifts:
        existing = session.exec(select(MasterShift).where(
            MasterShift.guard_date == shift.guard_date, MasterShift.shift_time == shift.shift_time, MasterShift.post_id == shift.post_id
        )).first()
        if existing:
            # THUẬT TOÁN BẢO VỆ: Nếu CQTM đổi đơn vị gác, phải tự động XÓA danh sách tên chiến sĩ của đơn vị cũ
            if existing.unit_id != shift.unit_id:
                old_assign = session.exec(select(ShiftAssignment).where(ShiftAssignment.master_shift_id == existing.id)).first()
                if old_assign:
                    session.delete(old_assign)
            
            existing.unit_id = shift.unit_id
            session.add(existing)
        else:
            session.add(MasterShift(guard_date=shift.guard_date, shift_time=shift.shift_time, post_id=shift.post_id, unit_id=shift.unit_id))
    session.commit()
    return {"message": f"ĐÃ PHÁT LỆNH / CẬP NHẬT {len(shifts)} CA GÁC!"}

@app.get("/api/master-shifts")
def get_master_shifts(year: int, month: int, post_id: int, session: Session = Depends(get_session)):
    start_date = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end_date = date(year, month, last_day)
    return session.exec(select(MasterShift).where(MasterShift.post_id == post_id, MasterShift.guard_date >= start_date, MasterShift.guard_date <= end_date)).all()

# --- 5. BÁO CÁO MA TRẬN & ĐƠN VỊ ĐIỀN TÊN ---
@app.get("/api/reports/matrix")
def get_matrix_report(year: int, month: int, post_id: int, session: Session = Depends(get_session)):
    start_date = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end_date = date(year, month, last_day)

    statement = select(MasterShift, Unit).join(Unit, MasterShift.unit_id == Unit.id).where(
        MasterShift.post_id == post_id, MasterShift.guard_date >= start_date, MasterShift.guard_date <= end_date
    )
    results = session.exec(statement).all()

    data = []
    for shift, unit in results:
        assign = session.exec(select(ShiftAssignment, Officer).join(Officer, ShiftAssignment.officer_id == Officer.id).where(ShiftAssignment.master_shift_id == shift.id)).first()
        data.append({
            "shift_id": shift.id,
            "guard_date": shift.guard_date.strftime("%Y-%m-%d"),
            "shift_time": shift.shift_time,
            "unit_id": unit.id,
            "unit_name": unit.name.upper(),
            "officer_id": assign[1].id if assign else "",
            "officer_name": assign[1].full_name if assign else ""
        })
    return data

class AssignShiftReq(BaseModel):
    master_shift_id: int
    officer_id: int

@app.post("/api/assign-shift/bulk")
def bulk_assign_shifts(reqs: List[AssignShiftReq], session: Session = Depends(get_session)):
    # Bộ nhớ tạm để kiểm tra xem đơn vị có lỡ gửi trùng 1 người trong cùng 1 lần bấm lưu không
    tracker = {}
    
    for req in reqs:
        # Lấy thông tin ca gác (ngày, giờ, vọng) từ MasterShift
        shift = session.get(MasterShift, req.master_shift_id)
        if not shift: continue
        
        # 1. KIỂM TRA TRÙNG TRONG CHÍNH BẢNG ĐANG GỬI LÊN
        check_key = f"{shift.guard_date}_{shift.shift_time}_{req.officer_id}"
        if check_key in tracker:
            officer = session.get(Officer, req.officer_id)
            raise HTTPException(400, f"LỖI PHÂN THÂN: Đ/c {officer.full_name} bị xếp gác 2 lần vào ca {shift.shift_time} ngày {shift.guard_date.strftime('%d/%m/%Y')}!")
        tracker[check_key] = True

        # 2. KIỂM TRA TRÙNG VỚI DỮ LIỆU ĐÃ CÓ DƯỚI ĐÁM MÂY (CSDL)
        conflict = session.exec(
            select(MasterShift).join(ShiftAssignment).where(
                ShiftAssignment.officer_id == req.officer_id,
                MasterShift.guard_date == shift.guard_date,
                MasterShift.shift_time == shift.shift_time,
                MasterShift.id != req.master_shift_id # Bỏ qua chính ca đang sửa
            )
        ).first()
        
        if conflict:
            officer = session.get(Officer, req.officer_id)
            post = session.get(GuardPost, conflict.post_id)
            raise HTTPException(400, f"LỖI TRÙNG LỊCH: Đ/c {officer.full_name} đang mắc gác tại '{post.name.upper()}' vào ca {shift.shift_time} ngày {shift.guard_date.strftime('%d/%m/%Y')}. Yêu cầu đổi người!")

        # 3. NẾU AN TOÀN, TIẾN HÀNH LƯU
        existing = session.exec(select(ShiftAssignment).where(ShiftAssignment.master_shift_id == req.master_shift_id)).first()
        if existing:
            existing.officer_id = req.officer_id
            session.add(existing)
        else:
            session.add(ShiftAssignment(master_shift_id=req.master_shift_id, officer_id=req.officer_id))
            
    session.commit()
    return {"message": "ĐÃ CẬP NHẬT LÊN CQTM THÀNH CÔNG!"}

# --- 6. QUÂN SỐ CỦA ĐƠN VỊ ---
class OfficerCreate(BaseModel):
    full_name: str
    phone_number: str
    unit_id: int

@app.post("/api/officers")
def create_officer(officer: OfficerCreate, session: Session = Depends(get_session)):
    session.add(Officer(full_name=officer.full_name, phone_number=officer.phone_number, unit_id=officer.unit_id))
    session.commit()
    return {"message": f"Đã thêm đ/c {officer.full_name}!"}

@app.get("/api/officers/{unit_id}")
def get_officers(unit_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Officer).where(Officer.unit_id == unit_id)).all()

@app.delete("/api/officers/{officer_id}")
def delete_officer(officer_id: int, session: Session = Depends(get_session)):
    try:
        session.delete(session.get(Officer, officer_id))
        session.commit()
        return {"message": "Đã gạch tên cán bộ"}
    except: raise HTTPException(400, "Đang có lịch gác, không thể xóa!")
# --- 8. API DÀNH RIÊNG CHO CHIẾN SĨ (MOBILE) ---

# Đăng nhập bằng Họ tên + Số điện thoại
@app.post("/api/officer-login", tags=["Mobile"])
def officer_login(data: dict, session: Session = Depends(get_session)):
    # Lấy dữ liệu và loại bỏ khoảng trắng thừa
    name = data.get("full_name", "").strip()
    phone = data.get("phone_number", "").strip()
    
    # Sử dụng func.lower() để so sánh không phân biệt hoa thường
    officer = session.exec(select(Officer).where(
        func.lower(Officer.full_name) == name.lower(), 
        Officer.phone_number == phone
    )).first()
    
    if not officer:
        # Nếu không tìm thấy, trả về lỗi 401
        raise HTTPException(401, "Thông tin không chính xác hoặc chưa được đăng ký!")
        
    return {"id": officer.id, "full_name": officer.full_name, "unit_id": officer.unit_id}

# Lấy lịch gác cá nhân + Thông tin người gác sau
# --- CẬP NHẬT API LẤY LỊCH CÁ NHÂN CÓ LỌC THÁNG/NĂM ---
@app.get("/api/my-shifts/{officer_id}", tags=["Mobile"])
def get_my_shifts(officer_id: int, month: int, year: int, session: Session = Depends(get_session)):
    try:
        # Lấy lịch của người gác
        statement = select(ShiftAssignment, MasterShift).join(MasterShift).where(
            ShiftAssignment.officer_id == officer_id
        ).order_by(MasterShift.guard_date, MasterShift.shift_time)
        
        all_my_assigns = session.exec(statement).all()
        results = []
        
        for assign, m_shift in all_my_assigns:
            try:
                raw_date = m_shift.guard_date
                if not raw_date:
                    continue
                
                if isinstance(raw_date, str):
                    date_str = raw_date.split(" ")[0].split("T")[0]
                    shift_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                else:
                    shift_date = raw_date

                if shift_date.month == int(month) and shift_date.year == int(year):
                    
                    post = session.get(GuardPost, m_shift.post_id) if m_shift.post_id else None
                    post_name = post.name if post else "Vọng chưa xác định"

                    next_info = None
                    try:
                        next_shift = session.exec(select(MasterShift).where(
                            MasterShift.post_id == m_shift.post_id,
                            MasterShift.guard_date >= m_shift.guard_date,
                            MasterShift.id != m_shift.id
                        ).order_by(MasterShift.guard_date, MasterShift.shift_time)).first()
                        
                        if next_shift:
                            # ==========================================
                            # ĐÂY CHÍNH LÀ NƠI ĐÃ ĐƯỢC VÁ LỖI 500
                            # Chỉ định rõ ràng: ShiftAssignment.officer_id == Officer.id
                            # ==========================================
                            n_assign = session.exec(
                                select(ShiftAssignment, Officer, Unit)
                                .join(Officer, ShiftAssignment.officer_id == Officer.id) 
                                .join(Unit, Officer.unit_id == Unit.id)
                                .where(ShiftAssignment.master_shift_id == next_shift.id)
                            ).first()
                            
                            if n_assign:
                                next_info = {
                                    "name": n_assign[1].full_name,
                                    "unit": n_assign[2].name.upper(),
                                    "phone": n_assign[1].phone_number
                                }
                    except Exception as next_err:
                        print(f"[-] Lỗi tìm ca sau cho ID {m_shift.id}: {next_err}")

                    results.append({
                        "shift_id": m_shift.id,
                        "date": shift_date.strftime("%d/%m/%Y"),
                        "time": m_shift.shift_time,
                        "post_name": post_name,
                        "next_officer": next_info
                    })
            except Exception as loop_err:
                print(f"[-] Lỗi xử lý ca gác ID {m_shift.id}: {loop_err}")
                continue 
                
        return results
        
    except Exception as e:
        import traceback
        print("====== LỖI BACKEND NGHIÊM TRỌNG ======")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Lỗi máy chủ nghiêm trọng")
        
# --- API BÁO CÁO VI PHẠM (MUỘN/BỎ GÁC) ---
# ==========================================
# ADMIN RESET MẬT KHẨU
# ==========================================

class ResetPasswordRequest(BaseModel):
    password: str


@app.put("/api/admin/reset-password/{unit_id}")
def admin_reset_password(
    unit_id: int,
    req: ResetPasswordRequest,
    session: Session = Depends(get_session)
):

    unit = session.get(Unit, unit_id)

    if not unit:
        raise HTTPException(404, "Không tìm thấy đơn vị")

    unit.password = req.password

    session.add(unit)
    session.commit()

    return {
        "message": f"Đã reset mật khẩu cho {unit.name.upper()}"
    }
# ==========================================
# GỬI BÁO CÁO VI PHẠM
# ==========================================

class IncidentRequest(BaseModel):
    shift_id: int
    type: str
    reporter: str
    reason: str = ""


@app.post("/api/report-incident")
def report_incident(
    data: IncidentRequest,
    session: Session = Depends(get_session)
):

    report = IncidentReport(
        shift_id=data.shift_id,
        report_type=data.type,
        reporter_name=data.reporter,
        reason=data.reason
    )

    session.add(report)
    session.commit()

    return {
        "message": "Đã gửi báo cáo vi phạm"
    }
@app.delete("/api/incidents/{incident_id}")
def delete_incident(incident_id: int):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM incidents WHERE id=%s",
        (incident_id,)
    )

    conn.commit()

    return {"success": True}

# ==========================================
# ADMIN XEM TOÀN BỘ VI PHẠM
# ==========================================

@app.get("/api/incidents")
def get_incidents(
    month: Optional[int] = None,
    year: Optional[int] = None,
    session: Session = Depends(get_session)
):

    reports = session.exec(
        select(IncidentReport)
        .order_by(IncidentReport.created_at.desc())
    ).all()

    results = []

    shift_times = [
        "00.00-02.00",
        "02.00-04.00",
        "04.00-06.00",
        "06.00-11.00",
        "11.00-14.00",
        "14.00-18.00",
        "18.00-22.00",
        "22.00-00.00"
    ]

    for r in reports:

        if month and r.created_at.month != month:
            continue

        if year and r.created_at.year != year:
            continue

        shift = session.get(MasterShift, r.shift_id)

        post_name = "Không rõ"
        report_shift = "?"
        violation_shift = ""

        if shift:

            report_shift = shift.shift_time

            try:
                idx = shift_times.index(report_shift)

                if idx > 0:
                    violation_shift = shift_times[idx - 1]

            except:
                pass

            post = session.get(GuardPost, shift.post_id)

            if post:
                post_name = post.name

        results.append({
            "id": r.id,
            "type": r.report_type,
            "reporter": r.reporter_name,
            "reason": r.reason,
            "created_at": r.created_at.strftime("%d/%m/%Y %H:%M"),
            "post_name": post_name,
            "shift_time": report_shift,
            "report_shift": report_shift,
            "violation_shift": violation_shift
        })

    return results
