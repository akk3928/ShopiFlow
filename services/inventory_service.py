
from sqlalchemy.orm import Session

from models.inventory import Inventory


class InventoryService:
    """Business logic for inventory management."""

    @staticmethod
    def get_inventory(db: Session, product_id: int):
        """Get inventory for a product."""

        return (
            db.query(Inventory)
            .filter(Inventory.product_id == product_id)
            .first()
        )

    @staticmethod
    def get_all_inventory(db: Session):
        """Return all inventory records."""

        return (
            db.query(Inventory)
            .order_by(Inventory.product_id)
            .all()
        )

    @staticmethod
    def update_stock(
        db: Session,
        product_id: int,
        quantity: int
    ):
        """Set the current stock quantity."""

        inventory = InventoryService.get_inventory(
            db,
            product_id
        )

        if not inventory:
            raise ValueError("Inventory record not found.")

        if quantity < 0:
            raise ValueError("Stock quantity cannot be negative.")

        inventory.quantity = quantity

        db.commit()
        db.refresh(inventory)

        return inventory

    @staticmethod
    def add_stock(
        db: Session,
        product_id: int,
        quantity: int
    ):
        """Add stock to existing inventory."""

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        inventory = InventoryService.get_inventory(
            db,
            product_id
        )

        if not inventory:
            raise ValueError("Inventory record not found.")

        inventory.quantity += quantity

        db.commit()
        db.refresh(inventory)

        return inventory

    @staticmethod
    def remove_stock(
        db: Session,
        product_id: int,
        quantity: int
    ):
        """Remove stock after a sale."""

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        inventory = InventoryService.get_inventory(
            db,
            product_id
        )

        if not inventory:
            raise ValueError("Inventory record not found.")

        if inventory.quantity < quantity:
            raise ValueError("Insufficient stock.")

        inventory.quantity -= quantity

        db.commit()
        db.refresh(inventory)

        return inventory

    @staticmethod
    def get_low_stock_products(db: Session):
        """Return products that have reached their reorder level."""

        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.quantity <= Inventory.reorder_level
            )
            .order_by(Inventory.quantity)
            .all()
        )

        return inventory


