```python
from sqlalchemy.orm import Session

from models.product import Product


class ProductService:
    """Business logic for product management."""

    @staticmethod
    def create_product(
        db: Session,
        product_name: str,
        category: str,
        sku: str,
        price: float,
        cost_price: float,
        supplier: str | None = None
    ):
        """Create a new product."""

        existing_product = (
            db.query(Product)
            .filter(Product.sku == sku)
            .first()
        )

        if existing_product:
            raise ValueError("A product with this SKU already exists.")

        product = Product(
            product_name=product_name,
            category=category,
            sku=sku,
            price=price,
            cost_price=cost_price,
            supplier=supplier
        )

        db.add(product)
        db.commit()
        db.refresh(product)

        return product

    @staticmethod
    def get_product(db: Session, product_id: int):
        """Get a product by ID."""
        return (
            db.query(Product)
            .filter(Product.product_id == product_id)
            .first()
        )

    @staticmethod
    def get_all_products(db: Session):
        """Return all active products."""
        return (
            db.query(Product)
            .filter(Product.is_active == True)
            .order_by(Product.product_id)
            .all()
        )

    @staticmethod
    def update_product(db: Session, product_id: int, **updates):
        """Update product information."""

        product = ProductService.get_product(db, product_id)

        if not product:
            raise ValueError("Product not found.")

        for field, value in updates.items():
            if hasattr(product, field):
                setattr(product, field, value)

        db.commit()
        db.refresh(product)

        return product

    @staticmethod
    def delete_product(db: Session, product_id: int):
        """Soft-delete a product."""

        product = ProductService.get_product(db, product_id)

        if not product:
            raise ValueError("Product not found.")

        product.is_active = False

        db.commit()

        return product
```

