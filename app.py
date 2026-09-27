import os
import socket
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# ==============================================================================
# CẤU HÌNH STREAMLIT
# ==============================================================================

st.set_page_config(
    page_title="Order Nhà Hàng",
    page_icon="🍽️",
    layout="wide"
)

# ==============================================================================
# KẾT NỐI AIVEN MYSQL
# ==============================================================================

# Khuyến nghị: Ưu tiên lấy cấu hình từ st.secrets nếu triển khai web (Streamlit Cloud)
# Nếu không tìm thấy secrets, sẽ fallback về giá trị cấu hình trực tiếp bên dưới.

try:
    DB_USER = st.secrets["mysql"]["user"]
    DB_PASSWORD = st.secrets["mysql"]["password"]
    DB_HOST = st.secrets["mysql"]["host"]
    DB_PORT = st.secrets["mysql"]["port"]
    DB_NAME = st.secrets["mysql"]["database"]
except Exception:
    # Cấu hình trực tiếp trên máy local (Lưu ý: Thay đổi password nếu đổi trên Aiven)
    DB_USER = "avnadmin" # sửa lại user
    DB_PASSWORD = "AVNS_IDUK3EMO9eJyNG6A4kI" # sửa lại password
    DB_HOST = "mysql-2f17a02b-vynguyen230505-0ba2.k.aivencloud.com" # sửa lại host
    DB_PORT = 15632 # sửa lại port
    DB_NAME = "defaultdb"

# ------------------------------------------------------------------
# Làm sạch dữ liệu kết nối
# ------------------------------------------------------------------

DB_USER = str(DB_USER).strip()
DB_PASSWORD = str(DB_PASSWORD).strip()
DB_HOST = str(DB_HOST).strip()
DB_NAME = str(DB_NAME).strip()
DB_PORT = int(DB_PORT)

# ==============================================================================
# DEBUG KẾT NỐI
# ==============================================================================

with st.expander("🔧 Kiểm tra kết nối Aiven", expanded=False):
    st.write("**HOST:**", repr(DB_HOST))
    st.write("**PORT:**", repr(DB_PORT))
    st.write("**DATABASE:**", repr(DB_NAME))
    st.write("**USER:**", repr(DB_USER))

    if DB_HOST != DB_HOST.strip():
        st.error("HOST đang có khoảng trắng ở đầu hoặc cuối. Đã tự động loại bỏ.")
    else:
        st.success("HOST không có khoảng trắng.")

    if st.button("🔍 Kiểm tra DNS Aiven"):
        try:
            ip_address = socket.gethostbyname(DB_HOST)
            st.success(f"DNS OK - Host Aiven trỏ tới IP: {ip_address}")
        except Exception as e:
            st.error(f"DNS ERROR: Không phân giải được hostname Aiven.\n\n{e}")

# ==============================================================================
# TẠO DATABASE URL
# ==============================================================================

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

# ==============================================================================
# DATABASE ENGINE
# ==============================================================================

@st.cache_resource
def get_db_engine():
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 15},
        pool_size=5,
        max_overflow=5,
    )
    return engine

# ==============================================================================
# KIỂM TRA KẾT NỐI MYSQL
# ==============================================================================

def test_database_connection():
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True, "Kết nối Aiven MySQL thành công!"
    except Exception as e:
        return False, str(e)

# ==============================================================================
# TẠO BẢNG ORDERS
# ==============================================================================

def init_db():
    engine = get_db_engine()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        created_at DATETIME NOT NULL,
        table_name VARCHAR(50) NOT NULL,
        item_name VARCHAR(100) NOT NULL,
        quantity INT NOT NULL,
        total_price DECIMAL(12, 2) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(create_table_query)

# ==============================================================================
# KHỞI TẠO DATABASE
# ==============================================================================

db_connected = False
try:
    init_db()
    db_connected = True
except Exception as e:
    db_connected = False
    st.error("❌ Không thể kết nối Aiven MySQL.")
    st.code(str(e), language="text")
    st.warning("Kiểm tra lại HOST, PORT, USER, PASSWORD và DATABASE trong Aiven.")

# ==============================================================================
# MENU NHÀ HÀNG
# ==============================================================================

menu = {
    "Đồ ăn": {
        "Pizza Hải Sản": 150000,
        "Mì Ý Bò Bằm": 95000,
        "Burger Gà": 65000,
        "Salad Trộn": 50000,
        "Bít tết Bò Mỹ": 250000,
        "Sườn nướng BBQ": 180000,
        "Cánh gà chiên mắm": 75000,
        "Lẩu cá diêu hồng": 200000,
        "Lẩu Thái hải sản": 300000,
    },
    "Thức uống": {
        "Coca Cola": 20000,
        "Trà Đào Cam Sả": 35000,
        "Cà Phê Sữa": 25000,
        "Nước Suối": 10000,
        "Sinh tố Bơ": 45000,
        "Nước ép cam": 40000,
        "Mojito chanh dây": 55000,
        "Bia Heineken": 30000,
    },
}

# ==============================================================================
# SESSION STATE
# ==============================================================================

if "order_dict" not in st.session_state:
    st.session_state.order_dict = {}

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# ==============================================================================
# HÀM ĐỌC LỊCH SỬ TỪ MYSQL
# ==============================================================================

def load_history_from_db():
    try:
        engine = get_db_engine()
        df = pd.read_sql(
            text(
                """
                SELECT
                    id,
                    created_at,
                    table_name,
                    item_name,
                    quantity,
                    total_price
                FROM orders
                ORDER BY created_at DESC
                """
            ),
            engine
        )

        if not df.empty:
            df.rename(
                columns={
                    "id": "ID",
                    "created_at": "Thời gian",
                    "table_name": "Bàn",
                    "item_name": "Tên món",
                    "quantity": "Số lượng",
                    "total_price": "Thành tiền",
                },
                inplace=True
            )
        return df
    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu từ Aiven: {e}")
        return pd.DataFrame()

# ==============================================================================
# SIDEBAR
# ==============================================================================

st.sidebar.title("🍽️ QUẢN LÝ NHÀ HÀNG")
page = st.sidebar.radio("📋 Chọn trang hệ thống", ["🍽️ Order", "🔑 Admin"])

# ==============================================================================
# TRANG ORDER
# ==============================================================================

if page == "🍽️ Order":
    st.title("🍽️ Hệ thống Order Nhà Hàng_Y Gi Bi Teo")
    st.caption("Ghi nhận order nhanh chóng và lưu dữ liệu trực tiếp lên Aiven MySQL")

    if db_connected:
        st.success("🟢 Aiven MySQL: ĐÃ KẾT NỐI")
    else:
        st.error("🔴 Aiven MySQL: CHƯA KẾT NỐI")

    st.markdown("---")

    col1, col2 = st.columns([1, 1.3])

    # --------------------------------------------------------------
    # CỘT CHỌN MÓN
    # --------------------------------------------------------------
    with col1:
        st.subheader("🍔 Chọn món")

        table_number = st.selectbox(
            "🪑 Chọn số bàn",
            [f"Bàn {i}" for i in range(1, 21)]
        )

        category = st.selectbox("📂 Chọn loại", list(menu.keys()))
        item = st.selectbox("🍽️ Chọn món", list(menu[category].keys()))
        price = menu[category][item]

        st.write(f"**Đơn giá:** {price:,.0f} VNĐ")

        quantity = st.number_input(
            "🔢 Số lượng", min_value=1, step=1, value=1
        )

        if st.button("➕ Thêm vào giỏ", use_container_width=True):
            if item in st.session_state.order_dict:
                st.session_state.order_dict[item]["Số lượng"] += quantity
                st.session_state.order_dict[item]["Thành tiền"] = (
                    st.session_state.order_dict[item]["Số lượng"] * price
                )
                st.session_state.order_dict[item]["Bàn"] = table_number
            else:
                st.session_state.order_dict[item] = {
                    "Bàn": table_number,
                    "Tên món": item,
                    "Đơn giá": price,
                    "Số lượng": quantity,
                    "Thành tiền": price * quantity,
                }

            st.success(f"Đã thêm {item} vào giỏ!")
            st.rerun()

    # --------------------------------------------------------------
    # CỘT GIỎ HÀNG
    # --------------------------------------------------------------
    with col2:
        st.subheader("🛒 Giỏ hàng hiện tại")

        if st.session_state.order_dict:
            df = pd.DataFrame.from_dict(
                st.session_state.order_dict, orient="index"
            )

            st.dataframe(
                df[["Bàn", "Tên món", "Đơn giá", "Số lượng", "Thành tiền"]],
                use_container_width=True,
                hide_index=True
            )

            # Tính tiền
            tam_tinh = df["Thành tiền"].sum()
            giam_gia = tam_tinh * 0.05 if tam_tinh > 1_000_000 else 0
            tong_thanh_toan = tam_tinh - giam_gia

            st.write(f"**Tạm tính:** {tam_tinh:,.0f} VNĐ")
            if giam_gia > 0:
                st.write(f"**Giảm giá 5%:** -{giam_gia:,.0f} VNĐ")

            st.metric("💰 Tổng thanh toán", f"{tong_thanh_toan:,.0f} VNĐ")
            st.markdown("---")

            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("💳 Thanh toán", use_container_width=True):
                    if not db_connected:
                        st.error("Không thể thanh toán vì Aiven MySQL chưa kết nối.")
                    else:
                        now_time = datetime.now()
                        records = []

                        for row in st.session_state.order_dict.values():
                            records.append({
                                "created_at": now_time,
                                "table_name": row["Bàn"],
                                "item_name": row["Tên món"],
                                "quantity": row["Số lượng"],
                                "total_price": row["Thành tiền"],
                            })

                        try:
                            engine = get_db_engine()
                            df_to_save = pd.DataFrame(records)
                            df_to_save.to_sql(
                                "orders",
                                engine,
                                if_exists="append",
                                index=False
                            )

                            st.success("✅ Thanh toán thành công!")
                            st.success("Dữ liệu đã được lưu vào Aiven MySQL.")

                            st.session_state.order_dict = {}
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Lỗi lưu dữ liệu: {e}")

            with col_btn2:
                if st.button("🗑️ Xóa toàn bộ giỏ", use_container_width=True):
                    st.session_state.order_dict = {}
                    st.rerun()

        else:
            st.info("🛒 Giỏ hàng đang trống. Hãy chọn món bên trái để lên đơn.")

# ==============================================================================
# TRANG ADMIN
# ==============================================================================

elif page == "🔑 Admin":
    st.title("🔑 Trang Quản Trị & Phân Tích Doanh Thu")

    # --------------------------------------------------------------
    # LOGIN ADMIN
    # --------------------------------------------------------------
    if not st.session_state.admin_logged_in:
        with st.form("admin_login_form"):
            password = st.text_input(
                "🔐 Nhập mật khẩu quản trị", type="password"
            )
            login_submitted = st.form_submit_button("🔑 Đăng nhập")

            if login_submitted:
                if password == "123456":
                    st.session_state.admin_logged_in = True
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else:
                    st.error("❌ Mật khẩu không chính xác!")

        st.warning("Vui lòng nhập mật khẩu quản trị.")
        st.stop()

    # --------------------------------------------------------------
    # ADMIN ĐÃ ĐĂNG NHẬP
    # --------------------------------------------------------------
    col_header_title, col_header_btn = st.columns([4, 1])

    with col_header_title:
        st.success("🟢 Xác thực quyền Quản trị viên thành công!")

    with col_header_btn:
        if st.button("🔒 Đăng xuất"):
            st.session_state.admin_logged_in = False
            st.rerun()

    # --------------------------------------------------------------
    # TABS ADMIN
    # --------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "📋 Danh sách thực đơn",
        "💰 Doanh thu & Nhật ký giao dịch",
        "📊 Thống kê & Phân tích",
    ])

    # TAB 1 - MENU
    with tab1:
        st.subheader("🍽️ Menu hiện hành của nhà hàng")
        data = []
        for category_name in menu:
            for item_name, price in menu[category_name].items():
                data.append([category_name, item_name, price])

        df_menu = pd.DataFrame(
            data, columns=["Phân loại", "Tên món", "Đơn giá (VNĐ)"]
        )
        st.dataframe(df_menu, use_container_width=True, hide_index=True)

    # TAB 2 - DOANH THU
    with tab2:
        st.subheader("💰 Doanh thu & Hóa đơn thực tế")
        df_history = load_history_from_db()

        if not df_history.empty:
            tong_doanh_thu = df_history["Thành tiền"].sum()
            tong_mon = df_history["Số lượng"].sum()

            col_met1, col_met2 = st.columns(2)
            with col_met1:
                st.metric("💰 Tổng doanh thu", f"{tong_doanh_thu:,.0f} VNĐ")
            with col_met2:
                st.metric("🍽️ Số lượng món đã phục vụ", f"{tong_mon} phần")

            st.markdown("---")

            st.subheader("📅 Doanh thu theo ngày")
            df_history["Ngày"] = pd.to_datetime(df_history["Thời gian"]).dt.date
            df_daily_revenue = (
                df_history.groupby("Ngày")["Thành tiền"]
                .sum()
                .reset_index()
            )
            df_daily_revenue.columns = ["Ngày", "Doanh thu (VNĐ)"]

            col_chart_day, col_table_day = st.columns([1.5, 1])
            with col_chart_day:
                st.bar_chart(
                    df_daily_revenue.set_index("Ngày")["Doanh thu (VNĐ)"]
                )

            with col_table_day:
                st.dataframe(
                    df_daily_revenue.style.format(
                        {"Doanh thu (VNĐ)": "{:,.0f} VNĐ"}
                    ),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("---")

            st.subheader("📋 Chi tiết lịch sử thanh toán thực tế")
            st.dataframe(
                df_history[["ID", "Thời gian", "Bàn", "Tên món", "Số lượng", "Thành tiền"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Hệ thống chưa ghi nhận giao dịch nào.")

    # TAB 3 - PHÂN TÍCH
    with tab3:
        st.subheader("📊 Thống kê & Phân tích bán hàng REAL-TIME")
        df_anal = load_history_from_db()

        if not df_anal.empty:
            df_anal["Thời gian"] = pd.to_datetime(df_anal["Thời gian"])
            df_anal["Giờ"] = df_anal["Thời gian"].dt.hour
            df_anal["Tháng-Năm"] = df_anal["Thời gian"].dt.strftime("%m/%Y")

            # Món bán chạy
            product_quantity = df_anal.groupby("Tên món")["Số lượng"].sum()
            best_seller = product_quantity.idxmax()
            best_seller_qty = product_quantity.max()

            # Khung giờ vàng
            hourly_sales = df_anal.groupby("Giờ")["Số lượng"].sum()
            best_hour = hourly_sales.idxmax()
            best_hour_qty = hourly_sales.max()

            # Tháng doanh thu cao nhất
            monthly_revenue = df_anal.groupby("Tháng-Năm")["Thành tiền"].sum()
            best_month = monthly_revenue.idxmax()
            best_month_rev = monthly_revenue.max()

            # KPI
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1:
                st.info("🏆 MÓN BÁN CHẠY NHẤT")
                st.metric(label=best_seller, value=f"{best_seller_qty} phần")

            with col_kpi2:
                st.warning("⚡ KHUNG GIỜ BÁN NHIỀU NHẤT")
                st.metric(
                    label=f"{best_hour:02d}:00 - {(best_hour + 1) % 24:02d}:00",
                    value=f"{best_hour_qty} phần"
                )

            with col_kpi3:
                st.success("📅 THÁNG DOANH THU CAO NHẤT")
                st.metric(label=f"Tháng {best_month}", value=f"{best_month_rev:,.0f} VNĐ")

            st.markdown("---")

            # Phân tích theo món
            st.subheader("🍔 Doanh thu & số lượng từng món")
            summary_mon = (
                df_anal.groupby("Tên món")
                .agg(
                    Số_lượng_bán=("Số lượng", "sum"),
                    Doanh_thu=("Thành tiền", "sum")
                )
                .reset_index()
                .sort_values(by="Số_lượng_bán", ascending=False)
            )

            col_chart1, col_table1 = st.columns([1.5, 1])
            with col_chart1:
                st.bar_chart(summary_mon.set_index("Tên món")["Số_lượng_bán"])

            with col_table1:
                st.dataframe(
                    summary_mon.style.format({"Doanh_thu": "{:,.0f} VNĐ"}),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("---")

            # Phân tích theo giờ
            st.subheader("⏰ Số lượng món bán theo giờ")
            summary_gio = (
                df_anal.groupby("Giờ")
                .agg(
                    Số_lượng_món=("Số lượng", "sum"),
                    Doanh_thu=("Thành tiền", "sum")
                )
                .reset_index()
            )

            all_hours = pd.DataFrame({"Giờ": range(24)})
            summary_gio = pd.merge(all_hours, summary_gio, on="Giờ", how="left").fillna(0)

            col_chart2, col_info2 = st.columns([1.5, 1])
            with col_chart2:
                st.bar_chart(summary_gio.set_index("Giờ")["Số_lượng_món"])

            with col_info2:
                st.write(f"**Khung giờ bán nhiều nhất:** {best_hour:02d}:00 - {(best_hour + 1) % 24:02d}:00")
                st.write(f"**Số lượng:** {best_hour_qty} phần")
                st.dataframe(
                    summary_gio[summary_gio["Số_lượng_món"] > 0].style.format(
                        {"Doanh_thu": "{:,.0f} VNĐ"}
                    ),
                    use_container_width=True,
                    hide_index=True
                )

            st.markdown("---")

            # Phân tích theo tháng
            st.subheader("📅 Doanh thu bán hàng theo tháng")
            df_anal["Tháng_Số"] = df_anal["Thời gian"].dt.month
            summary_thang = (
                df_anal.groupby(["Tháng_Số", "Tháng-Năm"])
                .agg(
                    Số_lượng_bán=("Số lượng", "sum"),
                    Doanh_thu=("Thành tiền", "sum")
                )
                .reset_index()
                .sort_values("Tháng_Số")
            )

            col_chart3, col_table3 = st.columns([1.5, 1])
            with col_chart3:
                st.bar_chart(summary_thang.set_index("Tháng-Năm")["Doanh_thu"])

            with col_table3:
                st.dataframe(
                    summary_thang[["Tháng-Năm", "Số_lượng_bán", "Doanh_thu"]].style.format(
                        {"Doanh_thu": "{:,.0f} VNĐ"}
                    ),
                    use_container_width=True,
                    hide_index=True
                )

        else:
            st.info("Chưa có dữ liệu giao dịch để thống kê.")
