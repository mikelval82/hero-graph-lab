from order_app.domain.order import Order


class PricingPolicy:
    def discounted_total(self, order: Order) -> float:
        subtotal = order.subtotal()
        discount = 0.1 if subtotal >= 100 else 0
        return subtotal * (1 - discount)
