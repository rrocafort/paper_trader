from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect

from .models import Portfolio, Holding
from .portfolio_services import ZERO, fmt_money, build_holdings_and_summary
from .market_data_services import get_stock_lookup_data
from .trade_services import execute_trade


# -------------------------
# Authentication views
# -------------------------
def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "signup.html", {"form": form})


# -------------------------
# Dashboard / home view
# -------------------------
def home(request):
    symbol = (request.GET.get("symbol") or "AAPL").upper().strip()
    range_option = request.GET.get("range") or "1y"

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

    if request.user.is_authenticated:
        portfolio, _ = Portfolio.objects.get_or_create(user=request.user)
        holdings = Holding.objects.filter(portfolio=portfolio)

        portfolio_data = build_holdings_and_summary(
            request_user=request.user,
            portfolio=portfolio,
            holdings=holdings,
        )

        holdings_data = portfolio_data["holdings_data"]
        total_value = portfolio_data["total_value"]
        total_portfolio_value = portfolio_data["total_portfolio_value"]
        cash_balance = portfolio_data["cash_balance"]

        cash_balance_display = portfolio_data["cash_balance_display"]
        holdings_value_display = portfolio_data["holdings_value_display"]
        total_portfolio_value_display = portfolio_data["total_portfolio_value_display"]
        positions_count = portfolio_data["positions_count"]

        trade_rows = portfolio_data["trade_rows"]

        allocation_labels_json = portfolio_data["allocation_labels_json"]
        allocation_weights_json = portfolio_data["allocation_weights_json"]

        perf_dates_json = portfolio_data["perf_dates_json"]
        perf_values_json = portfolio_data["perf_values_json"]
        sma7_json = portfolio_data["sma7_json"]
        sma30_json = portfolio_data["sma30_json"]
        drawdowns_json = portfolio_data["drawdowns_json"]
        max_drawdown = portfolio_data["max_drawdown"]
        ytd_return = portfolio_data["ytd_return"]
        one_year_return = portfolio_data["one_year_return"]

    stock_data = get_stock_lookup_data(symbol, range_option)

    price = stock_data["price"]
    timestamp = stock_data["timestamp"]
    change = stock_data["change"]
    stock_name = stock_data["stock_name"]

    chart_dates = stock_data["chart_dates"]
    closes = stock_data["closes"]
    sma20 = stock_data["sma20"]
    sma50 = stock_data["sma50"]
    sma150 = stock_data["sma150"]
    sma200 = stock_data["sma200"]
    volumes = stock_data["volumes"]
    volume_colors = stock_data["volume_colors"]

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


# -------------------------
# Trade view
# -------------------------
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

    result = execute_trade(
        user=request.user,
        symbol=symbol,
        shares=shares,
        trade_type=trade_type,
    )

    if result["ok"]:
        messages.success(request, result["message"])
    else:
        messages.error(request, result["message"])

    return redirect(redirect_url)


