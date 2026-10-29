from datetime import date, datetime, timedelta
from email.message import EmailMessage
from html import escape
import os
import smtplib
import ssl

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from sklearn.ensemble import RandomForestRegressor

from config.database import SessionLocal
from models.product import Product
from models.inventory import Inventory
from models.sales import Sale, SaleItem
from models.customer import Customer
from services.product_service import ProductService
from services.inventory_service import InventoryService
from services.sales_service import SalesService
from dashboard.analytics import AnalyticsService
from auth import require_login, logout


# ============================================================
# PAGE CONFIGURATION + PROFESSIONAL UI
# ============================================================
st.set_page_config(
    page_title="ShopiFlow | Retail Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit's active theme variables keep controls readable in both light and dark mode.
BASE_THEME = (st.get_option("theme.base") or "light").lower()
PLOTLY_TEMPLATE = "plotly_dark" if BASE_THEME == "dark" else "plotly_white"

st.markdown("""
<style>
:root {
    --sf-accent: var(--primary-color, #356AE6);
    --sf-bg: var(--background-color, #FFFFFF);
    --sf-panel: var(--secondary-background-color, #F5F7FB);
    --sf-text: var(--text-color, #202B3C);
    --sf-border: color-mix(in srgb, var(--sf-text) 16%, transparent);
    --sf-muted: color-mix(in srgb, var(--sf-text) 70%, transparent);
}
.stApp { background: var(--sf-bg); color: var(--sf-text); }
.block-container { max-width: 1600px; padding-top: 1.5rem; padding-bottom: 2.5rem; }
[data-testid="stSidebar"] { background: var(--sf-panel); border-right: 1px solid var(--sf-border); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color: var(--sf-text) !important; }
[data-testid="stMetric"] {
    background: var(--sf-panel); color: var(--sf-text);
    border: 1px solid var(--sf-border); border-radius: 12px;
    padding: 16px 18px; box-shadow: 0 2px 8px rgba(20, 30, 50, .06);
}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"],
[data-testid="stMetricDelta"] { color: var(--sf-text) !important; }
div[data-testid="stForm"] {
    background: var(--sf-panel); border: 1px solid var(--sf-border);
    border-radius: 12px; padding: 20px;
}
[data-testid="stTabs"] button, [data-testid="stRadio"] label,
[data-testid="stCheckbox"] label, [data-testid="stToggle"] label,
[data-testid="stWidgetLabel"] { color: var(--sf-text); }
input, textarea { color: var(--sf-text) !important; }
div.stButton > button, div.stFormSubmitButton > button {
    border-radius: 8px; font-weight: 600; min-height: 40px;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid var(--sf-border); border-radius: 8px;
}
.sf-brand { display:flex; align-items:center; gap:.7rem; margin:.2rem 0 1rem; }
.sf-brand-mark { display:flex; align-items:center; justify-content:center; width:2.45rem; height:2.45rem;
    border-radius:.75rem; background:var(--sf-accent); color:white !important; font-size:1.2rem; font-weight:800; }
.sf-brand-name { color:var(--sf-text) !important; font-size:1.35rem; font-weight:800; letter-spacing:.055em; line-height:1.1; }
.sf-brand-tag { color:var(--sf-muted) !important; font-size:.66rem; letter-spacing:.09em; margin-top:.25rem; }
.auth-brand { max-width:700px; margin:2.5rem auto 1.5rem; text-align:center; padding:1.5rem 1rem; }
.auth-eyebrow { color:var(--sf-accent); font-size:.72rem; font-weight:700; letter-spacing:.18em; margin-bottom:.8rem; }
.auth-brand h1 { color:var(--sf-text) !important; font-size:3rem; font-weight:800; letter-spacing:-.05em; margin:0; }
.auth-brand p { color:var(--sf-muted) !important; font-size:1rem; margin-top:.6rem; }
h1, h2, h3, p, label { color:var(--sf-text); }
/* Ensure Streamlit's native alerts, expanders and tabs retain readable contrast. */
[data-testid="stExpander"] { border-color:var(--sf-border); }
[data-testid="stAlert"] p { color:inherit; }
@media (prefers-reduced-motion: no-preference) {
    div.stButton > button, div.stFormSubmitButton > button { transition: border-color .15s ease, transform .15s ease; }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover { border-color:var(--sf-accent); }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# AUTHENTICATION GATE
# ============================================================
if not require_login():
    st.stop()

current_user = st.session_state["shopiflow_user"]
USER_ROLE = current_user.get("role", "staff")


def require_role(*allowed_roles):
    """Block unauthorized actions; hiding UI alone is not security."""
    if USER_ROLE not in allowed_roles:
        st.error("You do not have permission to perform this action.")
        return False
    return True


# ============================================================
# CURRENCY
# Monetary values in the database are assumed to be INR.
# Example rates only; replace with trusted live rates if required.
# ============================================================
CURRENCY_OPTIONS = {
    "INR — Indian Rupee (₹)": {"code": "INR", "symbol": "₹", "inr_per_unit": 1.0},
    "USD — US Dollar ($)": {"code": "USD", "symbol": "$", "inr_per_unit": 85.5},
    "EUR — Euro (€)": {"code": "EUR", "symbol": "€", "inr_per_unit": 99.5},
}

st.sidebar.markdown(
    """
    <div class="sf-brand">
      <div class="sf-brand-mark">S</div>
      <div>
        <div class="sf-brand-name">SHOPIFLOW</div>
        <div class="sf-brand-tag">RETAIL INTELLIGENCE</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.caption("RETAIL INTELLIGENCE PLATFORM")
st.sidebar.divider()
st.sidebar.caption("SIGNED-IN USER")
st.sidebar.markdown(f"**{current_user['full_name']}**")
st.sidebar.caption(f"{current_user['email']} · {USER_ROLE.title()}")
if st.sidebar.button("Sign out", use_container_width=True):
    logout()
st.sidebar.divider()

selected_currency = st.sidebar.selectbox(
    "Display currency", list(CURRENCY_OPTIONS.keys()), index=0, key="shopiflow_currency"
)
currency = CURRENCY_OPTIONS[selected_currency]
CURRENCY_CODE = currency["code"]
CURRENCY_SYMBOL = currency["symbol"]
INR_PER_UNIT = float(currency["inr_per_unit"])
st.sidebar.caption("Example exchange rates — not live market quotes.")

pages = [
    "Dashboard", "Products", "Customers", "Inventory",
    "POS & Sales", "Data Import", "AI Predictions"
]
if USER_ROLE == "staff":
    # Staff can use POS and see only operational pages they need.
    pages = ["Dashboard", "Products", "Customers", "Inventory", "POS & Sales"]
page = st.sidebar.radio("WORKSPACE", pages)
st.sidebar.divider()
st.sidebar.caption("Streamlit  ·  PostgreSQL  ·  Pandas  ·  Plotly  ·  Scikit-learn")


# ============================================================
# HELPERS
# ============================================================
def convert_from_inr(value):
    try:
        return float(value or 0) / INR_PER_UNIT
    except (TypeError, ValueError):
        return 0.0


def money(value):
    return f"{CURRENCY_SYMBOL}{convert_from_inr(value):,.2f}"


def currency_label(label="Amount"):
    return f"{label} ({CURRENCY_CODE})"


def product_frame(db):
    rows = db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.product_name).all()
    return pd.DataFrame([{
        "Product ID": p.product_id, "Product": p.product_name, "Category": p.category,
        "SKU": p.sku, currency_label("Selling Price"): convert_from_inr(p.price),
        currency_label("Cost Price"): convert_from_inr(p.cost_price), "Supplier": p.supplier or ""
    } for p in rows])


def sales_frame(db, start=None, end=None):
    query = db.query(Sale).order_by(Sale.sale_date.desc())
    if start:
        query = query.filter(Sale.sale_date >= datetime.combine(start, datetime.min.time()))
    if end:
        query = query.filter(Sale.sale_date < datetime.combine(end + timedelta(days=1), datetime.min.time()))
    rows = query.all()
    return pd.DataFrame([{
        "Order ID": f"ORD-{s.sale_id:06d}", "Sale ID": s.sale_id,
        "Customer Type": "Registered Customer" if s.customer_id is not None else "Walk-in Customer",
        "Customer ID": s.customer_id, currency_label("Revenue"): convert_from_inr(s.total_amount),
        "Currency": CURRENCY_CODE, "Payment Method": s.payment_method, "Sale Date": s.sale_date
    } for s in rows])


def make_daily_sales(db):
    rows = db.query(
        func.date(Sale.sale_date).label("sale_day"),
        func.sum(Sale.total_amount).label("revenue_inr"),
        func.count(Sale.sale_id).label("transactions")
    ).group_by(func.date(Sale.sale_date)).order_by(func.date(Sale.sale_date)).all()
    return pd.DataFrame([{
        "Date": pd.to_datetime(r.sale_day),
        "Revenue (INR)": float(r.revenue_inr or 0),
        currency_label("Revenue"): convert_from_inr(r.revenue_inr),
        "Transactions": int(r.transactions or 0)
    } for r in rows])


def low_stock_frame(db):
    rows = db.query(Inventory, Product).join(
        Product, Inventory.product_id == Product.product_id
    ).filter(Product.is_active.is_(True)).order_by(Inventory.quantity).all()
    return pd.DataFrame([{
        "Product": p.product_name, "SKU": p.sku, "Category": p.category,
        "Current Stock": i.quantity, "Reorder Level": i.reorder_level,
        "Suggested Restock": max(i.reorder_quantity, i.reorder_level - i.quantity + i.reorder_quantity),
        "Status": "Low Stock" if i.quantity <= i.reorder_level else "In Stock"
    } for i, p in rows])


def show_sales_charts(db):
    daily = make_daily_sales(db)
    if daily.empty:
        st.info("Record a sale or import historical sales data to unlock sales trends.")
        return
    rev_col = currency_label("Revenue")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.line(daily, x="Date", y=rev_col, markers=True,
            title=f"Revenue Trend ({CURRENCY_CODE})", template=PLOTLY_TEMPLATE), use_container_width=True)
    with right:
        st.plotly_chart(px.bar(daily, x="Date", y="Transactions",
            title="Daily Transactions", template=PLOTLY_TEMPLATE), use_container_width=True)
    top = db.query(
        Product.product_name.label("product"),
        func.sum(SaleItem.quantity).label("units"),
        func.sum(SaleItem.subtotal).label("revenue_inr")
    ).join(SaleItem, Product.product_id == SaleItem.product_id).join(
        Sale, Sale.sale_id == SaleItem.sale_id
    ).group_by(Product.product_id, Product.product_name).order_by(
        func.sum(SaleItem.quantity).desc()
    ).limit(10).all()
    if top:
        df = pd.DataFrame([{
            "Product": r.product, "Units Sold": int(r.units or 0),
            rev_col: convert_from_inr(r.revenue_inr)
        } for r in top])
        a, b = st.columns(2)
        with a:
            st.plotly_chart(px.bar(df, x="Product", y="Units Sold",
                title="Top-selling Products", template=PLOTLY_TEMPLATE), use_container_width=True)
        with b:
            st.plotly_chart(px.pie(df, names="Product", values=rev_col,
                title=f"Revenue Mix ({CURRENCY_CODE})", hole=.45), use_container_width=True)


def get_email_settings():
    """Read SMTP credentials from Streamlit Secrets or environment variables."""
    settings = {}
    try:
        settings = dict(st.secrets.get("email", {}))
    except Exception:
        settings = {}
    return {
        "smtp_server": settings.get("smtp_server") or os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(settings.get("smtp_port") or os.getenv("SMTP_PORT", "587")),
        "sender_email": settings.get("sender_email") or os.getenv("SMTP_USER", "shopiflow.rgu@gmail.com"),
        "app_password": settings.get("app_password") or os.getenv("SMTP_PASSWORD", ""),
    }


def send_invoice_email(to_email, order):
    """Send a self-contained HTML receipt through the configured Gmail SMTP account."""
    cfg = get_email_settings()
    if not cfg["app_password"]:
        raise RuntimeError(
            "Email is not configured yet. Add the Gmail app password in Streamlit Cloud → Settings → Secrets."
        )
    if not to_email or "@" not in to_email or "." not in to_email.rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid customer email address.")

    rows_html = "".join(
        "<tr>"
        f"<td style='padding:10px;border-bottom:1px solid #e5e7eb'>{escape(str(item['product_name']))}<br><small>SKU: {escape(str(item['sku']))}</small></td>"
        f"<td style='padding:10px;text-align:center;border-bottom:1px solid #e5e7eb'>{int(item['quantity'])}</td>"
        f"<td style='padding:10px;text-align:right;border-bottom:1px solid #e5e7eb'>{escape(order['currency_symbol'])}{float(item['unit_price_display']):,.2f}</td>"
        f"<td style='padding:10px;text-align:right;border-bottom:1px solid #e5e7eb'>{escape(order['currency_symbol'])}{float(item['line_total_display']):,.2f}</td>"
        "</tr>" for item in order["items"]
    )
    total = f"{order['currency_symbol']}{float(order['total_display']):,.2f}"
    order_id = escape(str(order['order_id']))
    customer = escape(str(order.get('customer_name') or 'Walk-in Customer'))
    sale_date = escape(str(order.get('sale_date') or datetime.now().strftime('%Y-%m-%d %H:%M')))
    payment = escape(str(order.get('payment_method') or ''))
    html_body = f"""<!doctype html><html><body style='font-family:Arial,sans-serif;color:#202b3c;max-width:760px;margin:auto;padding:24px'>
      <div style='background:#173b70;color:#fff;padding:22px;border-radius:12px 12px 0 0'><h1 style='margin:0;letter-spacing:2px'>SHOPIFLOW</h1><p style='margin:6px 0 0'>Retail purchase invoice</p></div>
      <div style='border:1px solid #e5e7eb;padding:22px;border-radius:0 0 12px 12px'><h2>Thank you for your purchase</h2>
      <p><b>Order:</b> {order_id}<br><b>Date:</b> {sale_date}<br><b>Customer:</b> {customer}<br><b>Payment:</b> {payment}</p>
      <table style='width:100%;border-collapse:collapse'><thead><tr style='background:#f3f6fb'><th style='padding:10px;text-align:left'>Item</th><th>Qty</th><th style='text-align:right'>Unit price</th><th style='text-align:right'>Amount</th></tr></thead><tbody>{rows_html}</tbody></table>
      <p style='text-align:right;font-size:20px;margin-top:22px'><b>Total: {total}</b></p>
      <p style='color:#667085;font-size:12px'>This email was sent by SHOPIFLOW from {escape(cfg['sender_email'])}. Please keep it for your records.</p></div></body></html>"""
    plain_lines = [
        "SHOPIFLOW — Purchase invoice", f"Order: {order['order_id']}",
        f"Date: {order.get('sale_date', '')}", f"Customer: {order.get('customer_name') or 'Walk-in Customer'}",
        f"Payment: {order.get('payment_method', '')}", "", "Items:"
    ]
    for item in order["items"]:
        plain_lines.append(
            f"{item['product_name']} ({item['sku']}) x {item['quantity']} — "
            f"{order['currency_symbol']}{item['line_total_display']:,.2f}"
        )
    plain_lines.extend(["", f"Total: {total}", "Thank you for shopping with SHOPIFLOW."])
    message = EmailMessage()
    message["Subject"] = f"SHOPIFLOW invoice {order['order_id']}"
    message["From"] = f"SHOPIFLOW <{cfg['sender_email']}>"
    message["To"] = to_email.strip()
    message.set_content("\n".join(plain_lines))
    message.add_alternative(html_body, subtype="html")
    context = ssl.create_default_context()
    with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"], timeout=25) as server:
        server.starttls(context=context)
        server.login(cfg["sender_email"], cfg["app_password"].replace(" ", ""))
        server.send_message(message)


# ============================================================
# DATABASE CONNECTION
# ============================================================
db = None
try:
    db = SessionLocal()
    db.execute(text("SELECT 1"))
except Exception as exc:
    if db is not None:
        db.close()
    st.error("ShopiFlow cannot connect to PostgreSQL.")
    st.markdown("""
    **For Streamlit Cloud:** configure `DATABASE_URL` or `DB_HOST`, `DB_PORT`,
    `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in App Settings → Secrets.
    The database must be hosted online; `localhost` refers to the app container.
    """)
    with st.expander("Technical details"):
        st.code(str(exc)[:1500])
    st.stop()


try:
    # ========================================================
    # DASHBOARD
    # ========================================================
    if page == "Dashboard":
        st.title("Retail Intelligence")
        st.caption("Sales performance, product trends and inventory health.")
        summary = AnalyticsService.get_dashboard_summary(db)
        cols = st.columns(5)
        cols[0].metric(f"Revenue ({CURRENCY_CODE})", money(summary.get("total_sales", 0)))
        cols[1].metric("Transactions", f"{summary.get('total_transactions', 0):,}")
        cols[2].metric("Active products", f"{summary.get('total_products', 0):,}")
        cols[3].metric("Units in stock", f"{summary.get('total_inventory', 0):,}")
        cols[4].metric("Low-stock items", f"{summary.get('low_stock', 0):,}")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Trend start date", date.today() - timedelta(days=90), key="trend_start")
        with c2:
            end_date = st.date_input("Trend end date", date.today(), key="trend_end")
        if start_date > end_date:
            st.warning("Start date must be on or before end date.")
        else:
            daily = make_daily_sales(db)
            if not daily.empty:
                daily = daily[(daily["Date"].dt.date >= start_date) & (daily["Date"].dt.date <= end_date)]
                if daily.empty:
                    st.info("No sales in the selected date range.")
                else:
                    st.subheader("Sales and revenue trends")
                    a, b = st.columns(2)
                    with a:
                        st.plotly_chart(px.line(daily, x="Date", y=currency_label("Revenue"),
                            markers=True, title=f"Revenue by day ({CURRENCY_CODE})",
                            template=PLOTLY_TEMPLATE), use_container_width=True)
                    with b:
                        st.plotly_chart(px.bar(daily, x="Date", y="Transactions",
                            title="Transactions by day", template=PLOTLY_TEMPLATE), use_container_width=True)
            else:
                st.info("No sales data yet. Record a POS transaction to get started.")
        st.subheader("Product performance")
        show_sales_charts(db)
        st.subheader("Inventory alerts")
        stock = low_stock_frame(db)
        if stock.empty:
            st.info("No inventory records yet.")
        else:
            low = stock[stock["Status"] == "Low Stock"]
            if low.empty:
                st.success("All tracked products are above their reorder levels.")
            else:
                st.warning(f"{len(low)} product(s) are at or below reorder level.")
                st.dataframe(low, use_container_width=True, hide_index=True)
        if USER_ROLE in ("admin", "manager"):
            with st.expander("Export current data"):
                products_export = product_frame(db)
                if not products_export.empty:
                    st.download_button("Download products CSV", products_export.to_csv(index=False).encode("utf-8"),
                        "shopiflow_products.csv", "text/csv")
                all_sales = sales_frame(db)
                if not all_sales.empty:
                    st.download_button("Download sales CSV", all_sales.to_csv(index=False).encode("utf-8"),
                        "shopiflow_sales.csv", "text/csv")

    # ========================================================
    # PRODUCTS
    # ========================================================
    elif page == "Products":
        st.title("Product management")
        st.caption(f"Prices are stored in INR. Display values use {CURRENCY_CODE}.")
        add_tab, view_tab, edit_tab = st.tabs(["Add product", "Product catalogue", "Update product"])
        with add_tab:
            with st.form("add_product_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                name = c1.text_input("Product name *")
                category = c2.text_input("Category *")
                sku = c1.text_input("SKU / barcode *").strip()
                supplier = c2.text_input("Supplier")
                price = c1.number_input("Selling price (INR)", min_value=0.0, value=10.0, step=1.0)
                cost = c2.number_input("Cost price (INR)", min_value=0.0, value=5.0, step=1.0)
                c3, c4, c5 = st.columns(3)
                opening_stock = c3.number_input("Opening stock", min_value=0, value=20, step=1)
                reorder_level = c4.number_input("Low-stock threshold", min_value=0, value=10, step=1)
                reorder_qty = c5.number_input("Suggested reorder quantity", min_value=1, value=50, step=1)
                submitted = st.form_submit_button("Save product", type="primary", use_container_width=True)
            if submitted:
                if not name.strip() or not category.strip() or not sku:
                    st.error("Product name, category and SKU are required.")
                elif not require_role("admin", "manager"):
                    pass
                else:
                    try:
                        product = ProductService.create_product(db, name.strip(), category.strip(), sku,
                            price, cost, supplier.strip() or None)
                        db.add(Inventory(product_id=product.product_id, quantity=int(opening_stock),
                            reorder_level=int(reorder_level), reorder_quantity=int(reorder_qty)))
                        db.commit()
                        st.success("Product and inventory record created.")
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(f"Could not add product: {exc}")
        with view_tab:
            df = product_frame(db)
            if df.empty:
                st.info("No products yet.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button("Export catalogue CSV", df.to_csv(index=False).encode("utf-8"),
                    "shopiflow_products.csv", "text/csv")
        with edit_tab:
            products = ProductService.get_all_products(db)
            if not products:
                st.info("Add a product before editing.")
            else:
                options = {f"{p.product_name} · {p.sku} (ID {p.product_id})": p.product_id for p in products}
                selected_label = st.selectbox("Choose product", list(options))
                selected = ProductService.get_product(db, options[selected_label])
                with st.form("edit_product_form"):
                    new_name = st.text_input("Product name", value=selected.product_name)
                    new_category = st.text_input("Category", value=selected.category)
                    new_price = st.number_input("Selling price (INR)", min_value=0.0,
                        value=float(selected.price or 0), step=1.0)
                    new_cost = st.number_input("Cost price (INR)", min_value=0.0,
                        value=float(selected.cost_price or 0), step=1.0)
                    new_supplier = st.text_input("Supplier", value=selected.supplier or "")
                    save_edit = st.form_submit_button("Update product", type="primary")
                if save_edit:
                    if not require_role("admin", "manager"):
                        pass
                    else:
                        try:
                            ProductService.update_product(db, selected.product_id,
                                product_name=new_name.strip(), category=new_category.strip(),
                                price=new_price, cost_price=new_cost, supplier=new_supplier.strip() or None)
                            st.success("Product updated.")
                            st.rerun()
                        except Exception as exc:
                            db.rollback()
                            st.error(str(exc))

    # ========================================================
    # CUSTOMERS
    # ========================================================
    elif page == "Customers":
        st.title("Customer management")
        st.caption("Walk-in customers do not need a registered customer ID.")
        add_tab, list_tab = st.tabs(["Register customer", "Customer directory"])
        with add_tab:
            with st.form("add_customer_form", clear_on_submit=True):
                name = st.text_input("Customer name *")
                email = st.text_input("Email (optional)")
                phone = st.text_input("Phone (optional)")
                address = st.text_area("Address (optional)")
                save = st.form_submit_button("Register customer", type="primary", use_container_width=True)
            if save:
                if not name.strip():
                    st.error("Customer name is required.")
                elif not require_role("admin", "manager"):
                    pass
                else:
                    try:
                        customer = Customer(customer_name=name.strip(), email=email.strip() or None,
                            phone=phone.strip() or None, address=address.strip() or None)
                        db.add(customer)
                        db.commit()
                        st.success(f"Customer registered. ID: {customer.customer_id}")
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(f"Could not register customer: {exc}")
        with list_tab:
            customers = db.query(Customer).order_by(Customer.customer_id.desc()).all()
            if not customers:
                st.info("No registered customers yet.")
            else:
                df = pd.DataFrame([{"Customer ID": c.customer_id, "Customer Name": c.customer_name,
                    "Email": c.email or "", "Phone": c.phone or "", "Address": c.address or ""} for c in customers])
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button("Export customers CSV", df.to_csv(index=False).encode("utf-8"),
                    "shopiflow_customers.csv", "text/csv")

    # ========================================================
    # INVENTORY
    # ========================================================
    elif page == "Inventory":
        st.title("Inventory management")
        stock_tab, adjust_tab = st.tabs(["Stock overview", "Adjust stock"])
        with stock_tab:
            stock = low_stock_frame(db)
            if stock.empty:
                st.info("No inventory records found.")
            else:
                low_only = st.toggle("Show only low-stock items")
                display = stock[stock["Status"] == "Low Stock"] if low_only else stock
                st.dataframe(display, use_container_width=True, hide_index=True)
                st.download_button("Export inventory CSV", stock.to_csv(index=False).encode("utf-8"),
                    "shopiflow_inventory.csv", "text/csv")
                st.plotly_chart(px.bar(stock.sort_values("Current Stock"), x="Product", y="Current Stock",
                    color="Status", title="Current stock by product", template=PLOTLY_TEMPLATE),
                    use_container_width=True)
        with adjust_tab:
            rows = db.query(Product, Inventory).join(Inventory, Product.product_id == Inventory.product_id).filter(
                Product.is_active.is_(True)).order_by(Product.product_name).all()
            if not rows:
                st.info("Add products first.")
            else:
                labels = {f"{p.product_name} · current stock {i.quantity}": (p, i) for p, i in rows}
                label = st.selectbox("Product to adjust", list(labels))
                product, inv = labels[label]
                st.write(f"Current quantity: **{inv.quantity}**")
                mode = st.radio("Adjustment type", ["Add stock", "Set exact stock"], horizontal=True)
                qty = st.number_input("Quantity", min_value=0 if mode == "Set exact stock" else 1, value=1, step=1)
                if st.button("Save stock adjustment", type="primary"):
                    if not require_role("admin", "manager"):
                        pass
                    else:
                        try:
                            if mode == "Add stock":
                                InventoryService.add_stock(db, product.product_id, int(qty))
                            else:
                                InventoryService.update_stock(db, product.product_id, int(qty))
                            st.success("Inventory updated.")
                            st.rerun()
                        except Exception as exc:
                            db.rollback()
                            st.error(str(exc))

    # ========================================================
    # POS & SALES — MULTI-ITEM CART + INVOICE EMAIL
    # ========================================================
    elif page == "POS & Sales":
        st.title("Point of sale")
        st.caption("Build one cart with multiple products, then complete one order and one bill.")
        products = ProductService.get_all_products(db)
        if not products:
            st.info("Add products and opening stock before recording sales.")
        else:
            if "shopiflow_cart" not in st.session_state:
                st.session_state["shopiflow_cart"] = {}
            cart = st.session_state["shopiflow_cart"]
            active_products = {p.product_id: p for p in products}

            st.subheader("1. Add items")
            product_options = {
                f"{p.product_name} · {p.sku} — {money(p.price)}": p.product_id
                for p in products
            }
            add_col1, add_col2, add_col3 = st.columns([3, 1, 1])
            with add_col1:
                selected_label = st.selectbox("Product", list(product_options), key="pos_add_product")
            selected_pid = product_options[selected_label]
            selected_product = active_products[selected_pid]
            selected_inventory = InventoryService.get_inventory(db, selected_pid)
            selected_stock = int(selected_inventory.quantity if selected_inventory else 0)
            with add_col2:
                add_qty = st.number_input(
                    "Quantity", min_value=1, max_value=max(1, selected_stock), value=1,
                    step=1, key="pos_add_quantity", disabled=(selected_stock <= 0)
                )
            with add_col3:
                st.write("")
                st.write("")
                add_clicked = st.button("Add to bill", type="primary", use_container_width=True,
                    disabled=(selected_stock <= 0), key="pos_add_to_cart")
            st.caption(f"Available stock for {selected_product.product_name}: {selected_stock}")
            if add_clicked:
                existing_qty = int(cart.get(selected_pid, {}).get("quantity", 0))
                if existing_qty + int(add_qty) > selected_stock:
                    st.error(f"Only {selected_stock} unit(s) are in stock; the cart already contains {existing_qty}.")
                else:
                    cart[selected_pid] = {
                        "product_id": selected_pid,
                        "product_name": selected_product.product_name,
                        "sku": selected_product.sku,
                        "unit_price_inr": float(selected_product.price or 0),
                        "quantity": existing_qty + int(add_qty),
                    }
                    st.session_state["shopiflow_cart"] = cart
                    st.rerun()

            st.divider()
            st.subheader("2. Current bill")
            if not cart:
                st.info("Your bill is empty. Add two or more products to make a multi-item order.")
            else:
                cart_total_inr = 0.0
                for pid in list(cart.keys()):
                    item = cart[pid]
                    product = active_products.get(pid)
                    if product is None:
                        cart.pop(pid, None)
                        continue
                    inv = InventoryService.get_inventory(db, pid)
                    available = int(inv.quantity if inv else 0)
                    # Refresh name/price from the database so the checkout uses current product data.
                    item["product_name"] = product.product_name
                    item["sku"] = product.sku
                    item["unit_price_inr"] = float(product.price or 0)
                    max_qty = max(1, available)
                    item_cols = st.columns([3, 1.2, 1.4, 1.4, 0.8])
                    item_cols[0].markdown(f"**{product.product_name}**  ")
                    item_cols[0].caption(f"SKU: {product.sku} · In stock: {available}")
                    item_cols[1].write(f"Price: {money(item['unit_price_inr'])}")
                    qty_now = st.number_input(
                        "Qty", min_value=1, max_value=max_qty,
                        value=min(max(1, int(item["quantity"])), max_qty), step=1,
                        key=f"pos_cart_qty_{pid}", disabled=(available <= 0)
                    )
                    item["quantity"] = int(qty_now)
                    line_total = item["unit_price_inr"] * item["quantity"]
                    cart_total_inr += line_total
                    item_cols[3].markdown(f"**{money(line_total)}**")
                    if item_cols[4].button("Remove", key=f"pos_remove_{pid}"):
                        cart.pop(pid, None)
                        st.session_state["shopiflow_cart"] = cart
                        st.rerun()
                    if int(item["quantity"]) > available:
                        st.error(f"{product.product_name}: quantity exceeds available stock.")
                st.session_state["shopiflow_cart"] = cart
                st.markdown(f"### Bill total: {money(cart_total_inr)}")
                st.caption(f"Prices are stored in INR; this bill is displayed in {CURRENCY_CODE}.")

                st.divider()
                st.subheader("3. Customer and checkout")
                customer_type = st.radio(
                    "Customer type", ["Walk-in Customer", "Registered Customer"],
                    horizontal=True, key="pos_customer_type"
                )
                customer_id = None
                customer_name = "Walk-in Customer"
                customer_email = ""
                checkout_disabled = not cart
                if customer_type == "Registered Customer":
                    customer_rows = db.query(Customer).order_by(Customer.customer_name).all()
                    if not customer_rows:
                        st.warning("Register a customer first, or choose Walk-in Customer.")
                        checkout_disabled = True
                    else:
                        customer_options = {
                            f"{c.customer_name} (ID: {c.customer_id})": c for c in customer_rows
                        }
                        selected_customer_label = st.selectbox("Select customer", list(customer_options), key="pos_registered_customer")
                        selected_customer = customer_options[selected_customer_label]
                        customer_id = selected_customer.customer_id
                        customer_name = selected_customer.customer_name
                        customer_email = selected_customer.email or ""
                payment = st.selectbox(
                    "Payment method", ["Cash", "UPI", "Card", "Bank Transfer", "Other"], key="pos_payment_method"
                )
                st.info("All cart items will be saved under one order ID. Stock is deducted only when the sale succeeds.")
                checkout = st.button(
                    "Complete sale and generate bill", type="primary", use_container_width=True,
                    disabled=checkout_disabled, key="pos_checkout"
                )
                if checkout:
                    try:
                        line_items = []
                        validation_errors = []
                        for pid, item in cart.items():
                            inv = InventoryService.get_inventory(db, pid)
                            available = int(inv.quantity if inv else 0)
                            quantity = int(item["quantity"])
                            if quantity < 1 or quantity > available:
                                validation_errors.append(f"{item['product_name']}: requested {quantity}, available {available}.")
                            line_items.append({"product_id": int(pid), "quantity": quantity})
                        if validation_errors:
                            st.error("Please correct the cart before checkout: " + " ".join(validation_errors))
                        elif not line_items:
                            st.error("Add at least one item before checkout.")
                        else:
                            sale = SalesService.create_sale(db, customer_id, line_items, payment)
                            order_items = []
                            for pid, item in cart.items():
                                q = int(item["quantity"])
                                unit_inr = float(item["unit_price_inr"])
                                order_items.append({
                                    "product_id": int(pid), "product_name": item["product_name"],
                                    "sku": item["sku"], "quantity": q,
                                    "unit_price_display": convert_from_inr(unit_inr),
                                    "line_total_display": convert_from_inr(unit_inr * q),
                                })
                            order = {
                                "order_id": f"ORD-{sale.sale_id:06d}",
                                "sale_id": int(sale.sale_id),
                                "sale_date": str(sale.sale_date or datetime.now()).replace("T", " ")[:19],
                                "customer_id": customer_id, "customer_name": customer_name,
                                "customer_email": customer_email, "payment_method": payment,
                                "total_display": convert_from_inr(float(sale.total_amount or 0)),
                                "currency_code": CURRENCY_CODE, "currency_symbol": CURRENCY_SYMBOL,
                                "items": order_items,
                            }
                            st.session_state["shopiflow_last_order"] = order
                            st.session_state["shopiflow_cart"] = {}
                            st.success(f"{order['order_id']} completed successfully. Total: {money(sale.total_amount)}")
                            st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(f"Sale was not saved: {exc}")

        # A completed order remains available for its invoice email after Streamlit reruns.
        last_order = st.session_state.get("shopiflow_last_order")
        if last_order:
            st.divider()
            st.subheader(f"Invoice — {last_order['order_id']}")
            st.write(f"**Customer:** {last_order.get('customer_name') or 'Walk-in Customer'}  ·  **Payment:** {last_order.get('payment_method', '')}")
            invoice_df = pd.DataFrame([{
                "Product": item["product_name"], "SKU": item["sku"], "Quantity": item["quantity"],
                f"Unit price ({last_order['currency_code']})": item["unit_price_display"],
                f"Line total ({last_order['currency_code']})": item["line_total_display"],
            } for item in last_order["items"]])
            st.dataframe(invoice_df, use_container_width=True, hide_index=True)
            st.markdown(f"### Total: {last_order['currency_symbol']}{last_order['total_display']:,.2f}")
            invoice_csv = invoice_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Download invoice items (CSV)", invoice_csv,
                f"{last_order['order_id']}_invoice.csv", "text/csv", key=f"download_invoice_{last_order['sale_id']}")
            with st.form(f"email_invoice_form_{last_order['sale_id']}"):
                recipient_email = st.text_input(
                    "Email bill to", value=last_order.get("customer_email", ""),
                    placeholder="customer@example.com"
                )
                send_clicked = st.form_submit_button("Send invoice email", type="primary", use_container_width=True)
            if send_clicked:
                try:
                    send_invoice_email(recipient_email, last_order)
                    st.success(f"Invoice {last_order['order_id']} emailed to {recipient_email.strip()}.")
                except Exception as exc:
                    st.error(f"The sale is saved, but the email could not be sent: {exc}")
            if st.button("Clear displayed invoice", key=f"clear_invoice_{last_order['sale_id']}"):
                st.session_state.pop("shopiflow_last_order", None)
                st.rerun()

        st.divider()
        st.subheader("Recent transactions")
        df = sales_frame(db)
        if df.empty:
            st.info("No transactions recorded yet.")
        else:
            st.dataframe(df.sort_values("Sale Date", ascending=False).head(100),
                use_container_width=True, hide_index=True)
            st.download_button("Export sales CSV", df.to_csv(index=False).encode("utf-8"),
                "shopiflow_sales.csv", "text/csv")

    # ========================================================
    # DATA IMPORT — ADMIN / MANAGER ONLY
    # ========================================================
    elif page == "Data Import":
        if not require_role("admin", "manager"):
            st.stop()
        st.title("Data import")
        st.write("Import CSV files. Product prices and historical sales are stored in INR.")
        with st.expander("Product CSV format", expanded=True):
            st.code("product_name,category,sku,price,cost_price,supplier,quantity,reorder_level,reorder_quantity\nTea,Groceries,TEA001,120,85,ABC Supplier,40,10,30", language="csv")
        product_file = st.file_uploader("Upload product CSV", type=["csv"], key="product_csv")
        if product_file:
            try:
                df = pd.read_csv(product_file)
                st.dataframe(df.head(10), use_container_width=True)
                if st.button("Import products", type="primary"):
                    required = {"product_name", "category", "sku", "price", "cost_price"}
                    if not required.issubset(df.columns):
                        st.error("Required columns: product_name, category, sku, price, cost_price.")
                    else:
                        added, errors = 0, []
                        for idx, row in df.iterrows():
                            try:
                                sku = str(row["sku"]).strip()
                                name = str(row["product_name"]).strip()
                                category = str(row["category"]).strip()
                                price = float(row["price"])
                                cost = float(row["cost_price"])
                                if not sku or not name or not category:
                                    raise ValueError("Product name, category and SKU are required.")
                                if price < 0 or cost < 0:
                                    raise ValueError("Prices cannot be negative.")
                                product = ProductService.create_product(db, name, category, sku, price, cost,
                                    None if pd.isna(row.get("supplier", None)) else str(row.get("supplier")).strip() or None)
                                q = int(row.get("quantity", 0)) if pd.notna(row.get("quantity", 0)) else 0
                                rl = int(row.get("reorder_level", 10)) if pd.notna(row.get("reorder_level", 10)) else 10
                                rq = int(row.get("reorder_quantity", 50)) if pd.notna(row.get("reorder_quantity", 50)) else 50
                                if q < 0 or rl < 0 or rq < 1:
                                    raise ValueError("Invalid stock/reorder values.")
                                db.add(Inventory(product_id=product.product_id, quantity=q,
                                    reorder_level=rl, reorder_quantity=rq))
                                db.commit()
                                added += 1
                            except Exception as exc:
                                db.rollback()
                                errors.append(f"Row {idx + 2}: {exc}")
                        st.success(f"Imported {added} product(s).")
                        if errors:
                            st.warning("Some rows were skipped:\n" + "\n".join(errors[:15]))
                        st.rerun()
            except Exception as exc:
                st.error(f"Could not read product CSV: {exc}")

        st.divider()
        with st.expander("Historical sales CSV format", expanded=True):
            st.write("One row per product line. SKUs must already exist. order_id groups lines into a transaction. Optional customer_id must exist. Imports do not deduct current stock.")
            st.code("order_id,sku,quantity,sale_date,payment_method,customer_id\nORD001,TEA001,2,2026-10-01,UPI,1\nORD001,NOTE001,1,2026-10-01,UPI,1\nORD002,TEA001,1,2026-10-02,Cash,", language="csv")
        sales_file = st.file_uploader("Upload historical sales CSV", type=["csv"], key="sales_csv")
        if sales_file:
            try:
                df = pd.read_csv(sales_file)
                st.dataframe(df.head(10), use_container_width=True)
                if st.button("Import historical sales", type="primary"):
                    if not {"sku", "quantity", "sale_date"}.issubset(df.columns):
                        st.error("Required columns: sku, quantity, sale_date.")
                    else:
                        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
                        df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
                        if df["quantity"].isna().any() or (df["quantity"] <= 0).any() or (df["quantity"] % 1 != 0).any() or df["sale_date"].isna().any():
                            st.error("Fix invalid quantities or dates. Quantities must be positive whole numbers.")
                        else:
                            if "order_id" not in df:
                                df["order_id"] = [f"ROW{i}" for i in range(len(df))]
                            else:
                                df["order_id"] = df["order_id"].fillna("").astype(str).str.strip()
                                missing = df["order_id"].eq("")
                                df.loc[missing, "order_id"] = [f"ROW{i}" for i in range(int(missing.sum()))]
                            if "payment_method" not in df:
                                df["payment_method"] = "Imported"
                            else:
                                df["payment_method"] = df["payment_method"].fillna("Imported").astype(str)
                            imported, errors = 0, []
                            for order_id, group in df.groupby("order_id", sort=False):
                                try:
                                    if group["sale_date"].nunique() > 1 or group["payment_method"].nunique() > 1:
                                        raise ValueError("Rows in one order must share date and payment method.")
                                    customer_id = None
                                    if "customer_id" in group.columns:
                                        ids = group["customer_id"].dropna().astype(str).str.strip()
                                        ids = ids[ids != ""]
                                        if len(ids.unique()) > 1:
                                            raise ValueError("Order has multiple customer IDs.")
                                        if not ids.empty:
                                            val = float(ids.iloc[0])
                                            if not val.is_integer():
                                                raise ValueError("Customer ID must be a whole number.")
                                            customer_id = int(val)
                                            if not db.query(Customer).filter(Customer.customer_id == customer_id).first():
                                                raise ValueError(f"Customer ID {customer_id} does not exist.")
                                    lines, total = [], 0.0
                                    for _, row in group.iterrows():
                                        sku = str(row["sku"]).strip()
                                        product = db.query(Product).filter(Product.sku == sku, Product.is_active.is_(True)).first()
                                        if not product:
                                            raise ValueError(f"SKU not found: {sku}")
                                        q = int(row["quantity"])
                                        subtotal = float(product.price or 0) * q
                                        total += subtotal
                                        lines.append((product, q, subtotal))
                                    sale = Sale(customer_id=customer_id, total_amount=total,
                                        payment_method=str(group.iloc[0]["payment_method"])[:50],
                                        sale_date=pd.to_datetime(group.iloc[0]["sale_date"]).to_pydatetime())
                                    db.add(sale)
                                    db.flush()
                                    for product, q, subtotal in lines:
                                        db.add(SaleItem(sale_id=sale.sale_id, product_id=product.product_id,
                                            quantity=q, unit_price=product.price, subtotal=subtotal))
                                    db.commit()
                                    imported += 1
                                except Exception as exc:
                                    db.rollback()
                                    errors.append(f"Order {order_id}: {exc}")
                            st.success(f"Imported {imported} transaction(s).")
                            if errors:
                                st.warning("Some transactions were skipped:\n" + "\n".join(errors[:15]))
                            st.rerun()
            except Exception as exc:
                st.error(f"Could not read sales CSV: {exc}")

    # ========================================================
    # AI PREDICTIONS
    # ========================================================
    elif page == "AI Predictions":
        if not require_role("admin", "manager"):
            st.stop()
        st.title("AI/ML predictions")
        st.caption("Random Forest baseline for sales forecasting and descriptive inventory demand.")
        daily = make_daily_sales(db)
        if daily.empty or len(daily) < 5:
            st.warning("At least 5 distinct sales days are recommended. Import historical sales to build a useful training set.")
        else:
            daily = daily.sort_values("Date").copy()
            daily["day_of_week"] = daily["Date"].dt.dayofweek
            daily["month"] = daily["Date"].dt.month
            daily["day"] = daily["Date"].dt.day
            daily["lag_1"] = daily["Revenue (INR)"].shift(1)
            training = daily.dropna(subset=["lag_1"])
            if len(training) >= 4:
                X = training[["day_of_week", "month", "day", "lag_1"]]
                y = training["Revenue (INR)"]
                model = RandomForestRegressor(n_estimators=150, random_state=42)
                model.fit(X, y)
                future_rows = []
                last_date = daily["Date"].max()
                last_revenue = float(daily.iloc[-1]["Revenue (INR)"])
                for step in range(1, 8):
                    future_date = last_date + pd.Timedelta(days=step)
                    features = pd.DataFrame([{"day_of_week": future_date.dayofweek,
                        "month": future_date.month, "day": future_date.day, "lag_1": last_revenue}])
                    prediction = max(0.0, float(model.predict(features)[0]))
                    future_rows.append({"Date": future_date, "Predicted Revenue (INR)": prediction,
                        currency_label("Predicted Revenue"): convert_from_inr(prediction)})
                    last_revenue = prediction
                forecast = pd.DataFrame(future_rows)
                forecast_col = currency_label("Predicted Revenue")
                st.subheader("Seven-day sales forecast")
                st.info("Educational baseline only. Forecast accuracy depends on the amount and quality of historical data.")
                st.metric(f"Forecast total ({CURRENCY_CODE})", f"{CURRENCY_SYMBOL}{forecast[forecast_col].sum():,.2f}")
                hist = daily[["Date", "Revenue (INR)"]].copy()
                hist["Revenue"] = hist["Revenue (INR)"].apply(convert_from_inr)
                hist["Type"] = "Historical"
                pred = forecast[["Date", forecast_col]].rename(columns={forecast_col: "Revenue"})
                pred["Type"] = "Forecast"
                combined = pd.concat([hist[["Date", "Revenue", "Type"]], pred[["Date", "Revenue", "Type"]],], ignore_index=True)
                st.plotly_chart(px.line(combined, x="Date", y="Revenue", color="Type",
                    markers=True, title=f"Historical and forecast revenue ({CURRENCY_CODE})",
                    template=PLOTLY_TEMPLATE), use_container_width=True)
                display = forecast[["Date", forecast_col]].rename(columns={forecast_col: f"Predicted Revenue ({CURRENCY_CODE})"})
                st.dataframe(display, use_container_width=True, hide_index=True)
                st.download_button("Download forecast CSV", display.to_csv(index=False).encode("utf-8"),
                    "shopiflow_sales_forecast.csv", "text/csv")
            else:
                st.info("More distinct sales days are needed.")

        st.divider()
        st.subheader("Inventory demand and reorder suggestions")
        demand_rows = db.query(
            Product.product_id, Product.product_name, Product.sku,
            Inventory.quantity, Inventory.reorder_level, Inventory.reorder_quantity,
            func.date(Sale.sale_date).label("sale_day"),
            func.sum(SaleItem.quantity).label("units_sold")
        ).join(Inventory, Inventory.product_id == Product.product_id).outerjoin(
            SaleItem, SaleItem.product_id == Product.product_id
        ).outerjoin(Sale, Sale.sale_id == SaleItem.sale_id).filter(
            Product.is_active.is_(True)
        ).group_by(Product.product_id, Product.product_name, Product.sku,
            Inventory.quantity, Inventory.reorder_level, Inventory.reorder_quantity,
            func.date(Sale.sale_date)).all()
        if not demand_rows:
            st.info("Add products and sales to see product demand.")
        else:
            demand_df = pd.DataFrame([{
                "Product": r.product_name, "SKU": r.sku, "Current Stock": int(r.quantity),
                "Reorder Level": int(r.reorder_level), "Reorder Quantity": int(r.reorder_quantity),
                "Date": r.sale_day, "Units Sold": int(r.units_sold or 0)
            } for r in demand_rows])
            by_product = demand_df.groupby(["Product", "SKU", "Current Stock",
                "Reorder Level", "Reorder Quantity"], as_index=False).agg(
                {"Units Sold": "sum", "Date": "nunique"})
            by_product = by_product.rename(columns={"Date": "Days with sales"})
            by_product["Average units/day"] = (by_product["Units Sold"] /
                by_product["Days with sales"].clip(lower=1)).round(2)
            by_product["Suggested reorder"] = (by_product["Reorder Level"] +
                by_product["Reorder Quantity"] - by_product["Current Stock"]).clip(lower=0)
            by_product["Status"] = by_product.apply(
                lambda r: "Low Stock" if r["Current Stock"] <= r["Reorder Level"] else "In Stock", axis=1)
            st.dataframe(by_product.sort_values(["Status", "Current Stock"]),
                use_container_width=True, hide_index=True)
            st.caption("Demand figures are descriptive; per-product ML needs sufficient dated sales history.")

finally:
    if db is not None:
        db.close()
