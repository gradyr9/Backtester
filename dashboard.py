# dashboard.py
import datetime

import dash
from dash import Dash, dcc, html, Input, Output, State, ctx, dash_table, ALL
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

from core.backtester import Backtester, run_parameter_grid_search
from core.strategies import strategy_registry

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)


app.layout = dbc.Container(
    [
        html.H1("Backtesting Dashboard"),

        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Select Strategy"),
                        dcc.Dropdown(
                            id="strategy-dropdown",
                            options=[{"label": name, "value": name} for name in strategy_registry],
                            value="Moving Average Crossover",
                            className="mb-2",
                        ),
                        html.Label("Symbol"),
                        dbc.Input(
                            id="symbol-input",
                            type="text",
                            value="SPY",
                            placeholder="Enter ticker symbol",
                            className="mb-2",
                        ),
                        html.Label("Date Range"),
                        dcc.DatePickerRange(
                            id="date-range",
                            start_date=datetime.date(2015, 1, 1),
                            end_date=datetime.date.today(),
                            display_format="YYYY-MM-DD",
                            className="mb-2",
                        ),
                        html.Div(id="strategy-params", className="mb-2"),
                        dbc.Button("Run Backtest", id="run-button", color="primary", className="mt-2"),
                    ],
                    width=4,
                ),
                dbc.Col(
                    [
                        dcc.Tabs(
                            id="graph-tabs",
                            value="equity",
                            children=[
                                dcc.Tab(label="Equity Curve", value="equity"),
                                dcc.Tab(label="Trade Signals", value="signals"),
                                dcc.Tab(label="Drawdowns", value="drawdown"),
                                dcc.Tab(label="Optimizer", value="optimizer"),
                            ],
                        ),
                        # All tab content renders here (and ONLY here)
                        html.Div(id="tab-content", className="mt-3"),
                        html.Hr(),
                        html.Div(id="metrics-output", className="mb-2"),
                        html.Div(id="trade-log-output"),
                    ],
                    width=8,
                ),
            ]
        ),

        # Stores for figures & trade log
        dcc.Store(id="stored-equity-figure"),
        dcc.Store(id="stored-signals-figure"),
        dcc.Store(id="stored-drawdown-figure"),
        dcc.Store(id="stored-trade-log"),

        # Store for best params from optimizer
        dcc.Store(id="best-params-store"),
    ],
    fluid=True,
)


@app.callback(
    Output("strategy-params", "children"),
    Input("strategy-dropdown", "value"),
)
def update_strategy_params_ui(selected_strategy):
    strategy_info = strategy_registry[selected_strategy]
    controls = []
    for param_name, meta in strategy_info["params"].items():
        controls.append(
            dbc.Row(
                [
                    dbc.Label(meta["label"], width=6),
                    dbc.Col(
                        dbc.InputGroup(
                            [
                                dbc.InputGroupText("Start"),
                                dbc.Input(
                                    id={"type": "opt-param", "param": param_name, "role": "start"},
                                    type="number",
                                    value=int(meta["default"]),
                                ),
                                dbc.InputGroupText("Stop"),
                                dbc.Input(
                                    id={"type": "opt-param", "param": param_name, "role": "stop"},
                                    type="number",
                                    value=int(meta["default"]) + 20,
                                ),
                                dbc.InputGroupText("Step"),
                                dbc.Input(
                                    id={"type": "opt-param", "param": param_name, "role": "step"},
                                    type="number",
                                    value=10,
                                ),
                            ]
                        )
                    ),
                ],
                className="mb-2",
            )
        )
    return controls



@app.callback(
    Output("stored-equity-figure", "data"),
    Output("stored-signals-figure", "data"),
    Output("stored-drawdown-figure", "data"),
    Output("metrics-output", "children"),
    Output("stored-trade-log", "data"),
    Output("trade-log-output", "children"),
    Input("run-button", "n_clicks"),
    State("strategy-dropdown", "value"),
    State("symbol-input", "value"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("strategy-params", "children"),
    prevent_initial_call=True,
)
def run_backtest(n_clicks, selected_strategy, symbol, start_date, end_date, param_children):
    if not n_clicks:
        raise PreventUpdate

    # Parse param values (use the 'start' box as the single run value)
    strategy_info = strategy_registry[selected_strategy]
    param_values = {}
    for row in (param_children or []):
        try:
            col = row["props"]["children"][1]
            input_group = col["props"].get("children")
            components = (input_group or {}).get("props", {}).get("children", [])
            role_values = {}
            param_name = None
            for comp in components:
                props = comp.get("props", {}) if isinstance(comp, dict) else {}
                cid = props.get("id")
                if isinstance(cid, dict) and cid.get("type") == "opt-param":
                    role_values[cid["role"]] = props.get("value")
                    param_name = cid["param"]
            if role_values and param_name is not None:
                val = role_values.get("start")
                if val is not None:
                    param_values[param_name] = int(val)
        except Exception:
            continue

    # Backtest
    try:
        strategy = strategy_info["class"](**param_values)
        bt = Backtester(symbol, strategy)
        bt.fetch_data(start_date, end_date)
        bt.run()
        cum_ret, sharpe, max_dd, vol = bt.evaluate()
        avg_pnl, win_rate, win_loss_ratio = bt.evaluate_trades()

        equity_figure = bt.get_equity_curve_figure().to_dict()
        signals_figure = bt.get_trade_signals_figure().to_dict()
        drawdown_figure = bt.get_drawdown_figure().to_dict()
        trade_log = bt.get_trade_log()

        trade_table = dash_table.DataTable(
            columns=[{"name": k, "id": k} for k in (trade_log[0].keys() if trade_log else [])],
            data=trade_log,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            page_size=10,
            style_data_conditional=[
                {"if": {"filter_query": "{P&L} > 0", "column_id": "P&L"}, "color": "green", "fontWeight": "bold"},
                {"if": {"filter_query": "{P&L} < 0", "column_id": "P&L"}, "color": "red", "fontWeight": "bold"},
            ],
        )

        metrics_string = (
            f"Cumulative Return: {cum_ret:.2%} | "
            f"Sharpe Ratio: {sharpe:.2f} | "
            f"Max Drawdown: {max_dd:.2%} | "
            f"Volatility: {vol:.2%} | "
            f"Avg P&L: ${avg_pnl:.2f} | "
            f"Win Rate: {win_rate:.2f}% | "
            f"Win/Loss Ratio: {win_loss_ratio:.2f}"
        )

        return (
            equity_figure,
            signals_figure,
            drawdown_figure,
            metrics_string,
            trade_log,
            trade_table,
        )
    except Exception as e:
        error_msg = html.Div(f"Error: {str(e)}", style={"color": "red"})
        # Clear stores on error so the renderer doesn't try to draw stale charts
        return None, None, None, error_msg, None, error_msg



@app.callback(
    Output("tab-content", "children"),
    Input("graph-tabs", "value"),
    Input("stored-equity-figure", "data"),
    Input("stored-signals-figure", "data"),
    Input("stored-drawdown-figure", "data"),
)
def render_tab_content(tab, equity_fig, signals_fig, drawdown_fig):
    # Optimizer tab: render only the optimizer UI (force a remount via key)
    if tab == "optimizer":
        return html.Div(
            [
                dbc.Button("Run Optimization", id="optimize-button", color="success", className="mb-3 me-2"),
                dbc.Button("Set Best Params", id="set-best-params", color="secondary", className="mb-3"),
                html.Div(id="optimization-output"),
            ],
            id="optimizer-pane",
            key="optimizer-pane",  # <- force React remount when switching tabs
        )

    # Charts tabs — wrap graph in keyed container to avoid leaking props across tabs
    fig = {
        "equity": equity_fig,
        "signals": signals_fig,
        "drawdown": drawdown_fig,
    }.get(tab)

    content = dcc.Graph(figure=fig) if fig else html.Div("Run a backtest to see charts.")
    return html.Div(content, id=f"{tab}-pane", key=f"{tab}-pane")



@app.callback(
    Output("optimization-output", "children"),
    Output("best-params-store", "data"),
    Input("optimize-button", "n_clicks"),
    State("strategy-dropdown", "value"),
    State("symbol-input", "value"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("strategy-params", "children"),
    prevent_initial_call=True,
)
def run_optimizer(n_clicks, strategy_name, symbol, start, end, param_children):
    if not n_clicks:
        raise PreventUpdate

    if not param_children:
        return html.Div("No strategy parameters found."), dash.no_update

    strategy_info = strategy_registry[strategy_name]
    param_inputs = {}

    # Parse Start/Stop/Step from dict IDs
    for row in (param_children or []):
        try:
            col = row["props"]["children"][1]
            input_group = col["props"].get("children")
            components = (input_group or {}).get("props", {}).get("children", [])
            for comp in components:
                props = comp.get("props", {}) if isinstance(comp, dict) else {}
                cid = props.get("id")
                if isinstance(cid, dict) and cid.get("type") == "opt-param":
                    p = cid.get("param")
                    role = cid.get("role")
                    val = props.get("value")
                    if val is None:
                        continue
                    try:
                        val = int(val)
                    except (TypeError, ValueError):
                        continue
                    param_inputs.setdefault(p, {})[role] = val
        except Exception:
            continue

    # Build ranges
    param_ranges = {}
    for p, d in param_inputs.items():
        if all(k in d for k in ("start", "stop", "step")):
            if d["step"] == 0 or d["stop"] < d["start"]:
                continue
            param_ranges[p] = list(range(int(d["start"]), int(d["stop"]) + 1, int(d["step"])))

    if not param_ranges:
        return html.Div(
            "Please enter valid Start/Stop/Step values for at least one parameter.",
            style={"color": "red"},
        ), dash.no_update

    # Run grid search
    grid_results = run_parameter_grid_search(strategy_info["class"], symbol, start, end, param_ranges)
    if not grid_results:
        return html.Div("No results returned."), dash.no_update

    # Sort by Sharpe desc and add Rank
    grid_results_sorted = sorted(
        grid_results, key=lambda r: r.get("Sharpe", float("-inf")), reverse=True
    )
    for i, row in enumerate(grid_results_sorted, start=1):
        row["Rank"] = i

    # Best params
    best_row = grid_results_sorted[0]
    best_params = {k: v for k, v in best_row.items() if k in strategy_info["params"].keys()}

    best_summary = html.Div(
        [
            html.Strong("Best (by Sharpe): "),
            html.Span(", ".join([f"{k}={v}" for k, v in best_params.items()])),
            html.Span(
                f"  |  Sharpe: {best_row['Sharpe']:.2f}, "
                f"CumRet: {best_row['Cumulative Return']:.2f}%, "
                f"MaxDD: {best_row['Max Drawdown']:.2f}%"
            ),
        ],
        className="mb-2",
    )

    table = dash_table.DataTable(
        columns=[{"name": k, "id": k} for k in grid_results_sorted[0].keys()],
        data=grid_results_sorted,
        page_size=10,
        sort_action="native",
        sort_by=[{"column_id": "Sharpe", "direction": "desc"}],
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center"},
        style_data_conditional=[
            {"if": {"filter_query": "{Rank} = 1"}, "backgroundColor": "#e6ffe6", "fontWeight": "bold"}
        ],
    )

    return html.Div([best_summary, table]), best_params



@app.callback(
    Output({"type": "opt-param", "param": ALL, "role": "start"}, "value"),
    Output({"type": "opt-param", "param": ALL, "role": "stop"}, "value"),
    Output({"type": "opt-param", "param": ALL, "role": "step"}, "value"),
    Input("set-best-params", "n_clicks"),
    State("best-params-store", "data"),
    State({"type": "opt-param", "param": ALL, "role": "start"}, "id"),
    State({"type": "opt-param", "param": ALL, "role": "stop"}, "id"),
    State({"type": "opt-param", "param": ALL, "role": "step"}, "id"),
    prevent_initial_call=True,
)
def apply_best_params(n_clicks, best_params, start_ids, stop_ids, step_ids):
    if not n_clicks or not best_params:
        raise PreventUpdate

    start_vals = [None] * len(start_ids)
    stop_vals = [None] * len(stop_ids)
    step_vals = [1] * len(step_ids)  # default step=1

    for i, id_obj in enumerate(start_ids):
        p = id_obj.get("param")
        if p in best_params:
            start_vals[i] = int(best_params[p])
    for i, id_obj in enumerate(stop_ids):
        p = id_obj.get("param")
        if p in best_params:
            stop_vals[i] = int(best_params[p])

    return start_vals, stop_vals, step_vals


if __name__ == "__main__":
    app.run(debug=True)
