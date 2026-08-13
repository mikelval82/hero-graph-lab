from order_app.application.order_service import OrderService
from order_app.infrastructure.repository import InMemoryOrderRepository
from order_app.pricing.policy import PricingPolicy


def build_service() -> OrderService:
    return OrderService(PricingPolicy(), InMemoryOrderRepository())
