# app/layout.py
from dash import html, dcc

layout = html.Div([
    html.H1("Backtesting Dashboard"),
    dcc.Input(id='ticker-input', value='SPY', type='text'),
    dcc.DatePickerRange(
        id='date-picker',
        start_date='2015-01-01',
        end_date='2024-12-31'
    ),
    html.Button("Run Backtest", id="submit-button", n_clicks=0),
    html.Div(id="metrics-output"),
    dcc.Graph(id="equity-curve"),
    dcc.Graph(id="trade-signals"),
])
