from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import json
import math

import yfinance as yf
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm

from django.contrib.auth import login
from django.contrib import messages

from .models import Portfolio, PortfolioSnapshot, Trade, Holding


TWOPLACES = Decimal("0.01")
ZERO = Decimal("0")


def q2(value):
    """
    Round Decimal values to 2 decimal places for display.
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def safe_float_or_none(value):
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number):
            return None
        return round(number, 2)
    except (TypeError, ValueError):
        return None
    

def fmt_money(value):
    """
    Format a number as U.S. currency with commas and 2 decimals.
    Example: $25,000.00
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"${value:,.2f}"


def fmt_shares(value):
    """
    Format share quantity with commas and 2 decimals.
    Example: 1,250.50
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f"{value:,.2f}"


def build_position_from_trades(trades):
    """
    Average-cost accounting for a single symbol.
    Trades MUST be in chronological order: oldest -> newest.

    Returns:
        {
            "shares": Decimal,
            "total_cost": Decimal,
            "avg_cost": Decimal,
            "realized_pl": Decimal,
        }
    """
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

            # Reduce cost by COST BASIS, not by sale proceeds
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
    """
    Build trade history rows with symbol-aware realized P&L.
    Trades MUST be in chronological order: oldest -> newest.
    Returns rows in reverse chronological order for display.
    """
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

        else:  # SELL
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


def home(request):
    symbol = (request.GET.get("symbol") or "AAPL").upper().strip()
    range_option = request.GET.get("range") or "1y"

    # Default values
    portfolio = None
    holdings_data = []
    total_value = ZERO
    total_portfolio_value = ZERO
    cash_balance = ZERO
    trade_rows = []

    cash_balance_display = fmt_money(ZERO)
    holdings_value_display = fmt_money(ZERO)
    total_portfolio_value_display = fmt_money(ZERO)
    positions_count = 0

    allocation_labels_json = json.dumps([])
    allocation_weights_json = json.dumps([])

    perf_dates_json = json.dumps([])
    perf_values_json = json.dumps([])
    sma7_json = json.dumps([])
    sma30_json = json.dumps([])
    drawdowns_json = json.dumps([])
    max_drawdown = 0
    ytd_return = 0
    one_year_return = 0

    price = None
    timestamp = None
    change = None
    stock_name = None

    chart_dates = []
    closes = []
    sma20 = []
    sma50 = []
    sma150 = []
    sma200 = []
    volumes = []
    volume_colors = []

    # -----------------------------
    # PORTFOLIO LOGIC
    # -----------------------------
    if request.user.is_authenticated:
        portfolio, created = Portfolio.objects.get_or_create(user=request.user)
        holdings = Holding.objects.filter(portfolio=portfolio)

        for h in holdings:
            stock = yf.Ticker(h.symbol)
            data = stock.history(period="1d")
            
            if data.empty:
                continue

            current_price = Decimal(str(data["Close"].iloc[-1]))
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

                # RAW / NUMERIC (for logic)
                "shares": h.shares,
                "current_price": q2(current_price),
                "market_value": q2(market_value),
                "avg_cost": q2(avg_cost),
                "profit_loss": q2(profit_loss),
                "pl_per_share": q2(pl_per_share),
                "percent_gain": q2(percent_gain),

                # DISPLAY (for UI)
                "shares_display": fmt_shares(h.shares),
                "current_price_display": fmt_money(current_price),
                "market_value_display": fmt_money(market_value),
                "avg_cost_display": fmt_money(avg_cost),
                "profit_loss_display": fmt_money(profit_loss),
                "pl_per_share_display": fmt_money(pl_per_share),
                
            })

        cash_balance = portfolio.cash_balance
        total_portfolio_value = cash_balance + total_value

        allocation_labels = []
        allocation_weights = []

        for h in holdings_data:
            ticker = h["symbol"]
            value = float(h["market_value"])

            if float(total_portfolio_value) > 0:
                weight = (value / float(total_portfolio_value)) * 100
            else:
                weight = 0

            allocation_labels.append(ticker)
            allocation_weights.append(round(weight, 2))

        allocation_labels_json = json.dumps(allocation_labels)
        allocation_weights_json = json.dumps(allocation_weights)

        # IMPORTANT: chronological order for cost basis / realized P&L
        trade_history = Trade.objects.filter(portfolio=portfolio).order_by("timestamp", "id")
        trade_rows = build_trade_rows_with_realized_pl(trade_history)

        today = date.today()
        existing = PortfolioSnapshot.objects.filter(user=request.user, date=today).first()

        if not existing:
            PortfolioSnapshot.objects.create(
                user=request.user,
                total_value=total_portfolio_value
            )

        snapshots = PortfolioSnapshot.objects.filter(user=request.user).order_by("date")

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

        perf_dates_json = json.dumps(perf_dates)
        perf_values_json = json.dumps(perf_values)
        sma7_json = json.dumps(sma7)
        sma30_json = json.dumps(sma30)
        drawdowns_json = json.dumps(drawdowns)

    # -----------------------------
    # STOCK LOOKUP / CHART LOGIC
    # -----------------------------
    if symbol:
        try:
            stock = yf.Ticker(symbol)

            try:
                info = stock.info
                stock_name = info.get("longName") or info.get("shortName") or symbol
            except Exception:
                stock_name = symbol

            data = stock.history(period=range_option)

            if not data.empty:
                price = float(data["Close"].iloc[-1])
                timestamp = str(data.index[-1])

                if len(data) > 1:
                    prev_close = float(data["Close"].iloc[-2])
                    change = round(price - prev_close, 2)

                data["SMA20"] = data["Close"].rolling(window=20).mean()
                data["SMA50"] = data["Close"].rolling(window=50).mean()
                data["SMA150"] = data["Close"].rolling(window=150).mean()
                data["SMA200"] = data["Close"].rolling(window=200).mean()

                chart_dates = [d.strftime("%Y-%m-%d") for d in data.index]
                closes = [round(float(c), 2) for c in data["Close"]]
                volumes = [int(v) for v in data["Volume"]]

                close_list = [float(c) for c in data["Close"]]

                for i in range(len(close_list)):
                    if i == 0:
                        volume_colors.append("rgba(148, 163, 184, 0.18)")
                    elif close_list[i] >= close_list[i - 1]:
                        volume_colors.append("rgba(34, 197, 94, 0.18)")
                    else:
                        volume_colors.append("rgba(239, 68, 68, 0.18)")

                sma20 = [safe_float_or_none(x) for x in data["SMA20"]]
                sma50 = [safe_float_or_none(x) for x in data["SMA50"]]
                sma150 = [safe_float_or_none(x) for x in data["SMA150"]]
                sma200 = [safe_float_or_none(x) for x in data["SMA200"]]

            else:
                stock_name = None

        except Exception:
            price = None
            timestamp = None
            change = None
            stock_name = None

            chart_dates = []
            closes = []
            sma20 = []
            sma50 = []
            sma150 = []
            sma200 = []
            volumes = []
            volume_colors = []
            

    return render(request, "home.html", {
         "portfolio": portfolio,
        "holdings": holdings_data,
        "total_value": total_value,
        "total_portfolio_value": total_portfolio_value,
        "cash_balance": cash_balance,

        "cash_balance_display": cash_balance_display,
        "holdings_value_display": holdings_value_display,
        "total_portfolio_value_display": total_portfolio_value_display,
        "positions_count": positions_count,

        "trade_rows": trade_rows,

        "allocation_labels": allocation_labels_json,
        "allocation_weights": allocation_weights_json,

        "perf_dates": perf_dates_json,
        "perf_values": perf_values_json,
        "perf_sma7": sma7_json,
        "perf_sma30": sma30_json,
        "drawdowns": drawdowns_json,
        "max_drawdown": max_drawdown,
        "ytd_return": ytd_return,
        "one_year_return": one_year_return,

        "symbol": symbol,
        "price": price,
        "timestamp": timestamp,
        "change": change,
        "dates": json.dumps(chart_dates),
        "closes": json.dumps(closes),
        "sma20": json.dumps(sma20),
        "sma50": json.dumps(sma50),
        "sma150": json.dumps(sma150),
        "sma200": json.dumps(sma200),
        "volumes": json.dumps(volumes),
        "volume_colors": json.dumps(volume_colors),
        "range_option": range_option,

        "stock_name": stock_name,      
    })


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "signup.html", {"form": form})

@login_required
def trade(request):
    if request.method != "POST":
        return redirect("home")

    symbol = (request.POST.get("symbol") or "").upper().strip()
    shares_raw = request.POST.get("shares")
    trade_type = request.POST.get("trade_type")
    range_option = request.POST.get("range_option", "1y")

    redirect_url = f"/?symbol={symbol}&range={range_option}"

    if not symbol or not shares_raw or trade_type not in ["BUY", "SELL"]:
        messages.error(request, "Invalid trade request.")
        return redirect(redirect_url)

    try:
        shares = Decimal(shares_raw)
    except Exception:
        messages.error(request, "Invalid number of shares.")
        return redirect(redirect_url)

    if shares <= 0:
        messages.error(request, "Shares must be greater than zero.")
        return redirect(redirect_url)

    portfolio, _ = Portfolio.objects.get_or_create(user=request.user)

    stock = yf.Ticker(symbol)
    data = stock.history(period="1d")

    if data.empty:
        messages.error(request, "Could not retrieve a valid stock price for that symbol.")
        return redirect(redirect_url)

    price = Decimal(str(data["Close"].iloc[-1]))
    trade_value = (price * shares).quantize(Decimal("0.01"))

    if trade_type == "BUY":
        cost = trade_value

        if portfolio.cash_balance < cost:
            messages.error(request, "Not enough cash to complete this trade.")
            return redirect(redirect_url)

        portfolio.cash_balance -= cost

        holding, _ = Holding.objects.get_or_create(
            portfolio=portfolio,
            symbol=symbol,
            defaults={"shares": Decimal("0")}
        )
        holding.shares += shares
        holding.save()

        action_word = "Bought"

    elif trade_type == "SELL":
        holding = Holding.objects.filter(
            portfolio=portfolio,
            symbol=symbol
        ).first()

        if not holding or holding.shares < shares:
            messages.error(request, "You do not have enough shares to sell.")
            return redirect(redirect_url)

        portfolio.cash_balance += trade_value
        holding.shares -= shares

        if holding.shares == 0:
            holding.delete()
        else:
            holding.save()

        action_word = "Sold"

    portfolio.save()

    Trade.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        shares=shares,
        price=price,
        trade_type=trade_type
    )

    messages.success(
        request,
        f"{action_word} {fmt_shares(shares)} shares of {symbol} at "
        f"{fmt_money(price)} for {fmt_money(trade_value)}. "
        f"Cash balance: {fmt_money(portfolio.cash_balance)}."
    )

    return redirect(redirect_url)