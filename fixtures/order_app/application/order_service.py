from order_app.domain.order import Order
from order_app.infrastructure.repository import InMemoryOrderRepository
from order_app.presentation.confirmation import format_confirmation
from order_app.pricing.policy import PricingPolicy


class OrderService:
    def __init__(
        self,
        pricing: PricingPolicy,
        repository: InMemoryOrderRepository,
    ) -> None:
        self.pricing = pricing
        self.repository = repository

    def place(self, order: Order) -> str:
        total = self.pricing.discounted_total(order)
        self.repository.save(order, total)
        return format_confirmation(order, total)
