from order_app.domain.order import Order


def format_confirmation(order: Order, total: float) -> str:
    return f"{order.customer_id}: {total:.2f}"
