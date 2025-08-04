# core/strategies.py
import pandas as pd

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
    def __init__(self, period=14):
        self.period = period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()

        rs = avg_gain / avg_loss
        df["RSI"] = 100 - (100 / (1 + rs))

        df["Signal"] = (df["RSI"] < 30).astype(float)
        df["Position"] = df["Signal"].diff().fillna(0)
        return df


class BollingerBandsStrategy(Strategy):
    def __init__(self, window=20, num_std=2):
        self.window = window
        self.num_std = num_std

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rolling_mean = df["Close"].rolling(window=self.window).mean()
        rolling_std = df["Close"].rolling(window=self.window).std()

        df["Upper"] = rolling_mean + self.num_std * rolling_std
        df["Lower"] = rolling_mean - self.num_std * rolling_std

        df["Signal"] = ((df["Close"] < df["Lower"]) | (df["Close"] > df["Upper"]))
        df["Signal"] = df["Signal"].astype(float)
        df["Position"] = df["Signal"].diff().fillna(0)
        return df


# Strategy registry to reference in Dash app
strategy_registry = {
    "Moving Average Crossover": {
        "class": MovingAverageCrossoverStrategy,
        "params": {
            "short_window": {"type": "int", "default": 20, "label": "Short Window"},
            "long_window": {"type": "int", "default": 50, "label": "Long Window"}
        }
    },
    "RSI Strategy": {
        "class": RSIStrategy,
        "params": {
            "period": {"type": "int", "default": 14, "label": "RSI Period"}
        }
    },
    "Bollinger Bands Strategy": {
        "class": BollingerBandsStrategy,
        "params": {
            "window": {"type": "int", "default": 20, "label": "Window Size"},
            "num_std": {"type": "int", "default": 2, "label": "Num Std Dev"}
        }
    }
}