from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    customer_id: str
    amount: float


class PricingPolicy:
    def discounted_total(self, order: Order) -> float:
        discount = 0.1 if order.amount >= 100 else 0
        return order.amount * (1 - discount)


class OrderService:
    def __init__(self, pricing: PricingPolicy) -> None:
        self.pricing = pricing

    def place(self, order: Order) -> str:
        total = self.pricing.discounted_total(order)
        return format_confirmation(order, total)


def format_confirmation(order: Order, total: float) -> str:
    return f"{order.customer_id}: {total:.2f}"


def build_service() -> OrderService:
    return OrderService(PricingPolicy())
