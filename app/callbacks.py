from dash import Input, Output, State
from core.backtester import Backtester
from core.strategies import MovingAverageCrossoverStrategy

def register_callbacks(app):
    @app.callback(
        [Output("metrics-output", "children"),
         Output("equity-curve", "figure"),
         Output("trade-signals", "figure")],
        Input("submit-button", "n_clicks"),
        [State("ticker-input", "value"),
         State("date-picker", "start_date"),
         State("date-picker", "end_date")]
    )
    def update_dashboard(n_clicks, ticker, start_date, end_date):
        strategy = MovingAverageCrossoverStrategy()
        bt = Backtester(ticker, strategy)
        bt.fetch_data(start_date, end_date)
        bt.run()
        cum_ret, sharpe = bt.evaluate()
        metrics = f"Cumulative Return: {cum_ret:.2%} | Sharpe Ratio: {sharpe:.2f}"
        return metrics, bt.get_equity_curve_figure(), bt.get_trade_signals_figure()