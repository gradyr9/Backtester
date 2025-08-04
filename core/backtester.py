import pandas as pd
import yfinance as yf
import plotly.graph_objs as go

class Backtester:
    def __init__(self, symbol: str, strategy, initial_cash: float = 100000):
        self.symbol = symbol
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.df = None

    def fetch_data(self, start, end):
        raw_df = yf.download(self.symbol, start=start, end=end, auto_adjust=False)
        if isinstance(raw_df.columns, pd.MultiIndex):
            self.df = raw_df[("Close", self.symbol)].copy().to_frame(name="Close")
        else:
            self.df = raw_df[["Close"]].copy()

    def run(self):
        if self.df is None:
            raise ValueError("Data not loaded. Call fetch_data() first.")

        self.df = self.strategy.generate_signals(self.df)
        self.df["Holdings"] = self.df["Signal"] * self.df["Close"]
        self.df["Cash"] = self.initial_cash - (self.df["Position"] * self.df["Close"]).cumsum()
        self.df["Total"] = self.df["Holdings"] + self.df["Cash"]
        self.df["Returns"] = self.df["Total"].pct_change()

    def evaluate(self):
        cumulative_return = self.df["Total"].iloc[-1] / self.initial_cash - 1
        sharpe_ratio = self.df["Returns"].mean() / self.df["Returns"].std() * (252 ** 0.5)
        return cumulative_return, sharpe_ratio

    def get_equity_curve_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.df.index, y=self.df["Total"], mode='lines', name="Portfolio Value"))
        fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Portfolio Value ($)")
        return fig

    def get_trade_signals_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.df.index, y=self.df["Close"], mode='lines', name="Price"))
        buys = self.df[self.df["Position"] == 1]
        sells = self.df[self.df["Position"] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=buys["Close"], mode='markers', marker_symbol='triangle-up',
                                 marker_color='green', marker_size=10, name='Buy'))
        fig.add_trace(go.Scatter(x=sells.index, y=sells["Close"], mode='markers', marker_symbol='triangle-down',
                                 marker_color='red', marker_size=10, name='Sell'))
        fig.update_layout(title="Trade Signals on Price", xaxis_title="Date", yaxis_title="Price ($)")
        return fig
