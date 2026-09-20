import json
import typer
from .backtest import run_backtest
from .config import ZerqenConfig
from .data import load_csv

app = typer.Typer(help="Zerqen adaptive quantitative compounding engine.")

@app.command()
def backtest(
    csv: str = typer.Option(..., help="OHLCV CSV path"),
    starting_capital: float = typer.Option(10_000.0, min=1),
    target_daily: float = typer.Option(0.08, min=0),
):
    """Run the baseline research strategy on historical OHLCV data."""
    cfg = ZerqenConfig(starting_capital=starting_capital, target_daily_return=target_daily)
    frame = load_csv(csv)
    trades, metrics = run_backtest(frame, cfg)
    typer.echo(json.dumps(metrics, indent=2, default=str))
    if not trades.empty:
        typer.echo("\nLast trades:")
        typer.echo(trades.tail(10).to_string(index=False))

if __name__ == "__main__":
    app()
