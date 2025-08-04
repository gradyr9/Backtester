# dashboard.py
import dash
from dash import Dash, dcc, html, Input, Output, State, ctx, exceptions
import dash_bootstrap_components as dbc
from core.backtester import Backtester
from core.strategies import strategy_registry
import datetime

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    html.H1("Backtesting Dashboard"),

    dbc.Row([
        dbc.Col([
            html.Label("Select Strategy"),
            dcc.Dropdown(
                id="strategy-dropdown",
                options=[{"label": name, "value": name} for name in strategy_registry],
                value="Moving Average Crossover",
                className="mb-2"
            ),

            html.Label("Symbol"),
            dbc.Input(id="symbol-input", type="text", value="SPY", placeholder="Enter ticker symbol", className="mb-2"),

            html.Label("Date Range"),
            dcc.DatePickerRange(
                id="date-range",
                start_date=datetime.date(2015, 1, 1),
                end_date=datetime.date.today(),
                display_format="YYYY-MM-DD",
                className="mb-2"
            ),

            html.Div(id="strategy-params")
        ], width=4),

        dbc.Col([
            dbc.Button("Run Backtest", id="run-button", color="primary", className="mt-4"),
            dbc.Spinner(
                dbc.Card([
                    dbc.CardHeader("Backtest Metrics"),
                    dbc.CardBody(html.Div(id="metrics-output"))
                ], className="mt-3"),
                color="primary",
                fullscreen=False
            )
        ], width=8)
    ]),

    html.Hr(),

    dcc.Tabs(id="graph-tabs", value="equity", children=[
        dcc.Tab(label="Equity Curve", value="equity"),
        dcc.Tab(label="Trade Signals", value="signals")
    ]),
    dcc.Store(id="stored-equity-figure"),
    dcc.Store(id="stored-signals-figure"),
    dbc.Spinner(html.Div(id="tab-content"), color="primary", fullscreen=False)
], fluid=True)


@app.callback(
    Output("strategy-params", "children"),
    Input("strategy-dropdown", "value")
)
def update_strategy_params_ui(selected_strategy):
    strategy_info = strategy_registry[selected_strategy]
    controls = []
    for param_name, meta in strategy_info["params"].items():
        controls.append(
            dbc.Row([
                dbc.Label(meta["label"], width=6),
                dbc.Col(
                    dbc.Input(
                        id=f"param-{param_name}",
                        type="number",
                        value=meta["default"],
                        debounce=True
                    ), width=6
                )
            ], className="mb-2")
        )
    return controls


@app.callback(
    Output("stored-equity-figure", "data"),
    Output("stored-signals-figure", "data"),
    Output("metrics-output", "children"),
    Output("tab-content", "children"),
    Input("run-button", "n_clicks"),
    Input("graph-tabs", "value"),
    State("strategy-dropdown", "value"),
    State("symbol-input", "value"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("strategy-params", "children"),
    State("stored-equity-figure", "data"),
    State("stored-signals-figure", "data")
)
def unified_callback(n_clicks, tab, selected_strategy, symbol, start_date, end_date,
                     param_children, stored_equity, stored_signals):
    triggered = ctx.triggered_id

    if triggered == "run-button":
        try:
            strategy_info = strategy_registry[selected_strategy]
            param_defs = strategy_info["params"]
            param_values = {}

            for row in param_children:
                try:
                    label, col = row["props"]["children"]
                    input_component = col["props"]["children"]
                    param_id = input_component["props"]["id"]
                    param_value = input_component["props"]["value"]
                    param_name = param_id.replace("param-", "")
                    param_values[param_name] = param_value
                except (KeyError, IndexError, TypeError):
                    continue

            strategy = strategy_info["class"](**param_values)
            bt = Backtester(symbol, strategy)
            bt.fetch_data(start_date, end_date)
            bt.run()
            cum_ret, sharpe = bt.evaluate()

            equity_figure = bt.get_equity_curve_figure().to_dict()
            signals_figure = bt.get_trade_signals_figure().to_dict()
            graph_fig = equity_figure if tab == "equity" else signals_figure

            return (
                equity_figure,
                signals_figure,
                f"Cumulative Return: {cum_ret:.2%} | Sharpe Ratio: {sharpe:.2f}",
                dcc.Graph(figure=graph_fig)
            )

        except Exception as e:
            error_msg = html.Div(f"Error: {str(e)}", style={"color": "red"})
            return {}, {}, error_msg, error_msg

    else:
        if tab == "equity" and stored_equity:
            return dash.no_update, dash.no_update, dash.no_update, dcc.Graph(figure=stored_equity)
        elif tab == "signals" and stored_signals:
            return dash.no_update, dash.no_update, dash.no_update, dcc.Graph(figure=stored_signals)
        else:
            return dash.no_update, dash.no_update, dash.no_update, html.Div("No data available.")


if __name__ == "__main__":
    app.run(debug=True)
