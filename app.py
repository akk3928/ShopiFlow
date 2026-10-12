
import streamlit as st
import pandas as pd
import plotly.express as px

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config.database import SessionLocal
from services.product_service import ProductService
from services.inventory_service import InventoryService
from services.sales_service import SalesService
from dashboard.analytics import AnalyticsService


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ShopiFlow",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

@st.cache_resource
def get_session_factory():
    """Cache the session factory, not an individual DB session."""
    return SessionLocal


try:
    SessionFactory = get_session_factory()
    db = SessionFactory()

    # Test the connection before querying the application.
    db.execute(text("SELECT 1"))

except SQLAlchemyError as exc:
    st.error("Unable to connect to the ShopiFlow database.")
    st.warning(
        "Check your PostgreSQL connection URL, database credentials, "
        "network access, and Streamlit Cloud secrets."
    )
    with st.expander("Technical error details"):
        st.code(str(exc)[:2000])

    try:
        db.close()
    except Exception:
        pass

    st.stop()

except Exception as exc:
    st.error("ShopiFlow could not initialize its database session.")
    with st.expander("Technical error details"):
        st.code(str(exc)[:2000])
    st.stop()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def show_dataframe(data, required_columns=None):
    """Convert records to a DataFrame and validate chart/table columns."""
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if required_columns:
        missing = [
            column for column in required_columns
            if column not in df.columns
        ]
        if missing:
            st.warning(
                "Some expected data columns are missing: "
                + ", ".join(missing)
            )
            return pd.DataFrame()

    return df


def show_sales_chart(data):
    """Render the sales trend only when its data is valid."""
    df = show_dataframe(data, ["date", "sales"])

    if df.empty:
        st.info("No valid sales trend data is available yet.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")

    df = df.dropna(subset=["date", "sales"])

    if df.empty:
        st.info("Sales data does not contain valid dates and amounts.")
        return

    df = (
        df.groupby("date", as_index=False)["sales"]
        .sum()
        .sort_values("date")
    )

    fig = px.line(
        df,
        x="date",
        y="sales",
        markers=True,
        title="Sales Trend"
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Sales (₹)",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)


def show_top_products_chart(data):
    """Render top-selling products after validating their data."""
    df = show_dataframe(
        data,
        ["product", "quantity_sold"]
    )

    if df.empty:
        st.info("No top-selling product data is available yet.")
        return

    df["quantity_sold"] = pd.to_numeric(
        df["quantity_sold"],
        errors="coerce"
    )

    df = df.dropna(subset=["product", "quantity_sold"])

    if df.empty:
        st.info("There are no valid product sales records to display.")
        return

    df = (
        df.groupby("product", as_index=False)["quantity_sold"]
        .sum()
        .sort_values("quantity_sold", ascending=False)
        .head(10)
    )

    fig = px.bar(
        df,
        x="product",
        y="quantity_sold",
        title="Top Selling Products",
        template="plotly_white"
    )

    fig.update_layout(
        xaxis_title="Product",
        yaxis_title="Quantity Sold"
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🛒 ShopiFlow")

st.sidebar.markdown(
    "**AI/ML Business Intelligence & Retail Management System**"
)

menu = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Products", "Inventory", "Sales"]
)


# =========================================================
# APPLICATION
# =========================================================

try:

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    if menu == "Dashboard":

        st.title("📊 ShopiFlow Dashboard")
        st.caption(
            "AI/ML-powered retail business intelligence and management"
        )

        summary = AnalyticsService.get_dashboard_summary(db)

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric(
            "Total Sales",
            f"₹{float(summary.get('total_sales') or 0):,.2f}"
        )

        col2.metric(
            "Transactions",
            int(summary.get("total_transactions") or 0)
        )

        col3.metric(
            "Products",
            int(summary.get("total_products") or 0)
        )

        col4.metric(
            "Inventory",
            int(summary.get("total_inventory") or 0)
        )

        col5.metric(
            "Low Stock",
            int(summary.get("low_stock") or 0)
        )

        st.divider()

        st.subheader("📈 Sales Analysis")
        sales_data = AnalyticsService.get_sales_by_date(db)
        show_sales_chart(sales_data)

        st.divider()

        st.subheader("🏆 Product Performance")
        top_products = AnalyticsService.get_top_products(db)
        show_top_products_chart(top_products)

    # -----------------------------------------------------
    # PRODUCTS
    # -----------------------------------------------------

    elif menu == "Products":

        st.title("📦 Product Management")

        products = ProductService.get_all_products(db)

        if products:
            product_data = [
                {
                    "ID": product.product_id,
                    "Product": product.product_name,
                    "Category": product.category,
                    "SKU": product.sku,
                    "Price": float(product.price or 0),
                    "Cost Price": float(product.cost_price or 0),
                    "Supplier": product.supplier
                }
                for product in products
            ]

            st.dataframe(
                pd.DataFrame(product_data),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No products available.")

    # -----------------------------------------------------
    # INVENTORY
    # -----------------------------------------------------

    elif menu == "Inventory":

        st.title("📋 Inventory Management")

        inventory = InventoryService.get_all_inventory(db)

        if inventory:
            inventory_data = [
                {
                    "Inventory ID": item.inventory_id,
                    "Product ID": item.product_id,
                    "Quantity": item.quantity,
                    "Reorder Level": item.reorder_level,
                    "Reorder Quantity": item.reorder_quantity,
                    "Status": (
                        "Low Stock"
                        if item.quantity <= item.reorder_level
                        else "In Stock"
                    )
                }
                for item in inventory
            ]

            st.dataframe(
                pd.DataFrame(inventory_data),
                use_container_width=True,
                hide_index=True
            )

            low_stock = InventoryService.get_low_stock_products(db)

            if low_stock:
                st.warning(
                    f"{len(low_stock)} product(s) require restocking."
                )
            else:
                st.success("No products are below their reorder levels.")

        else:
            st.info("No inventory records available.")

    # -----------------------------------------------------
    # SALES
    # -----------------------------------------------------

    elif menu == "Sales":

        st.title("💳 Sales Management")

        sales = SalesService.get_all_sales(db)

        if sales:
            sales_data = [
                {
                    "Sale ID": sale.sale_id,
                    "Customer ID": sale.customer_id,
                    "Total Amount": float(sale.total_amount or 0),
                    "Payment Method": sale.payment_method,
                    "Sale Date": sale.sale_date
                }
                for sale in sales
            ]

            sales_df = pd.DataFrame(sales_data)

            st.dataframe(
                sales_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No sales transactions available.")

except SQLAlchemyError as exc:
    st.error("A database query failed while loading this page.")

    with st.expander("Technical error details"):
        st.code(str(exc)[:2000])

    st.info(
        "Check that your database tables and columns match the "
        "models and service queries used by ShopiFlow."
    )

except Exception as exc:
    st.error("An unexpected error occurred while loading this page.")

    with st.expander("Technical error details"):
        st.code(str(exc)[:2000])

finally:
    db.close()


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "ShopiFlow | AI/ML Business Intelligence & Retail Management System"
)
