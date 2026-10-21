from pathlib import Path

import io
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, text
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


st.set_page_config(
    page_title="ShopiFlow | Retail Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        background: #f7f9fc; border: 1px solid #e7ebf2;
        padding: 14px 16px; border-radius: 12px;
    }
    div[data-testid="stForm"] {
        border: 1px solid #e7ebf2; border-radius: 12px; padding: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("🛒 ShopiFlow")
st.sidebar.caption("AI/ML Business Intelligence & Retail Management System")
page = st.sidebar.radio(
    "Workspace",
    [
        "Dashboard",
        "Products",
        "Customers",
        "Inventory",
        "POS & Sales",
        "Data Import",
        "AI Predictions",
    ],
)
st.sidebar.divider()
st.sidebar.caption("Streamlit • PostgreSQL • Pandas • Plotly • Scikit-learn")


def money(value):
    return f"₹{float(value or 0):,.2f}"


def refresh():
    st.cache_data.clear()
    st.rerun()


def product_frame(db):
    rows = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .order_by(Product.product_name)
        .all()
    )
    return pd.DataFrame(
        [
            {
                "Product ID": p.product_id,
                "Product": p.product_name,
                "Category": p.category,
                "SKU": p.sku,
                "Selling Price (₹)": float(p.price or 0),
                "Cost Price (₹)": float(p.cost_price or 0),
                "Supplier": p.supplier or "",
            }
            for p in rows
        ]
    )


def sales_frame(db, start=None, end=None):
    query = db.query(Sale).order_by(Sale.sale_date.desc())
    if start:
        query = query.filter(
            Sale.sale_date >= datetime.combine(start, datetime.min.time())
        )
    if end:
        query = query.filter(
            Sale.sale_date
            < datetime.combine(end + timedelta(days=1), datetime.min.time())
        )

    rows = query.all()
    return pd.DataFrame(
        [
            {
                # Display ID generated from the existing primary key.
                # This does not require a new database column.
                "Order ID": f"ORD-{s.sale_id:06d}",
                "Sale ID": s.sale_id,
                "Customer Type": (
                    "Registered Customer"
                    if s.customer_id is not None
                    else "Walk-in Customer"
                ),
                "Customer ID": s.customer_id,
                "Revenue (₹)": float(s.total_amount or 0),
                "Payment Method": s.payment_method,
                "Sale Date": s.sale_date,
            }
            for s in rows
        ]
    )


def make_daily_sales(db):
    rows = (
        db.query(
            func.date(Sale.sale_date).label("sale_day"),
            func.sum(Sale.total_amount).label("revenue"),
            func.count(Sale.sale_id).label("transactions"),
        )
        .group_by(func.date(Sale.sale_date))
        .order_by(func.date(Sale.sale_date))
        .all()
    )
    return pd.DataFrame(
        [
            {
                "Date": pd.to_datetime(r.sale_day),
                "Revenue (₹)": float(r.revenue or 0),
                "Transactions": int(r.transactions or 0),
            }
            for r in rows
        ]
    )


def low_stock_frame(db):
    rows = (
        db.query(Inventory, Product)
        .join(Product, Inventory.product_id == Product.product_id)
        .filter(Product.is_active.is_(True))
        .order_by(Inventory.quantity)
        .all()
    )
    return pd.DataFrame(
        [
            {
                "Product": p.product_name,
                "SKU": p.sku,
                "Category": p.category,
                "Current Stock": i.quantity,
                "Reorder Level": i.reorder_level,
                "Suggested Restock": max(
                    i.reorder_quantity,
                    i.reorder_level - i.quantity + i.reorder_quantity,
                ),
                "Status": (
                    "Low Stock"
                    if i.quantity <= i.reorder_level
                    else "In Stock"
                ),
            }
            for i, p in rows
        ]
    )


def show_sales_charts(db):
    daily = make_daily_sales(db)
    if daily.empty:
        st.info("Record a sale or import historical sales data to unlock sales trends.")
        return

    left, right = st.columns(2)
    with left:
        fig = px.line(
            daily,
            x="Date",
            y="Revenue (₹)",
            markers=True,
            title="Revenue Trend",
            template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.bar(
            daily,
            x="Date",
            y="Transactions",
            title="Daily Transactions",
            template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)

    top = (
        db.query(
            Product.product_name.label("product"),
            func.sum(SaleItem.quantity).label("units"),
            func.sum(SaleItem.subtotal).label("revenue"),
        )
        .join(SaleItem, Product.product_id == SaleItem.product_id)
        .join(Sale, Sale.sale_id == SaleItem.sale_id)
        .group_by(Product.product_id, Product.product_name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(10)
        .all()
    )

    if top:
        top_df = pd.DataFrame(
            [
                {
                    "Product": r.product,
                    "Units Sold": int(r.units or 0),
                    "Revenue (₹)": float(r.revenue or 0),
                }
                for r in top
            ]
        )
        a, b = st.columns(2)
        with a:
            st.plotly_chart(
                px.bar(
                    top_df,
                    x="Product",
                    y="Units Sold",
                    title="Top-selling Products",
                    template="plotly_white",
                ),
                use_container_width=True,
            )
        with b:
            st.plotly_chart(
                px.pie(
                    top_df,
                    names="Product",
                    values="Revenue (₹)",
                    title="Revenue Mix by Product",
                    hole=0.45,
                ),
                use_container_width=True,
            )


# Database connection
db = None
try:
    db = SessionLocal()
    db.execute(text("SELECT 1"))
except Exception as exc:
    if db is not None:
        db.close()
    st.error("ShopiFlow cannot connect to PostgreSQL.")
    st.markdown(
        """
        **For Streamlit Cloud:** open your app's **Settings → Secrets** and configure
        either `DATABASE_URL` or the five `DB_HOST`, `DB_PORT`, `DB_NAME`,
        `DB_USER`, and `DB_PASSWORD` values. The database must be hosted online;
        `localhost` refers to the app container, not your laptop.
        """
    )
    with st.expander("Technical details"):
        st.code(str(exc)[:1500])
    st.stop()


try:
    if page == "Dashboard":
        st.title("📊 Retail Intelligence Dashboard")
        st.caption(
            "Live KPIs, product performance, inventory health and sales trends from your database."
        )
        summary = AnalyticsService.get_dashboard_summary(db)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Revenue", money(summary.get("total_sales", 0)))
        c2.metric("Transactions", f"{summary.get('total_transactions', 0):,}")
        c3.metric("Active Products", f"{summary.get('total_products', 0):,}")
        c4.metric("Units in Stock", f"{summary.get('total_inventory', 0):,}")
        c5.metric("Low-stock Items", f"{summary.get('low_stock', 0):,}")
        st.divider()

        start_col, end_col = st.columns(2)
        with start_col:
            start_date = st.date_input(
                "Trend start date",
                value=date.today() - timedelta(days=90),
                key="trend_start",
            )
        with end_col:
            end_date = st.date_input(
                "Trend end date", value=date.today(), key="trend_end"
            )

        if start_date > end_date:
            st.warning("Start date must be on or before end date.")
        else:
            daily = make_daily_sales(db)
            if not daily.empty:
                daily = daily[
                    (daily["Date"].dt.date >= start_date)
                    & (daily["Date"].dt.date <= end_date)
                ]
                if daily.empty:
                    st.info("No sales in the selected date range.")
                else:
                    st.subheader("📈 Sales and Revenue Trends")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.plotly_chart(
                            px.line(
                                daily,
                                x="Date",
                                y="Revenue (₹)",
                                markers=True,
                                title="Revenue by Day",
                                template="plotly_white",
                            ),
                            use_container_width=True,
                        )
                    with col_b:
                        st.plotly_chart(
                            px.bar(
                                daily,
                                x="Date",
                                y="Transactions",
                                title="Transactions by Day",
                                template="plotly_white",
                            ),
                            use_container_width=True,
                        )
            else:
                st.info(
                    "No sales data yet. Add a POS transaction or import a CSV from Data Import."
                )

        st.subheader("🏆 Product Performance")
        show_sales_charts(db)

        st.subheader("⚠️ Inventory Alerts")
        stock = low_stock_frame(db)
        if stock.empty:
            st.info("No inventory records yet. Add products to start tracking stock.")
        else:
            low = stock[stock["Status"] == "Low Stock"]
            if low.empty:
                st.success("All tracked products are above their reorder levels.")
            else:
                st.warning(
                    f"{len(low)} product(s) are at or below their reorder level."
                )
                st.dataframe(low, use_container_width=True, hide_index=True)

        with st.expander("Export current data"):
            products_export = product_frame(db)
            if not products_export.empty:
                st.download_button(
                    "Download products CSV",
                    products_export.to_csv(index=False).encode("utf-8"),
                    "shopiflow_products.csv",
                    "text/csv",
                )
            all_sales = sales_frame(db)
            if not all_sales.empty:
                st.download_button(
                    "Download sales CSV",
                    all_sales.to_csv(index=False).encode("utf-8"),
                    "shopiflow_sales.csv",
                    "text/csv",
                )

    elif page == "Products":
        st.title("📦 Product Management")
        add_tab, view_tab, edit_tab = st.tabs(
            ["➕ Add Product", "📋 Product Catalogue", "✏️ Update Product"]
        )

        with add_tab:
            with st.form("add_product_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                name = col1.text_input("Product name *")
                category = col2.text_input("Category *")
                sku = col1.text_input("SKU / barcode *").strip()
                supplier = col2.text_input("Supplier")
                price = col1.number_input(
                    "Selling price (₹)", min_value=0.0, value=10.0, step=1.0
                )
                cost = col2.number_input(
                    "Cost price (₹)", min_value=0.0, value=5.0, step=1.0
                )
                col3, col4, col5 = st.columns(3)
                opening_stock = col3.number_input(
                    "Opening stock", min_value=0, value=20, step=1
                )
                reorder_level = col4.number_input(
                    "Low-stock threshold", min_value=0, value=10, step=1
                )
                reorder_qty = col5.number_input(
                    "Suggested reorder quantity", min_value=1, value=50, step=1
                )
                submitted = st.form_submit_button(
                    "Save product", type="primary", use_container_width=True
                )

            if submitted:
                if not name.strip() or not category.strip() or not sku:
                    st.error("Product name, category, and SKU are required.")
                else:
                    try:
                        product = ProductService.create_product(
                            db,
                            name.strip(),
                            category.strip(),
                            sku,
                            price,
                            cost,
                            supplier.strip() or None,
                        )
                        db.add(
                            Inventory(
                                product_id=product.product_id,
                                quantity=int(opening_stock),
                                reorder_level=int(reorder_level),
                                reorder_quantity=int(reorder_qty),
                            )
                        )
                        db.commit()
                        st.success(
                            f"Added {product.product_name} and created its inventory record."
                        )
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(f"Could not add product: {exc}")

        with view_tab:
            df = product_frame(db)
            if df.empty:
                st.info("No products yet. Use Add Product to create the first record.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Export catalogue CSV",
                    df.to_csv(index=False).encode("utf-8"),
                    "shopiflow_products.csv",
                    "text/csv",
                )

        with edit_tab:
            products = ProductService.get_all_products(db)
            if not products:
                st.info("Add a product before editing.")
            else:
                options = {
                    f"{p.product_name} · {p.sku} (ID {p.product_id})": p.product_id
                    for p in products
                }
                selected_label = st.selectbox("Choose product", list(options))
                selected = ProductService.get_product(db, options[selected_label])
                with st.form("edit_product_form"):
                    new_name = st.text_input(
                        "Product name", value=selected.product_name
                    )
                    new_category = st.text_input(
                        "Category", value=selected.category
                    )
                    new_price = st.number_input(
                        "Selling price (₹)",
                        min_value=0.0,
                        value=float(selected.price),
                        step=1.0,
                    )
                    new_cost = st.number_input(
                        "Cost price (₹)",
                        min_value=0.0,
                        value=float(selected.cost_price),
                        step=1.0,
                    )
                    new_supplier = st.text_input(
                        "Supplier", value=selected.supplier or ""
                    )
                    save_edit = st.form_submit_button(
                        "Update product", type="primary"
                    )

                if save_edit:
                    try:
                        ProductService.update_product(
                            db,
                            selected.product_id,
                            product_name=new_name.strip(),
                            category=new_category.strip(),
                            price=new_price,
                            cost_price=new_cost,
                            supplier=new_supplier.strip() or None,
                        )
                        st.success("Product updated.")
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(str(exc))

    elif page == "Customers":
        st.title("👥 Customer Management")
        st.caption(
            "Register customers here. Registered customers receive a Customer ID; walk-in customers do not need one."
        )
        add_customer_tab, customer_list_tab = st.tabs(
            ["➕ Register Customer", "📋 Customer Directory"]
        )

        with add_customer_tab:
            with st.form("add_customer_form", clear_on_submit=True):
                customer_name = st.text_input("Customer name *")
                customer_email = st.text_input("Email (optional)")
                customer_phone = st.text_input("Phone (optional)")
                customer_address = st.text_area("Address (optional)")
                save_customer = st.form_submit_button(
                    "Register customer", type="primary", use_container_width=True
                )

            if save_customer:
                if not customer_name.strip():
                    st.error("Customer name is required.")
                else:
                    try:
                        customer = Customer(
                            customer_name=customer_name.strip(),
                            email=customer_email.strip() or None,
                            phone=customer_phone.strip() or None,
                            address=customer_address.strip() or None,
                        )
                        db.add(customer)
                        db.commit()
                        st.success(
                            f"Customer registered successfully. Customer ID: {customer.customer_id}"
                        )
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(
                            "Could not register customer. Check that the email is not already used. "
                            f"Details: {exc}"
                        )

        with customer_list_tab:
            customers = (
                db.query(Customer)
                .order_by(Customer.customer_id.desc())
                .all()
            )
            if not customers:
                st.info("No registered customers yet.")
            else:
                customer_df = pd.DataFrame(
                    [
                        {
                            "Customer ID": c.customer_id,
                            "Customer Name": c.customer_name,
                            "Email": c.email or "",
                            "Phone": c.phone or "",
                            "Address": c.address or "",
                        }
                        for c in customers
                    ]
                )
                st.dataframe(
                    customer_df, use_container_width=True, hide_index=True
                )
                st.download_button(
                    "Export customers CSV",
                    customer_df.to_csv(index=False).encode("utf-8"),
                    "shopiflow_customers.csv",
                    "text/csv",
                )

    elif page == "Inventory":
        st.title("📋 Inventory Management")
        inventory_tab, adjustment_tab = st.tabs(
            ["Stock Overview", "Adjust Stock"]
        )

        with inventory_tab:
            stock = low_stock_frame(db)
            if stock.empty:
                st.info("No inventory records found. Add products first.")
            else:
                low_only = st.toggle("Show only low-stock items")
                display = (
                    stock[stock["Status"] == "Low Stock"] if low_only else stock
                )
                st.dataframe(
                    display, use_container_width=True, hide_index=True
                )
                st.download_button(
                    "Export inventory CSV",
                    stock.to_csv(index=False).encode("utf-8"),
                    "shopiflow_inventory.csv",
                    "text/csv",
                )
                st.plotly_chart(
                    px.bar(
                        stock.sort_values("Current Stock"),
                        x="Product",
                        y="Current Stock",
                        color="Status",
                        title="Current Stock by Product",
                        template="plotly_white",
                    ),
                    use_container_width=True,
                )

        with adjustment_tab:
            rows = (
                db.query(Product, Inventory)
                .join(Inventory, Product.product_id == Inventory.product_id)
                .filter(Product.is_active.is_(True))
                .order_by(Product.product_name)
                .all()
            )
            if not rows:
                st.info("Add products first.")
            else:
                labels = {
                    f"{p.product_name} · current stock {i.quantity}": (p, i)
                    for p, i in rows
                }
                label = st.selectbox("Product to adjust", list(labels))
                p, inv = labels[label]
                st.write(f"Current quantity: **{inv.quantity}**")
                mode = st.radio(
                    "Adjustment type",
                    ["Add stock", "Set exact stock"],
                    horizontal=True,
                )
                qty = st.number_input(
                    "Quantity",
                    min_value=0 if mode == "Set exact stock" else 1,
                    value=1,
                    step=1,
                )

                if st.button("Save stock adjustment", type="primary"):
                    try:
                        if mode == "Add stock":
                            InventoryService.add_stock(
                                db, p.product_id, int(qty)
                            )
                        else:
                            InventoryService.update_stock(
                                db, p.product_id, int(qty)
                            )
                        st.success("Inventory updated.")
                        st.rerun()
                    except Exception as exc:
                        db.rollback()
                        st.error(str(exc))

    elif page == "POS & Sales":
        st.title("🧾 POS & Sales")
        st.caption(
            "Record a sale, select customer type, calculate the bill, and automatically deduct stock."
        )
        products = ProductService.get_all_products(db)

        if not products:
            st.info(
                "Add products and opening stock in Product Management before recording sales."
            )
        else:
            with st.form("pos_form"):
                product_options = {
                    f"{p.product_name} · {p.sku} — {money(p.price)}": p
                    for p in products
                }
                chosen = st.selectbox("Product", list(product_options))
                product = product_options[chosen]
                inv = InventoryService.get_inventory(db, product.product_id)
                available = inv.quantity if inv else 0
                st.caption(f"Available stock: {available}")

                quantity = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=max(1, available),
                    value=1,
                    step=1,
                    disabled=(available == 0),
                )

                customer_type = st.radio(
                    "Customer Type",
                    ["Walk-in Customer", "Registered Customer"],
                    horizontal=True,
                )
                customer_id = None
                checkout_disabled = available == 0

                if customer_type == "Registered Customer":
                    customer_rows = (
                        db.query(Customer)
                        .order_by(Customer.customer_name)
                        .all()
                    )
                    if not customer_rows:
                        st.warning(
                            "No registered customers found. Register a customer in the Customers page first."
                        )
                        checkout_disabled = True
                    else:
                        customer_options = {
                            f"{c.customer_name} (ID: {c.customer_id})": c.customer_id
                            for c in customer_rows
                        }
                        selected_customer = st.selectbox(
                            "Select registered customer",
                            list(customer_options.keys()),
                        )
                        customer_id = customer_options[selected_customer]
                        st.info(f"Customer ID: {customer_id}")

                if customer_type == "Walk-in Customer":
                    st.info("Walk-in Customer — no customer ID is required.")

                payment = st.selectbox(
                    "Payment method",
                    ["Cash", "UPI", "Card", "Bank Transfer", "Other"],
                )
                st.write(
                    f"**Bill total: {money(float(product.price) * quantity)}**"
                )
                checkout = st.form_submit_button(
                    "Complete sale",
                    type="primary",
                    use_container_width=True,
                    disabled=checkout_disabled,
                )

            if checkout:
                try:
                    sale = SalesService.create_sale(
                        db,
                        customer_id,
                        [
                            {
                                "product_id": product.product_id,
                                "quantity": int(quantity),
                            }
                        ],
                        payment,
                    )
                    order_id = f"ORD-{sale.sale_id:06d}"
                    customer_id_text = (
                        str(customer_id)
                        if customer_id is not None
                        else "N/A (Walk-in)"
                    )
                    st.success(
                        f"Order {order_id} completed! "
                        f"Customer Type: {customer_type} | "
                        f"Customer ID: {customer_id_text} | "
                        f"Total: {money(sale.total_amount)}"
                    )
                    st.rerun()
                except Exception as exc:
                    db.rollback()
                    st.error(f"Sale was not saved: {exc}")

        st.divider()
        st.subheader("Recent transactions")
        all_sales = sales_frame(db)
        if all_sales.empty:
            st.info("No transactions recorded yet.")
        else:
            st.dataframe(
                all_sales.sort_values("Sale Date", ascending=False).head(100),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Export sales CSV",
                all_sales.to_csv(index=False).encode("utf-8"),
                "shopiflow_sales.csv",
                "text/csv",
            )

    elif page == "Data Import":
        st.title("📥 Import Data from Your Computer")
        st.write(
            "Upload CSV files to populate ShopiFlow without editing the database manually."
        )

        with st.expander("1. Product CSV format", expanded=True):
            st.code(
                "product_name,category,sku,price,cost_price,supplier,quantity,reorder_level,reorder_quantity\n"
                "Tea,Groceries,TEA001,120,85,ABC Supplier,40,10,30\n"
                "Notebook,Stationery,NOTE001,60,35,XYZ Supplier,25,5,20",
                language="csv",
            )

        product_file = st.file_uploader(
            "Upload product CSV", type=["csv"], key="product_csv"
        )
        if product_file is not None:
            try:
                df = pd.read_csv(product_file)
                st.dataframe(df.head(10), use_container_width=True)
                if st.button("Import products", type="primary"):
                    required = {
                        "product_name",
                        "category",
                        "sku",
                        "price",
                        "cost_price",
                    }
                    if not required.issubset(df.columns):
                        st.error(
                            "Required columns: product_name, category, sku, price, cost_price."
                        )
                    else:
                        added = 0
                        errors = []
                        for idx, row in df.iterrows():
                            try:
                                if pd.isna(row["sku"]):
                                    raise ValueError("Missing SKU")
                                sku = str(row["sku"]).strip()
                                if not sku:
                                    raise ValueError("Missing SKU")

                                product = ProductService.create_product(
                                    db,
                                    str(row["product_name"]).strip(),
                                    str(row["category"]).strip(),
                                    sku,
                                    float(row["price"]),
                                    float(row["cost_price"]),
                                    (
                                        None
                                        if pd.isna(row.get("supplier", None))
                                        else str(row.get("supplier")).strip()
                                        or None
                                    ),
                                )
                                q = (
                                    int(row.get("quantity", 0))
                                    if pd.notna(row.get("quantity", 0))
                                    else 0
                                )
                                rl = (
                                    int(row.get("reorder_level", 10))
                                    if pd.notna(row.get("reorder_level", 10))
                                    else 10
                                )
                                rq = (
                                    int(row.get("reorder_quantity", 50))
                                    if pd.notna(row.get("reorder_quantity", 50))
                                    else 50
                                )
                                if q < 0 or rl < 0 or rq < 1:
                                    raise ValueError(
                                        "Stock/reorder values are invalid"
                                    )

                                db.add(
                                    Inventory(
                                        product_id=product.product_id,
                                        quantity=q,
                                        reorder_level=rl,
                                        reorder_quantity=rq,
                                    )
                                )
                                db.commit()
                                added += 1
                            except Exception as exc:
                                db.rollback()
                                errors.append(f"Row {idx + 2}: {exc}")

                        st.success(f"Imported {added} product(s).")
                        if errors:
                            st.warning(
                                "Some rows were skipped:\n"
                                + "\n".join(errors[:15])
                            )
                        st.rerun()
            except Exception as exc:
                st.error(f"Could not read product CSV: {exc}")

        st.divider()
        with st.expander("2. Historical sales CSV format", expanded=True):
            st.write(
                "One row per product line. Existing product SKUs must already be in ShopiFlow. "
                "Use order_id to group lines from one transaction. Optional customer_id must already "
                "exist in the customers table. Historical imports do not deduct current stock. "
                "The original order_id is used to group lines during import; displayed order IDs "
                "are generated from the ShopiFlow sale ID."
            )
            st.code(
                "order_id,sku,quantity,sale_date,payment_method,customer_id\n"
                "ORD001,TEA001,2,2026-10-01,UPI,1\n"
                "ORD001,NOTE001,1,2026-10-01,UPI,1\n"
                "ORD002,TEA001,1,2026-10-02,Cash,",
                language="csv",
            )

        sales_file = st.file_uploader(
            "Upload historical sales CSV", type=["csv"], key="sales_csv"
        )
        if sales_file is not None:
            try:
                df = pd.read_csv(sales_file)
                st.dataframe(df.head(10), use_container_width=True)

                if st.button("Import historical sales", type="primary"):
                    required = {"sku", "quantity", "sale_date"}
                    if not required.issubset(df.columns):
                        st.error(
                            "Required columns: sku, quantity, sale_date."
                        )
                    else:
                        df["quantity"] = pd.to_numeric(
                            df["quantity"], errors="coerce"
                        )
                        df["sale_date"] = pd.to_datetime(
                            df["sale_date"], errors="coerce"
                        )

                        if (
                            df["quantity"].isna().any()
                            or (df["quantity"] <= 0).any()
                            or (df["quantity"] % 1 != 0).any()
                            or df["sale_date"].isna().any()
                        ):
                            st.error(
                                "Fix invalid quantities or dates before importing. "
                                "Quantities must be positive whole numbers."
                            )
                        else:
                            if "order_id" in df.columns:
                                df["order_id"] = (
                                    df["order_id"].fillna("").astype(str).str.strip()
                                )
                                missing_order = df["order_id"].eq("")
                                df.loc[missing_order, "order_id"] = [
                                    f"ROW{i}"
                                    for i in range(int(missing_order.sum()))
                                ]
                            else:
                                df["order_id"] = [
                                    f"ROW{i}" for i in range(len(df))
                                ]

                            if "payment_method" not in df.columns:
                                df["payment_method"] = "Imported"
                            else:
                                df["payment_method"] = (
                                    df["payment_method"].fillna("Imported").astype(str)
                                )

                            imported = 0
                            errors = []

                            for order_id, group in df.groupby(
                                "order_id", sort=False
                            ):
                                try:
                                    if group["sale_date"].nunique() > 1:
                                        raise ValueError(
                                            "Rows in one order have different sale dates."
                                        )
                                    if group["payment_method"].nunique() > 1:
                                        raise ValueError(
                                            "Rows in one order have different payment methods."
                                        )

                                    sale_date = pd.to_datetime(
                                        group.iloc[0]["sale_date"]
                                    ).to_pydatetime()
                                    payment_method = str(
                                        group.iloc[0]["payment_method"]
                                    )[:50]

                                    customer_id = None
                                    if "customer_id" in group.columns:
                                        customer_values = (
                                            group["customer_id"]
                                            .dropna()
                                            .astype(str)
                                            .str.strip()
                                        )
                                        customer_values = customer_values[
                                            customer_values != ""
                                        ]
                                        if len(customer_values.unique()) > 1:
                                            raise ValueError(
                                                "Order has multiple customer IDs."
                                            )
                                        if not customer_values.empty:
                                            customer_id_raw = customer_values.iloc[0]
                                            customer_id_num = float(customer_id_raw)
                                            if not customer_id_num.is_integer():
                                                raise ValueError(
                                                    "Customer ID must be a whole number."
                                                )
                                            customer_id = int(customer_id_num)
                                            customer = (
                                                db.query(Customer)
                                                .filter(
                                                    Customer.customer_id
                                                    == customer_id
                                                )
                                                .first()
                                            )
                                            if not customer:
                                                raise ValueError(
                                                    f"Customer ID {customer_id} does not exist."
                                                )

                                    total = 0.0
                                    lines = []
                                    for _, row in group.iterrows():
                                        sku = str(row["sku"]).strip()
                                        product = (
                                            db.query(Product)
                                            .filter(
                                                Product.sku == sku,
                                                Product.is_active.is_(True),
                                            )
                                            .first()
                                        )
                                        if not product:
                                            raise ValueError(
                                                f"SKU not found: {sku}"
                                            )

                                        q = int(row["quantity"])
                                        subtotal = float(product.price) * q
                                        total += subtotal
                                        lines.append((product, q, subtotal))

                                    sale = Sale(
                                        customer_id=customer_id,
                                        total_amount=total,
                                        payment_method=payment_method,
                                        sale_date=sale_date,
                                    )
                                    db.add(sale)
                                    db.flush()

                                    for product, q, subtotal in lines:
                                        db.add(
                                            SaleItem(
                                                sale_id=sale.sale_id,
                                                product_id=product.product_id,
                                                quantity=q,
                                                unit_price=product.price,
                                                subtotal=subtotal,
                                            )
                                        )

                                    db.commit()
                                    imported += 1

                                except Exception as exc:
                                    db.rollback()
                                    errors.append(f"Order {order_id}: {exc}")

                            st.success(
                                f"Imported {imported} transaction(s)."
                            )
                            if errors:
                                st.warning(
                                    "Some transactions were skipped:\n"
                                    + "\n".join(errors[:15])
                                )
                            st.rerun()

            except Exception as exc:
                st.error(f"Could not read sales CSV: {exc}")

    elif page == "AI Predictions":
        st.title("🤖 AI/ML Predictions")
        st.caption(
            "Random Forest baseline for sales forecasting and descriptive inventory demand summaries."
        )
        daily = make_daily_sales(db)

        if daily.empty or len(daily) < 5:
            st.warning(
                "At least 5 distinct days with recorded sales are recommended before generating a demo forecast. "
                "Import historical sales to build a more meaningful training set."
            )
        else:
            daily = daily.sort_values("Date").copy()
            daily["day_of_week"] = daily["Date"].dt.dayofweek
            daily["month"] = daily["Date"].dt.month
            daily["day"] = daily["Date"].dt.day
            daily["lag_1"] = daily["Revenue (₹)"].shift(1)
            training = daily.dropna(subset=["lag_1"])

            if len(training) >= 4:
                X = training[["day_of_week", "month", "day", "lag_1"]]
                y = training["Revenue (₹)"]
                model = RandomForestRegressor(
                    n_estimators=150, random_state=42
                )
                model.fit(X, y)

                future_rows = []
                last_date = daily["Date"].max()
                last_revenue = float(daily.iloc[-1]["Revenue (₹)"])

                for step in range(1, 8):
                    d = last_date + pd.Timedelta(days=step)
                    features = pd.DataFrame(
                        [
                            {
                                "day_of_week": d.dayofweek,
                                "month": d.month,
                                "day": d.day,
                                "lag_1": last_revenue,
                            }
                        ]
                    )
                    pred = max(
                        0.0, float(model.predict(features)[0])
                    )
                    future_rows.append(
                        {"Date": d, "Predicted Revenue (₹)": pred}
                    )
                    last_revenue = pred

                forecast = pd.DataFrame(future_rows)
                st.subheader("📈 7-day Sales Forecast")
                st.info(
                    "This is an educational baseline trained on the sales currently stored in ShopiFlow. "
                    "Forecast quality depends on data volume and quality; it is not a guarantee of future sales."
                )
                st.metric(
                    "Forecast total (next 7 days)",
                    money(forecast["Predicted Revenue (₹)"].sum()),
                )

                hist = daily[["Date", "Revenue (₹)"]].rename(
                    columns={"Revenue (₹)": "Revenue"}
                )
                pred_chart = forecast.rename(
                    columns={"Predicted Revenue (₹)": "Revenue"}
                )
                hist["Type"] = "Historical"
                pred_chart["Type"] = "Forecast"
                combined = pd.concat(
                    [
                        hist[["Date", "Revenue", "Type"]],
                        pred_chart[["Date", "Revenue", "Type"]],
                    ]
                )
                st.plotly_chart(
                    px.line(
                        combined,
                        x="Date",
                        y="Revenue",
                        color="Type",
                        markers=True,
                        title="Historical and Forecast Revenue",
                        template="plotly_white",
                    ),
                    use_container_width=True,
                )
                st.dataframe(
                    forecast, use_container_width=True, hide_index=True
                )
            else:
                st.info(
                    "More distinct sales days are needed to train the sales model."
                )

        st.divider()
        st.subheader("📦 Inventory Demand & Reorder Suggestions")
        demand_rows = (
            db.query(
                Product.product_id,
                Product.product_name,
                Product.sku,
                Inventory.quantity,
                Inventory.reorder_level,
                Inventory.reorder_quantity,
                func.date(Sale.sale_date).label("sale_day"),
                func.sum(SaleItem.quantity).label("units_sold"),
            )
            .join(Inventory, Inventory.product_id == Product.product_id)
            .outerjoin(SaleItem, SaleItem.product_id == Product.product_id)
            .outerjoin(Sale, Sale.sale_id == SaleItem.sale_id)
            .filter(Product.is_active.is_(True))
            .group_by(
                Product.product_id,
                Product.product_name,
                Product.sku,
                Inventory.quantity,
                Inventory.reorder_level,
                Inventory.reorder_quantity,
                func.date(Sale.sale_date),
            )
            .all()
        )

        if not demand_rows:
            st.info("Add products and sales to see product-demand information.")
        else:
            demand_df = pd.DataFrame(
                [
                    {
                        "Product": r.product_name,
                        "SKU": r.sku,
                        "Current Stock": int(r.quantity),
                        "Reorder Level": int(r.reorder_level),
                        "Reorder Quantity": int(r.reorder_quantity),
                        "Date": r.sale_day,
                        "Units Sold": int(r.units_sold or 0),
                    }
                    for r in demand_rows
                ]
            )
            by_product = demand_df.groupby(
                [
                    "Product",
                    "SKU",
                    "Current Stock",
                    "Reorder Level",
                    "Reorder Quantity",
                ],
                as_index=False,
            ).agg(
                {
                    "Units Sold": "sum",
                    "Date": "nunique",
                }
            )
            by_product = by_product.rename(
                columns={"Date": "Days with sales"}
            )
            by_product["Average units/day"] = (
                by_product["Units Sold"]
                / by_product["Days with sales"].clip(lower=1)
            ).round(2)
            by_product["Suggested reorder"] = (
                by_product["Reorder Level"]
                + by_product["Reorder Quantity"]
                - by_product["Current Stock"]
            ).clip(lower=0)
            by_product["Status"] = by_product.apply(
                lambda r: (
                    "Low Stock"
                    if r["Current Stock"] <= r["Reorder Level"]
                    else "In Stock"
                ),
                axis=1,
            )
            st.dataframe(
                by_product.sort_values(["Status", "Current Stock"]),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Demand summary is descriptive. A per-product ML model should be trained only after sufficient dated sales history exists."
            )

finally:
    if db is not None:
        db.close()

