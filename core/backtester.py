# backtester.py
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from itertools import product

class Backtester:
    def __init__(self, symbol, strategy, initial_cash: float = 100000):
        self.symbol = symbol
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.df = None

    def fetch_data(self, start_date, end_date):
        df = yf.download(self.symbol, start=start_date, end=end_date, auto_adjust=False)

        # If the result is multi-level column (e.g., from multiple tickers), fix it
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]  # Safe now
        df.dropna(inplace=True)
        self.df = df


    def run(self):
        if self.df is None:
            raise ValueError("Data not loaded. Call fetch_data() first.")

        self.df = self.strategy.generate_signals(self.df.copy())

        self.df["Signal"] = self.df["Signal"].fillna(0).astype(int)
        self.df["Position"] = self.df["Signal"].shift(1).fillna(0).astype(int)

        # Calculate trades (delta position)
        self.df["Trade"] = self.df["Position"].diff().fillna(0)

        # Initialize cash and holdings
        cash = self.initial_cash
        quantity = 0
        cash_history = []
        holdings_history = []
        total_history = []

        for i in range(len(self.df)):
            trade = self.df["Trade"].iloc[i]
            price = float(self.df["Close"].iloc[i].item())  # Safer for scalars



            quantity += trade
            cash -= trade * price
            holdings = quantity * price
            total = cash + holdings

            cash_history.append(cash)
            holdings_history.append(holdings)
            total_history.append(total)

        self.df["Cash"] = cash_history
        self.df["Holdings"] = holdings_history
        self.df["Total"] = total_history
        self.df["Returns"] = self.df["Total"].pct_change().fillna(0)




    def evaluate(self):
        cumulative_return = self.df["Total"].iloc[-1] / self.initial_cash - 1
        sharpe_ratio = self.df["Returns"].mean() / self.df["Returns"].std() * (252 ** 0.5)

        # Max Drawdown
        running_max = self.df["Total"].cummax()
        drawdown = self.df["Total"] / running_max - 1
        max_drawdown = drawdown.min()

        # Annualized Volatility
        volatility = self.df["Returns"].std() * (252 ** 0.5)

        return cumulative_return, sharpe_ratio, max_drawdown, volatility


    def get_equity_curve_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.df.index, y=self.df["Total"], mode='lines', name="Portfolio Value"))
        fig.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Portfolio Value ($)")
        return fig

    def get_trade_signals_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=self.df.index, y=self.df["Close"], mode='lines', name="Price"))
        buys = self.df[self.df["Trade"] == 1]
        sells = self.df[self.df["Trade"] == -1]
        fig.add_trace(go.Scatter(
            x=buys.index,
            y=buys["Close"],
            mode='markers',
            marker_symbol='triangle-up',
            marker_color='green',
            marker_size=10,
            name='Buy',
            text=["Buy on {}".format(d.date()) for d in buys.index],
            hoverinfo='text+y'
        ))
        fig.add_trace(go.Scatter(
            x=sells.index,
            y=sells["Close"],
            mode='markers',
            marker_symbol='triangle-down',
            marker_color='red',
            marker_size=10,
            name='Sell',
            text=[f"Sell on {d.date()}" for d in sells.index],
            hoverinfo='text+y'
        ))
        fig.update_layout(title="Trade Signals on Price", xaxis_title="Date", yaxis_title="Price ($)")
        return fig

    def get_trade_log(self):
        logs = []
        open_trade = None

        for i in range(1, len(self.df)):
            trade = self.df["Trade"].iloc[i]
            price = self.df["Close"].iloc[i]
            date = self.df.index[i].strftime("%Y-%m-%d")

            if trade == 1:
                # Buy
                open_trade = {
                    "Date": date,
                    "Action": "Buy",
                    "Price": round(price, 2),
                    "Quantity": 1,
                    "P&L": ""
                }
                logs.append(open_trade)

            elif trade == -1 and open_trade:
                # Sell
                pnl = round(price - open_trade["Price"], 2)  # 1 share assumed
                logs.append({
                    "Date": date,
                    "Action": "Sell",
                    "Price": round(price, 2),
                    "Quantity": 1,
                    "P&L": pnl
                })
                open_trade = None

        return logs

    
    def get_drawdown_figure(self):
        running_max = self.df["Total"].cummax()
        drawdown = self.df["Total"] / running_max - 1

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=self.df.index,
            y=drawdown,
            mode='lines',
            name='Drawdown',
            line=dict(color='firebrick'),
            hovertemplate='%{y:.2%}<extra></extra>'  # Show 2 decimal % in hover
        ))

        fig.update_layout(
            title="Drawdown Over Time",
            xaxis_title="Date",
            yaxis_title="Drawdown",
            yaxis_tickformat=".2%",  # Show 2 decimal places
            hovermode="x unified"
        )

        return fig
    
    def evaluate_trades(self):
        trade_log = self.get_trade_log()

        # Extract only 'Sell' rows that contain P&L
        sells = [row for row in trade_log if row["Action"] == "Sell" and isinstance(row.get("P&L"), (int, float))]

        if not sells:
            return 0, 0, 0  # Avoid division by zero

        pnls = [row["P&L"] for row in sells]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        avg_pnl = round(sum(pnls) / len(pnls), 2)
        win_rate = round(len(wins) / len(pnls) * 100, 2)  # As percentage
        win_loss_ratio = round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses),), 2) if losses else float('inf')

        return avg_pnl, win_rate, win_loss_ratio
    
 



from itertools import product

def run_parameter_grid_search(strategy_class, symbol, start_date, end_date, param_grid):
    keys = list(param_grid.keys())
    value_lists = list(param_grid.values())

    results = []

    for values in product(*value_lists):
        param_combo = dict(zip(keys, values))
        strategy = strategy_class(**param_combo)
        bt = Backtester(symbol, strategy)
        bt.fetch_data(start_date, end_date)
        bt.run()
        cum_ret, sharpe, max_dd, vol = bt.evaluate()

        results.append({
            **param_combo,
            "Cumulative Return": round(cum_ret * 100, 2),
            "Sharpe": round(sharpe, 2),
            "Max Drawdown": round(max_dd * 100, 2),
            "Volatility": round(vol, 2)
        })

    return results





