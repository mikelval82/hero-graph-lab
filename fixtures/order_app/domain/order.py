from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    customer_id: str
    amount: float

    def subtotal(self) -> float:
        return self.amount
