
from sqlalchemy.orm import Session

from models.product import Product
from models.sales import Sale, SaleItem
from models.inventory import Inventory


class SalesService:
    """Business logic for sales and POS transactions."""

    @staticmethod
    def create_sale(
        db: Session,
        customer_id: int | None,
        items: list[dict],
        payment_method: str
    ):
        """
        Create a complete sales transaction.

        Each item should contain:
        {
            "product_id": int,
            "quantity": int
        }
        """

        if not items:
            raise ValueError("Sale must contain at least one item.")

        total_amount = 0
        sale_items = []

        # Validate products and stock first
        for item in items:

            product = (
                db.query(Product)
                .filter(
                    Product.product_id == item["product_id"],
                    Product.is_active == True
                )
                .first()
            )

            if not product:
                raise ValueError(
                    f"Product {item['product_id']} not found."
                )

            quantity = item["quantity"]

            if quantity <= 0:
                raise ValueError(
                    "Quantity must be greater than zero."
                )

            inventory = (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == product.product_id
                )
                .first()
            )

            if not inventory:
                raise ValueError(
                    f"No inventory record for {product.product_name}."
                )

            if inventory.quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for {product.product_name}."
                )

            subtotal = float(product.price) * quantity
            total_amount += subtotal

            sale_items.append({
                "product": product,
                "inventory": inventory,
                "quantity": quantity,
                "unit_price": product.price,
                "subtotal": subtotal
            })

        # Create sale
        sale = Sale(
            customer_id=customer_id,
            total_amount=total_amount,
            payment_method=payment_method
        )

        db.add(sale)
        db.flush()

        # Create sale items and update inventory
        for item in sale_items:

            sale_item = SaleItem(
                sale_id=sale.sale_id,
                product_id=item["product"].product_id,
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                subtotal=item["subtotal"]
            )

            db.add(sale_item)

            item["inventory"].quantity -= item["quantity"]

        db.commit()
        db.refresh(sale)

        return sale

    @staticmethod
    def get_sale(db: Session, sale_id: int):
        """Get a sale by ID."""

        return (
            db.query(Sale)
            .filter(Sale.sale_id == sale_id)
            .first()
        )

    @staticmethod
    def get_all_sales(db: Session):
        """Return all sales."""

        return (
            db.query(Sale)
            .order_by(Sale.sale_date.desc())
            .all()
        )

    @staticmethod
    def get_sale_items(db: Session, sale_id: int):
        """Return all items belonging to a sale."""

        return (
            db.query(SaleItem)
            .filter(SaleItem.sale_id == sale_id)
            .all()
        )


