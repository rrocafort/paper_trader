# core/portfolio_services.py

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import json

import yfinance as yf

from .models import PortfolioSnapshot, Trade


TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def q2(value):
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def fmt_money(value):
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"${value:,.2f}"


def fmt_shares(value):
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:,.2f}"


def build_position_from_trades(trades):
    total_shares = ZERO
    total_cost = ZERO
    realized_pl = ZERO

    for t in trades:
        shares = Decimal(str(t.shares))
        price = Decimal(str(t.price))

        if t.trade_type == "BUY":
            total_cost += shares * price
            total_shares += shares

        elif t.trade_type == "SELL":
            if total_shares <= 0:
                raise ValueError(
                    f"Cannot sell shares for {t.symbol} without an open position."
                )

            if shares > total_shares:
                raise ValueError(
                    f"Sell trade exceeds open shares for {t.symbol}."
                )

            avg_cost_before_sale = total_cost / total_shares
            realized_pl += (price - avg_cost_before_sale) * shares

            total_cost -= avg_cost_before_sale * shares
            total_shares -= shares

            if total_shares == 0:
                total_cost = ZERO

    avg_cost = (total_cost / total_shares) if total_shares > 0 else ZERO

    return {
        "shares": total_shares,
        "total_cost": total_cost,
        "avg_cost": avg_cost,
        "realized_pl": realized_pl,
    }


def build_trade_rows_with_realized_pl(trades):
    state = {}
    rows = []

    for t in trades:
        symbol = t.symbol
        shares = Decimal(str(t.shares))
        price = Decimal(str(t.price))
        trade_value = shares * price

        if symbol not in state:
            state[symbol] = {
                "shares": ZERO,
                "cost": ZERO,
            }

        running_shares = state[symbol]["shares"]
        running_cost = state[symbol]["cost"]

        if t.trade_type == "BUY":
            running_cost += shares * price
            running_shares += shares
            pl = None

        else:
            if running_shares <= 0 or shares > running_shares:
                pl = None
            else:
                avg_cost_before_sale = running_cost / running_shares
                pl = q2((price - avg_cost_before_sale) * shares)

                running_cost -= avg_cost_before_sale * shares
                running_shares -= shares

                if running_shares == 0:
                    running_cost = ZERO

        state[symbol]["shares"] = running_shares
        state[symbol]["cost"] = running_cost

        rows.append({
            "symbol": symbol,
            "trade_type": t.trade_type,

            # RAW
            "shares": shares,
            "price": q2(price),
            "trade_value": q2(trade_value),
            "timestamp": t.timestamp,
            "pl": q2(pl) if pl is not None else None,

            # DISPLAY
            "shares_display": fmt_shares(shares),
            "price_display": fmt_money(price),
            "trade_value_display": fmt_money(trade_value),
            "pl_display": fmt_money(pl) if pl is not None else None,
        })

    rows.reverse()
    return rows


def build_holdings_and_summary(request_user, portfolio, holdings):
    holdings_data = []
    total_value = ZERO

    for h in holdings:
        current_price = Decimal("0.00")

        try:
            stock = yf.Ticker(h.symbol)
            data = stock.history(period="1d")

            if data is not None and not data.empty and "Close" in data.columns:
                close_value = data["Close"].iloc[-1]

                if close_value is not None:
                    current_price = Decimal(str(close_value))
        except Exception:
            current_price = Decimal("0.00")

        market_value = current_price * Decimal(str(h.shares))

        trades = Trade.objects.filter(
            portfolio=portfolio,
            symbol=h.symbol
        ).order_by("timestamp", "id")

        position = build_position_from_trades(trades)
        avg_cost = position["avg_cost"]

        cost_basis_value = avg_cost * Decimal(str(h.shares))
        profit_loss = market_value - cost_basis_value
        pl_per_share = current_price - avg_cost
        percent_gain = (pl_per_share / avg_cost * Decimal("100")) if avg_cost > 0 else ZERO

        total_value += market_value

        holdings_data.append({
            "symbol": h.symbol,

            # RAW / NUMERIC
            "shares": h.shares,
            "current_price": q2(current_price),
            "market_value": q2(market_value),
            "avg_cost": q2(avg_cost),
            "profit_loss": q2(profit_loss),
            "pl_per_share": q2(pl_per_share),
            "percent_gain": q2(percent_gain),

            # DISPLAY
            "shares_display": fmt_shares(h.shares),
            "current_price_display": fmt_money(current_price),
            "market_value_display": fmt_money(market_value),
            "avg_cost_display": fmt_money(avg_cost),
            "profit_loss_display": fmt_money(profit_loss),
            "pl_per_share_display": fmt_money(pl_per_share),
            "percent_gain_display": f"{q2(percent_gain):,.2f}%",
        })

    cash_balance = Decimal(str(portfolio.cash_balance or "0.00"))
    total_portfolio_value = q2(cash_balance + total_value)

    cash_balance_display = fmt_money(cash_balance)
    holdings_value_display = fmt_money(total_value)
    total_portfolio_value_display = fmt_money(total_portfolio_value)
    positions_count = len(holdings_data)

    allocation_labels = []
    allocation_values = []

    cash_value = float(cash_balance)

    # Add cash as actual dollar value
    if cash_value > 0:
        allocation_labels.append("Cash")
        allocation_values.append(round(cash_value, 2))

    # Add each holding as actual market value
    for h in holdings_data:
        ticker = h["symbol"]
        value = float(h["market_value"])

        if value > 0:
            allocation_labels.append(ticker)
            allocation_values.append(round(value, 2))

    # Fallback so chart does not break
    if not allocation_labels:
        allocation_labels = ["No Data"]
        allocation_values = [1.0]

    trade_history = Trade.objects.filter(portfolio=portfolio).order_by("timestamp", "id")
    trade_rows = build_trade_rows_with_realized_pl(trade_history)

    today = date.today()
    existing = PortfolioSnapshot.objects.filter(user=request_user, date=today).first()

    if existing:
        existing.total_value = total_portfolio_value
        existing.save(update_fields=["total_value"])
    else:
        PortfolioSnapshot.objects.create(
            user=request_user,
            total_value=total_portfolio_value
        )

    snapshots = PortfolioSnapshot.objects.filter(user=request_user).order_by("date")

    perf_dates = [s.date.strftime("%Y-%m-%d") for s in snapshots]
    perf_values = [float(s.total_value) for s in snapshots]

    drawdowns = []
    running_peak = float("-inf")

    for v in perf_values:
        if v > running_peak:
            running_peak = v

        dd = ((v - running_peak) / running_peak) * 100 if running_peak != 0 else 0
        drawdowns.append(round(dd, 2))

    max_drawdown = min(drawdowns) if drawdowns else 0

    year_start = date(today.year, 1, 1)
    ytd_value_start = next(
        (float(s.total_value) for s in snapshots if s.date >= year_start),
        None
    )

    ytd_return = 0
    if ytd_value_start and perf_values:
        ytd_return = round(
            ((perf_values[-1] - ytd_value_start) / ytd_value_start) * 100,
            2
        )

    one_year_ago = today - timedelta(days=365)
    one_year_value_start = next(
        (float(s.total_value) for s in snapshots if s.date >= one_year_ago),
        None
    )

    one_year_return = 0
    if one_year_value_start and perf_values:
        one_year_return = round(
            ((perf_values[-1] - one_year_value_start) / one_year_value_start) * 100,
            2
        )

    sma7 = []
    for i in range(len(perf_values)):
        if i < 6:
            sma7.append(None)
        else:
            window = perf_values[i - 6:i + 1]
            sma7.append(round(sum(window) / 7, 2))

    sma30 = []
    for i in range(len(perf_values)):
        if i < 29:
            sma30.append(None)
        else:
            window = perf_values[i - 29:i + 1]
            sma30.append(round(sum(window) / 30, 2))

    return {
        "holdings_data": holdings_data,
        "total_value": total_value,
        "total_portfolio_value": total_portfolio_value,
        "cash_balance": cash_balance,

        "cash_balance_display": cash_balance_display,
        "holdings_value_display": holdings_value_display,
        "total_portfolio_value_display": total_portfolio_value_display,
        "positions_count": positions_count,

        "trade_rows": trade_rows,

        "allocation_labels": json.dumps(allocation_labels),
        "allocation_values": json.dumps(allocation_values),

        "perf_dates": json.dumps(perf_dates),
        "perf_values": json.dumps(perf_values),
        "perf_sma7": json.dumps(sma7),
        "perf_sma30": json.dumps(sma30),
        "drawdowns": json.dumps(drawdowns),
        "max_drawdown": max_drawdown,
        "ytd_return": ytd_return,
        "one_year_return": one_year_return,
    }