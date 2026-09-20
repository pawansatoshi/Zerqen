from dataclasses import dataclass

@dataclass
class PortfolioState:
    initial_equity: float
    equity: float
    peak_equity: float
    day_start_equity: float

    @classmethod
    def create(cls, capital: float) -> "PortfolioState":
        if capital <= 0:
            raise ValueError("capital must be positive")
        return cls(capital, capital, capital, capital)

    def apply_pnl(self, pnl: float) -> float:
        self.equity = max(0.0, self.equity + pnl)
        self.peak_equity = max(self.peak_equity, self.equity)
        return self.equity

    def start_day(self) -> None:
        self.day_start_equity = self.equity

    @property
    def drawdown(self) -> float:
        return 0.0 if self.peak_equity <= 0 else 1.0 - self.equity / self.peak_equity
