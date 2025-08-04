# main.py
from core.backtester import Backtester
from core.strategies import MovingAverageCrossoverStrategy

import plotly.io as pio
pio.renderers.default = "browser"

if __name__ == "__main__":
    strategy = MovingAverageCrossoverStrategy(short_window=20, long_window=50)
    bt = Backtester("SPY", strategy)

    bt.fetch_data("2015-01-01", "2024-12-31")
    bt.run()

    cumulative_return, sharpe_ratio = bt.evaluate()
    print(f"Cumulative Return: {cumulative_return:.2%}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

    bt.get_equity_curve_figure().show()
    bt.get_trade_signals_figure().show()


