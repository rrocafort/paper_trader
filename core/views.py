from decimal import Decimal
from datetime import date, timedelta
import json
import math

import yfinance as yf
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .models import Portfolio, PortfolioSnapshot, Trade, Holding

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login



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


def home(request):
    symbol = (request.GET.get("symbol") or "").upper().strip()
    range_option = request.GET.get("range") or "1y"

    # -----------------------------
    # DEFAULT VALUES
    # -----------------------------
    portfolio = None
    holdings_data = []
    total_value = Decimal("0")
    total_portfolio_value = Decimal("0")
    cash_balance = Decimal("0")
    trade_rows = []

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
            market_value = current_price * h.shares

            trades = Trade.objects.filter(portfolio=portfolio, symbol=h.symbol)
            total_shares = Decimal("0")
            total_cost = Decimal("0")

            for t in trades:
                if t.trade_type == "BUY":
                    total_shares += t.shares
                    total_cost += t.shares * t.price
                elif t.trade_type == "SELL":
                    total_shares -= t.shares
                    total_cost -= t.shares * t.price

            avg_cost = total_cost / total_shares if total_shares > 0 else Decimal("0")
            profit_loss = market_value - (avg_cost * h.shares)
            pl_per_share = current_price - avg_cost
            percent_gain = (pl_per_share / avg_cost * 100) if avg_cost > 0 else Decimal("0")

            total_value += market_value

            holdings_data.append({
                "symbol": h.symbol,
                "shares": h.shares,
                "current_price": current_price,
                "market_value": market_value,
                "avg_cost": avg_cost,
                "profit_loss": profit_loss,
                "pl_per_share": pl_per_share,
                "percent_gain": percent_gain,
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

        trade_history = Trade.objects.filter(portfolio=portfolio).order_by("-timestamp")

        running_cost_basis = 0.0
        running_shares = 0.0

        for t in trade_history:
            trade_value = float(t.shares) * float(t.price)

            if t.trade_type == "BUY":
                if running_shares > 0:
                    running_cost_basis = (
                        (running_cost_basis * running_shares) + trade_value
                    ) / (running_shares + float(t.shares))
                else:
                    running_cost_basis = float(t.price)

                running_shares += float(t.shares)
                pl = None
            else:
                pl = round((float(t.price) - running_cost_basis) * float(t.shares), 2)
                running_shares -= float(t.shares)

            trade_rows.append({
                "symbol": t.symbol,
                "trade_type": t.trade_type,
                "shares": float(t.shares),
                "price": float(t.price),
                "trade_value": round(trade_value, 2),
                "timestamp": t.timestamp,
                "pl": pl,
            })

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
                        volume_colors.append("rgba(120,120,120,0.35)")
                    elif close_list[i] >= close_list[i - 1]:
                        volume_colors.append("rgba(46, 204, 113, 0.45)")
                    else:
                        volume_colors.append("rgba(231, 76, 60, 0.45)")

                sma20 = [safe_float_or_none(x) for x in data["SMA20"]]
                sma50 = [safe_float_or_none(x) for x in data["SMA50"]]
                sma150 = [safe_float_or_none(x) for x in data["SMA150"]]
                sma200 = [safe_float_or_none(x) for x in data["SMA200"]]

        except Exception:
            price = None
            timestamp = None
            change = None
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

    if not symbol or not shares_raw or trade_type not in ["BUY", "SELL"]:
        return render(request, "trade_error.html", {
            "message": "Invalid trade request."
        })

    try:
        shares = Decimal(shares_raw)
    except Exception:
        return render(request, "trade_error.html", {
            "message": "Invalid number of shares."
        })

    if shares <= 0:
        return render(request, "trade_error.html", {
            "message": "Shares must be greater than zero."
        })

    portfolio, created = Portfolio.objects.get_or_create(user=request.user)

    stock = yf.Ticker(symbol)
    data = stock.history(period="1d")

    if data.empty:
        return render(request, "trade_error.html", {
            "message": "Could not retrieve a valid stock price for that symbol."
        })

    price = Decimal(str(data["Close"].iloc[-1]))

    if trade_type == "BUY":
        cost = price * shares

        if portfolio.cash_balance < cost:
            return render(request, "trade_error.html", {
                "message": "Not enough cash to complete this trade."
            })

        portfolio.cash_balance -= cost

        holding, created = Holding.objects.get_or_create(
            portfolio=portfolio,
            symbol=symbol,
            defaults={"shares": Decimal("0")}
        )
        holding.shares += shares
        holding.save()

    elif trade_type == "SELL":
        holding = Holding.objects.filter(
            portfolio=portfolio,
            symbol=symbol
        ).first()

        if not holding or holding.shares < shares:
            return render(request, "trade_error.html", {
                "message": "You do not have enough shares to sell."
            })

        portfolio.cash_balance += price * shares
        holding.shares -= shares

        if holding.shares == 0:
            holding.delete()
        else:
            holding.save()

    portfolio.save()

    Trade.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        shares=shares,
        price=price,
        trade_type=trade_type
    )
    return redirect("home")