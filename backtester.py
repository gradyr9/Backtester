import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

class Strategy:
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError("You must implement generate_signals")


class MovingAverageCrossoverStrategy(Strategy):
    def __init__(self, short_window=20, long_window=50):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["SMA_short"] = df["Close"].rolling(window=self.short_window).mean()
        df["SMA_long"] = df["Close"].rolling(window=self.long_window).mean()
        df["Signal"] = (df["SMA_short"] > df["SMA_long"]).astype(float)
        df["Position"] = df["Signal"].diff().fillna(0)
        return df


class RSIStrategy(Strategy):
    def __init__(self, rsi_window=14, lower_thresh=30, upper_thresh=70):
        self.rsi_window = rsi_window
        self.lower_thresh = lower_thresh
        self.upper_thresh = upper_thresh

    def compute_rsi(self, series):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=self.rsi_window).mean()
        avg_loss = loss.rolling(window=self.rsi_window).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["RSI"] = self.compute_rsi(df["Close"])
        df["Signal"] = 0.0
        df.loc[df["RSI"] < self.lower_thresh, "Signal"] = 1.0  # Buy
        df.loc[df["RSI"] > self.upper_thresh, "Signal"] = 0.0  # Sell
        df["Signal"] = df["Signal"].ffill().fillna(0)
        df["Position"] = df["Signal"].diff().fillna(0)
        return df



class Backtester:
    def __init__(self, symbol: str, strategy: Strategy, initial_cash: float = 100000):
        self.symbol = symbol
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.df = None

    def fetch_data(self, start, end):
        raw_df = yf.download(self.symbol, start=start, end=end, auto_adjust=False)
        try:
            close_series = raw_df[("Close", self.symbol)].copy()
        except KeyError:
            raise KeyError(f"Could not find ('Close', {self.symbol}) in DataFrame columns:\n{raw_df.columns}")

        # Store in self.df as a single-column DataFrame
        self.df = close_series.to_frame(name="Close")

    def run(self):
        if self.df is None:
            raise ValueError("Data not loaded. Call fetch_data() first.")

        self.df = self.strategy.generate_signals(self.df)
        self.df["Holdings"] = self.df["Signal"] * self.df["Close"]
        self.df["Cash"] = self.initial_cash - (self.df["Position"] * self.df["Close"]).cumsum()
        self.df["Total"] = self.df["Holdings"] + self.df["Cash"]
        self.df["Returns"] = self.df["Total"].pct_change()

    def evaluate(self):
        total = self.df["Total"]
        returns = self.df["Returns"].dropna()
        final_value = total.iloc[-1]

        cumulative_return = final_value / self.initial_cash - 1
        sharpe_ratio = returns.mean() / returns.std() * (252 ** 0.5)

        rolling_max = total.cummax()
        drawdown = (total - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Calculate CAGR
        num_years = (self.df.index[-1] - self.df.index[0]).days / 365.25
        cagr = (final_value / self.initial_cash) ** (1 / num_years) - 1

        # Calmar Ratio
        calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else float("inf")

        # Trade performance (based on position changes)
        trades = self.df[self.df["Position"] != 0]
        win_rate = (trades["Returns"] > 0).sum() / len(trades) if not trades.empty else 0.0
        max_gain = returns.max()
        max_loss = returns.min()

        print(f"Cumulative Return: {cumulative_return:.2%}")
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"Max Drawdown: {max_drawdown:.2%}")
        print(f"CAGR: {cagr:.2%}")
        print(f"Calmar Ratio: {calmar:.2f}")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Max Daily Gain: {max_gain:.2%}")
        print(f"Max Daily Loss: {max_loss:.2%}")

        return {
            "Cumulative Return": cumulative_return,
            "Sharpe Ratio": sharpe_ratio,
            "Max Drawdown": max_drawdown,
            "CAGR": cagr,
            "Calmar Ratio": calmar,
            "Win Rate": win_rate,
            "Max Gain": max_gain,
            "Max Loss": max_loss,
        }


    def plot_equity_curve(self):
        plt.figure(figsize=(12, 6))
        plt.plot(self.df["Total"], label="Portfolio Value", color="blue")
        plt.title("Portfolio Value Over Time")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value ($)")
        plt.legend()
        plt.grid(True)
        plt.show()

    def plot_trades(self):
        plt.figure(figsize=(12, 6))
        plt.plot(self.df["Close"], label="Price", alpha=0.5, color="black")
        plt.scatter(self.df[self.df["Position"] == 1].index, self.df[self.df["Position"] == 1]["Close"],
                    label="Buy", marker="^", color="green", s=100)
        plt.scatter(self.df[self.df["Position"] == -1].index, self.df[self.df["Position"] == -1]["Close"],
                    label="Sell", marker="v", color="red", s=100)
        plt.title("Trade Signals on Price")
        plt.xlabel("Date")
        plt.ylabel("Price ($)")
        plt.legend()
        plt.grid(True)
        plt.show()


# strategy = MovingAverageCrossoverStrategy()
strategy = RSIStrategy(rsi_window=14, lower_thresh=30, upper_thresh=70)
bt = Backtester("SPY", strategy)
bt.fetch_data("2015-01-01", "2024-12-31")
bt.run()
metrics = bt.evaluate()
bt.plot_equity_curve()
bt.plot_trades()