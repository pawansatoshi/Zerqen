from dataclasses import dataclass

@dataclass(frozen=True)
class Fill:
    price: float
    quantity: float
    fee: float
    notional: float

class CandleExecutionModel:
    """Conservative candle-based fill model.

    Entry/exit prices are shifted by slippage. The model is intentionally
    deterministic and does not claim to model order-book microstructure.
    """

    def __init__(self, fee_rate: float = 0.001, slippage_rate: float = 0.0005):
        if fee_rate < 0 or slippage_rate < 0:
            raise ValueError("fee_rate and slippage_rate must be non-negative")
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def buy(self, reference_price: float, quantity: float) -> Fill:
        price = reference_price * (1 + self.slippage_rate)
        notional = price * quantity
        return Fill(price, quantity, notional * self.fee_rate, notional)

    def sell(self, reference_price: float, quantity: float) -> Fill:
        price = reference_price * (1 - self.slippage_rate)
        notional = price * quantity
        return Fill(price, quantity, notional * self.fee_rate, notional)
