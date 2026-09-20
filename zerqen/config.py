from pydantic import BaseModel, Field

class RiskConfig(BaseModel):
    risk_per_trade: float = Field(0.005, gt=0, lt=0.1)
    max_daily_loss: float = Field(0.03, gt=0, lt=1)
    max_drawdown: float = Field(0.20, gt=0, lt=1)
    max_open_positions: int = Field(3, ge=1)

class CostConfig(BaseModel):
    fee_rate: float = Field(0.001, ge=0)
    slippage_rate: float = Field(0.0005, ge=0)

class StrategyConfig(BaseModel):
    fast_ema: int = Field(20, ge=2)
    slow_ema: int = Field(50, ge=3)
    rsi_period: int = Field(14, ge=2)
    rsi_min: float = Field(50, ge=0, le=100)
    rsi_max: float = Field(75, ge=0, le=100)
    atr_period: int = Field(14, ge=2)
    stop_atr: float = Field(1.5, gt=0)
    target_rr: float = Field(2.0, gt=0)

class ZerqenConfig(BaseModel):
    starting_capital: float = Field(10_000, gt=0)
    target_daily_return: float = Field(0.08, ge=0)
    risk: RiskConfig = RiskConfig()
    costs: CostConfig = CostConfig()
    strategy: StrategyConfig = StrategyConfig()
