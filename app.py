```python
import streamlit as st
import pandas as pd
import plotly.express as px

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
# DATABASE
# =========================================================

@st.cache_resource
def get_database_session():
    """Create a database session for the application."""
    return SessionLocal()


db = get_database_session()


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🛒 ShopiFlow")

st.sidebar.markdown(
    """
    **AI/ML Business Intelligence & Retail Management System**
    """
)

menu = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Products",
        "Inventory",
        "Sales"
    ]
)


# =========================================================
# DASHBOARD
# =========================================================

if menu == "Dashboard":

    st.title("📊 ShopiFlow Dashboard")

    st.caption(
        "AI/ML-powered retail business intelligence and management"
    )

    summary = AnalyticsService.get_dashboard_summary(db)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Total Sales",
        f"₹{summary['total_sales']:,.2f}"
    )

    col2.metric(
        "Transactions",
        summary["total_transactions"]
    )

    col3.metric(
        "Products",
        summary["total_products"]
    )

    col4.metric(
        "Inventory",
        summary["total_inventory"]
    )

    col5.metric(
        "Low Stock",
        summary["low_stock"]
    )

    st.divider()

    # Sales trend
    sales_data = AnalyticsService.get_sales_by_date(db)

    if sales_data:

        sales_df = pd.DataFrame(sales_data)

        fig = px.line(
            sales_df,
            x="date",
            y="sales",
            markers=True,
            title="Sales Trend"
        )

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Sales (₹)"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # Top products
    top_products = AnalyticsService.get_top_products(db)

    if top_products:

        product_df = pd.DataFrame(top_products)

        fig = px.bar(
            product_df,
            x="product",
            y="quantity_sold",
            title="Top Selling Products"
        )

        fig.update_layout(
            xaxis_title="Product",
            yaxis_title="Quantity Sold"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# =========================================================
# PRODUCTS
# =========================================================

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
                "Price": float(product.price),
                "Cost Price": float(product.cost_price),
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


# =========================================================
# INVENTORY
# =========================================================

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

        inventory_df = pd.DataFrame(inventory_data)

        st.dataframe(
            inventory_df,
            use_container_width=True,
            hide_index=True
        )

        low_stock = InventoryService.get_low_stock_products(db)

        if low_stock:
            st.warning(
                f"{len(low_stock)} product(s) require restocking."
            )

    else:
        st.info("No inventory records available.")


# =========================================================
# SALES
# =========================================================

elif menu == "Sales":

    st.title("💳 Sales Management")

    sales = SalesService.get_all_sales(db)

    if sales:

        sales_data = [
            {
                "Sale ID": sale.sale_id,
                "Customer ID": sale.customer_id,
                "Total Amount": float(sale.total_amount),
                "Payment Method": sale.payment_method,
                "Sale Date": sale.sale_date
            }
            for sale in sales
        ]

        st.dataframe(
            pd.DataFrame(sales_data),
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No sales transactions available.")


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "ShopiFlow | AI/ML Business Intelligence & Retail Management System"
)
```
