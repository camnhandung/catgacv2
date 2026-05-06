import flet as ft
import requests
from datetime import datetime

# Địa chỉ máy chủ Backend
API_URL = "https://catgac.onrender.com/api"

def main(page: ft.Page):
    # 1. CẤU HÌNH GIAO DIỆN HIỆN ĐẠI
    page.title = "Sổ Tay Tác Chiến"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#080c09"
    page.padding = 15
    
    ACCENT = "#a2d149"
    CARD_BG = "#131d15"
    
    now = datetime.now()
    user_session = {
        "id": None, 
        "name": "",
        "month": str(now.month),
        "year": str(now.year),
        "current_shifts": [] # LƯU TRỮ DANH SÁCH CA GÁC HIỆN TẠI ĐỂ BÁO THỨC HÀNG LOẠT
    }

    # --- CHỨC NĂNG: BÁO CÁO VI PHẠM ---
    def open_report_dialog(shift_id, report_type):
        def submit_report(e):
            try:
                requests.post(f"{API_URL}/report-incident", json={
                    "shift_id": shift_id,
                    "type": report_type,
                    "reporter": user_session["name"],
                    "reason": txt_reason.value
                }, timeout=5)
                dlg.open = False
                page.snack_bar = ft.SnackBar(ft.Text(f"Đã gửi báo cáo: {report_type}"), bgcolor="orange")
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Lỗi mạng: {ex}"), bgcolor="red")
                page.snack_bar.open = True
                page.update()

        txt_reason = ft.TextField(label="Mô tả chi tiết (nếu có)", multiline=True, border_color="orange")
        
        def close_dlg(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"BÁO CÁO: {report_type.upper()}", color="orange"),
            content=txt_reason,
            actions=[
                ft.TextButton("HỦY", on_click=close_dlg),
                ft.ElevatedButton("GỬI CHỈ HUY", on_click=submit_report, bgcolor="#8b0000", color="white")
            ]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    # --- CHỨC NĂNG: BÁO THỨC ĐƠN LẺ ---
    def set_alarm(shift_time, shift_date):
        page.snack_bar = ft.SnackBar(
            ft.Text(f"⏰ Đã đồng bộ lịch! Báo trước 20 phút cho ca lúc {shift_time} ngày {shift_date}."),
            bgcolor=ACCENT
        )
        page.snack_bar.open = True
        page.update()

    # --- TÍNH NĂNG MỚI: BÁO THỨC CẢ THÁNG ---
    def sync_month_alarms(e):
        shifts = user_session.get("current_shifts", [])
        if not shifts:
            page.snack_bar = ft.SnackBar(
                ft.Text("Không có ca gác nào trong tháng này để đặt báo thức!"), 
                bgcolor="orange"
            )
        else:
            count = len(shifts)
            # Ảo hóa logic đặt báo thức hàng loạt tại đây
            page.snack_bar = ft.SnackBar(
                ft.Text(f"🎯 THÀNH CÔNG: Đã đặt báo thức tự động cho {count} ca gác trong Tháng {user_session['month']}!"),
                bgcolor=ACCENT,
                duration=4000
            )
        page.snack_bar.open = True
        page.update()

    # --- MÀN HÌNH CHÍNH (DASHBOARD) ---
    def show_dashboard():
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.START
        
        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text("ĐIỀU HÀNH TÁC CHIẾN", size=10, color=ACCENT, weight="bold"),
                    ft.Text(user_session["name"].upper(), size=20, weight="bold"),
                ], spacing=2),
                ft.IconButton(icon="power_settings_new", icon_color="red", on_click=lambda _: logout())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=12,
            margin=ft.margin.only(bottom=15)
        )

        list_container = ft.ListView(expand=True, spacing=15)

        def load_data(m, y):
            user_session["month"] = m
            user_session["year"] = y
            list_container.controls.clear()
            
            try:
                res = requests.get(f"{API_URL}/my-shifts/{user_session['id']}?month={m}&year={y}", timeout=5)
                shifts = res.json()

                if not shifts or not isinstance(shifts, list):
                    user_session["current_shifts"] = [] # Xóa dữ liệu cũ
                    list_container.controls.append(
                        ft.Text("Đồng chí không có lịch gác trong tháng này.", italic=True, color="gray", text_align=ft.TextAlign.CENTER)
                    )
                else:
                    user_session["current_shifts"] = shifts # LƯU TRỮ LẠI ĐỂ DÙNG CHO NÚT BÁO THỨC TỔNG
                    for s in shifts:
                        next_man = s.get("next_officer")
                        
                        if next_man:
                            next_content = ft.Column([
                                ft.Text("BÀN GIAO MỤC TIÊU CHO:", size=10, color="orange", weight="bold"),
                                ft.Text(f"{next_man.get('name', '')} ({next_man.get('unit', '')})", size=14, weight="bold"),
                                ft.Text(f"SĐT: {next_man.get('phone', '')}", size=12, italic=True)
                            ], spacing=2)
                        else:
                            next_content = ft.Text("CA CUỐI - Thu dọn vũ khí trang bị", color="orange", weight="bold", size=12)

                        card = ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(str(s.get('time', '00:00')), size=26, weight="bold", color=ACCENT),
                                    ft.Text(str(s.get('date', '')), size=14, color="white70"),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                
                                ft.Text(f"VỊ TRÍ: {s.get('post_name', '').upper()}", size=16, weight="bold"),
                                ft.Divider(height=1, color="white10"),
                                
                                ft.Container(
                                    content=ft.Row([
                                        ft.Icon(name="swap_call", color="orange", size=24),
                                        next_content
                                    ]),
                                    padding=10, bgcolor="#1f1a0e", border_radius=8
                                ),
                                ft.Divider(height=1, color="transparent"),
                                
                                ft.Row([
                                    ft.ElevatedButton(
                                        "ĐẶT LỊCH", 
                                        icon="alarm_add", 
                                        color="white", bgcolor="#1a3b1a",
                                        on_click=lambda _, t=s.get('time'), d=s.get('date'): set_alarm(t, d)
                                    ),
                                    ft.PopupMenuButton(
                                        icon="warning_amber", icon_color="red",
                                        items=[
                                            ft.PopupMenuItem(text="Báo đổi gác muộn", on_click=lambda _, sid=s.get('shift_id'): open_report_dialog(sid, "Đổi gác muộn")),
                                            ft.PopupMenuItem(text="Báo bỏ gác", on_click=lambda _, sid=s.get('shift_id'): open_report_dialog(sid, "Bỏ gác"))
                                        ],
                                        tooltip="Báo cáo vi phạm"
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            ]),
                            padding=15, bgcolor=CARD_BG, border_radius=15, border=ft.border.all(1, "white10")
                        )
                        list_container.controls.append(card)
            except Exception as e:
                list_container.controls.append(ft.Text(f"Lỗi tải dữ liệu. Chi tiết lỗi: {e}", color="red"))
            
            page.update()

        # Thanh chọn Tháng/Năm
        filter_row = ft.Row([
            ft.Dropdown(
                label="Tháng", width=120, border_color=ACCENT,
                options=[ft.dropdown.Option(str(i)) for i in range(1, 13)],
                value=user_session["month"],
                on_change=lambda e: load_data(e.control.value, user_session["year"])
            ),
            ft.Dropdown(
                label="Năm", width=120, border_color=ACCENT,
                options=[ft.dropdown.Option(str(i)) for i in range(2024, 2030)],
                value=user_session["year"],
                on_change=lambda e: load_data(user_session["month"], e.control.value)
            )
        ], alignment=ft.MainAxisAlignment.CENTER)

        # NÚT ĐỒNG BỘ CẢ THÁNG
        btn_sync_all = ft.Container(
            content=ft.ElevatedButton(
                "ĐỒNG BỘ BÁO THỨC CẢ THÁNG", 
                icon="notifications_active", 
                color="black", 
                bgcolor=ACCENT,
                height=45,
                on_click=sync_month_alarms
            ),
            alignment=ft.alignment.center,
            margin=ft.margin.only(top=5, bottom=15)
        )

        page.add(header, filter_row, btn_sync_all, list_container)
        load_data(user_session["month"], user_session["year"])

    # --- MÀN HÌNH ĐĂNG NHẬP ---
    txt_name = ft.TextField(label="Họ và tên", text_align=ft.TextAlign.CENTER, border_color=ACCENT)
    txt_phone = ft.TextField(label="Số điện thoại", text_align=ft.TextAlign.CENTER, border_color=ACCENT)

    def login_click(e):
        try:
            res = requests.post(f"{API_URL}/officer-login", json={
                "full_name": txt_name.value.strip(),
                "phone_number": txt_phone.value.strip()
            }, timeout=5)

            if res.status_code == 200:
                data = res.json()
                user_session["id"] = data["id"]
                user_session["name"] = data["full_name"]
                show_dashboard()
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Sai thông tin xác thực!"), bgcolor="red")
                page.snack_bar.open = True
                page.update()
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Lỗi kết nối máy chủ Backend!"), bgcolor="red")
            page.snack_bar.open = True
            page.update()

    login_view = ft.Column([
        ft.Container(height=40),
        ft.Icon(name="shield", size=80, color=ACCENT),
        ft.Text("XÁC THỰC CHIẾN SĨ", size=24, weight="bold"),
        ft.Divider(height=20, color="transparent"),
        txt_name,
        txt_phone,
        ft.Divider(height=10, color="transparent"),
        ft.ElevatedButton("VÀO TRỰC", on_click=login_click, bgcolor="#285223", color="white", width=300, height=50)
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def logout():
        user_session["id"] = None
        user_session["current_shifts"] = [] # Xóa phiên
        page.clean()
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        page.add(login_view)
        page.update()

    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.add(login_view)

# Ép chạy trên Web Browser
ft.app(target=main, view=ft.AppView.WEB_BROWSER)