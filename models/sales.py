
from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from config.database import Base


class Sale(Base):
    __tablename__ = "sales"

    sale_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(
        Integer,
        ForeignKey("customers.customer_id"),
        nullable=True
    )
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(50), nullable=False)
    sale_date = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Sale(sale_id={self.sale_id}, total={self.total_amount})>"


class SaleItem(Base):
    __tablename__ = "sale_items"

    sale_item_id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(
        Integer,
        ForeignKey("sales.sale_id"),
        nullable=False
    )
    product_id = Column(
        Integer,
        ForeignKey("products.product_id"),
        nullable=False
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    def __repr__(self):
        return f"<SaleItem(sale_item_id={self.sale_item_id}, quantity={self.quantity})>"


