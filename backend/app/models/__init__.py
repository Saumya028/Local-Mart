from app.models.base import Base
from app.models.profile import Profile
from app.models.address import Address
from app.models.shop import Shop
from app.models.product import Product
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.audit_log import AuditLog

# Alembic's env.py imports `Base` from here and reads `Base.metadata`.
# Every model file must be imported above, or Alembic won't know it exists
# when generating migrations.
__all__ = [
    "Base",
    "Profile",
    "Address",
    "Shop",
    "Product",
    "Order",
    "OrderItem",
    "Payment",
    "AuditLog",
]
