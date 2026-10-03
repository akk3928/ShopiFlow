```python
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime
from sqlalchemy.sql import func

from config.database import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=False)
    supplier = Column(String(150))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Product(product_id={self.product_id}, name='{self.product_name}')>"
```

