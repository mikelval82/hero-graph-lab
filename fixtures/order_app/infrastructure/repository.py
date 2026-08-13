from order_app.domain.order import Order


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self.orders: list[tuple[Order, float]] = []

    def save(self, order: Order, total: float) -> None:
        self.orders.append((order, total))
