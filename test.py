import yfinance as yf

dat = yf.Ticker("MSFT")

# get historical market data
print(dat.history(period='1mo'))

# options
print(dat.option_chain(dat.options[0]).calls)

# get financials
print(dat.balance_sheet)
print(dat.quarterly_income_stmt)

# dates
print(dat.calendar)

# general info
print(dat.info)

# analysis
print(dat.analyst_price_targets)

