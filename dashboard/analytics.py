
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.product import Product
from models.sales import Sale, SaleItem
from models.inventory import Inventory


class AnalyticsService:
    """Analytics and KPI calculations for the ShopiFlow dashboard."""

    @staticmethod
    def get_total_sales(db: Session):
        """Return total sales revenue."""

        result = (
            db.query(func.coalesce(func.sum(Sale.total_amount), 0))
            .scalar()
        )

        return float(result)

    @staticmethod
    def get_total_transactions(db: Session):
        """Return the total number of sales transactions."""

        return db.query(Sale).count()

    @staticmethod
    def get_total_products(db: Session):
        """Return the number of active products."""

        return (
            db.query(Product)
            .filter(Product.is_active == True)
            .count()
        )

    @staticmethod
    def get_total_inventory(db: Session):
        """Return the total quantity of products in stock."""

        result = (
            db.query(func.coalesce(func.sum(Inventory.quantity), 0))
            .scalar()
        )

        return int(result)

    @staticmethod
    def get_low_stock_count(db: Session):
        """Return the number of products at or below reorder level."""

        return (
            db.query(Inventory)
            .filter(
                Inventory.quantity <= Inventory.reorder_level
            )
            .count()
        )

    @staticmethod
    def get_sales_by_date(db: Session):
        """Return daily sales totals for dashboard charts."""

        results = (
            db.query(
                func.date(Sale.sale_date).label("sale_date"),
                func.sum(Sale.total_amount).label("total_sales")
            )
            .group_by(func.date(Sale.sale_date))
            .order_by(func.date(Sale.sale_date))
            .all()
        )

        return [
            {
                "date": row.sale_date,
                "sales": float(row.total_sales)
            }
            for row in results
        ]

    @staticmethod
    def get_sales_by_payment_method(db: Session):
        """Return sales grouped by payment method."""

        results = (
            db.query(
                Sale.payment_method,
                func.sum(Sale.total_amount).label("total_sales")
            )
            .group_by(Sale.payment_method)
            .order_by(func.sum(Sale.total_amount).desc())
            .all()
        )

        return [
            {
                "payment_method": row.payment_method,
                "sales": float(row.total_sales)
            }
            for row in results
        ]

    @staticmethod
    def get_top_products(db: Session, limit: int = 10):
        """Return products with the highest sales quantity."""

        results = (
            db.query(
                Product.product_name,
                func.sum(SaleItem.quantity).label("quantity_sold"),
                func.sum(SaleItem.subtotal).label("revenue")
            )
            .join(
                SaleItem,
                Product.product_id == SaleItem.product_id
            )
            .group_by(Product.product_id, Product.product_name)
            .order_by(
                func.sum(SaleItem.quantity).desc()
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "product": row.product_name,
                "quantity_sold": int(row.quantity_sold),
                "revenue": float(row.revenue)
            }
            for row in results
        ]

    @staticmethod
    def get_dashboard_summary(db: Session):
        """Return the main KPI values for the dashboard."""

        return {
            "total_sales": AnalyticsService.get_total_sales(db),
            "total_transactions": AnalyticsService.get_total_transactions(db),
            "total_products": AnalyticsService.get_total_products(db),
            "total_inventory": AnalyticsService.get_total_inventory(db),
            "low_stock": AnalyticsService.get_low_stock_count(db)
        }

