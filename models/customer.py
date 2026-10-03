
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from config.database import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True)
    phone = Column(String(20))
    address = Column(String(250))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Customer(customer_id={self.customer_id}, name='{self.customer_name}')>"


