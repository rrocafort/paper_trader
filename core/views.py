from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect

from .models import Portfolio, Holding, PortfolioSnapshot
from .portfolio_services import ZERO, fmt_money, build_holdings_and_summary
from .market_data_services import get_stock_lookup_data
from .trade_services import execute_trade

from django.views.decorators.http import require_POST


# =========================================================
# AUTHENTICATION VIEWS
# =========================================================
def signup_view(request):
    """
    Handle user registration.
    If the signup form is valid, create the user, log them in,
    and redirect them to the home page.
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()

    return render(request, "signup.html", {"form": form})


# =========================================================
# HOME / DASHBOARD VIEW
# =========================================================
def home(request):
    """
    Main dashboard page.
    Shows stock lookup/chart data for all users.
    If the user is authenticated, also shows portfolio/trading data.
    """
    # -------------------------
    # Stock lookup inputs
    # -------------------------
    symbol = (request.GET.get("symbol") or "AAPL").upper().strip()
    range_option = request.GET.get("range") or "1y"

    # -------------------------
    # Default portfolio values
    # -------------------------
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

    allocation_labels = json.dumps([])
    allocation_values = json.dumps([])

    perf_dates = json.dumps([])
    perf_values = json.dumps([])
    perf_sma7 = json.dumps([])
    perf_sma30 = json.dumps([])
    drawdowns = json.dumps([])

    max_drawdown = 0
    ytd_return = 0
    one_year_return = 0

    # -------------------------
    # Default stock lookup values
    # -------------------------
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

    # -------------------------
    # Authenticated user portfolio data
    # -------------------------
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

        allocation_labels = portfolio_data["allocation_labels"]
        allocation_values = portfolio_data["allocation_values"]

        perf_dates = portfolio_data["perf_dates"]
        perf_values = portfolio_data["perf_values"]
        perf_sma7 = portfolio_data["perf_sma7"]
        perf_sma30 = portfolio_data["perf_sma30"]
        drawdowns = portfolio_data["drawdowns"]

        max_drawdown = portfolio_data["max_drawdown"]
        ytd_return = portfolio_data["ytd_return"]
        one_year_return = portfolio_data["one_year_return"]

    # -------------------------
    # Stock market lookup/chart data
    # -------------------------
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

    # -------------------------
    # Render dashboard
    # -------------------------
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

        "allocation_labels": allocation_labels,
        "allocation_values": allocation_values,

        "perf_dates": perf_dates,
        "perf_values": perf_values,
        "perf_sma7": perf_sma7,
        "perf_sma30": perf_sma30,
        "drawdowns": drawdowns,
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


# =========================================================
# TRADE EXECUTION VIEW
# =========================================================
@login_required
def trade(request):
    """
    Handle buy/sell requests.
    Validates symbol, shares, and trade type before passing
    the request to the trade service.
    """
    if request.method != "POST":
        return redirect("home")

    symbol = (request.POST.get("symbol") or "").upper().strip()
    shares_raw = request.POST.get("shares")
    trade_type = request.POST.get("trade_type")
    range_option = request.POST.get("range_option", "1y")

    redirect_url = f"/?symbol={symbol}&range={range_option}"

    # -------------------------
    # Basic request validation
    # -------------------------
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

    # -------------------------
    # Execute trade
    # -------------------------
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


# =========================================================
# TRADE HISTORY VIEW
# =========================================================
@login_required
def trade_history(request):
    """
    Display the user's trade history table.
    """
    portfolio, _ = Portfolio.objects.get_or_create(user=request.user)
    holdings = Holding.objects.filter(portfolio=portfolio)

    portfolio_data = build_holdings_and_summary(
        request_user=request.user,
        portfolio=portfolio,
        holdings=holdings,
    )

    return render(request, "history.html", {
        "trade_rows": portfolio_data["trade_rows"],
    })


# =========================================================
# PORTFOLIO PAGE VIEW
# =========================================================
@login_required
def portfolio_page(request):
    """
    Display the portfolio summary page:
    - cash balance
    - holdings value
    - total portfolio value
    - positions count
    - allocation chart
    - performance chart
    """
    portfolio, _ = Portfolio.objects.get_or_create(user=request.user)
    holdings = Holding.objects.filter(portfolio=portfolio)

    portfolio_data = build_holdings_and_summary(
        request_user=request.user,
        portfolio=portfolio,
        holdings=holdings,
    )

    return render(request, "portfolio.html", {
        "portfolio": portfolio,
        "holdings": portfolio_data["holdings_data"],

        "cash_balance_display": portfolio_data["cash_balance_display"],
        "holdings_value_display": portfolio_data["holdings_value_display"],
        "total_portfolio_value_display": portfolio_data["total_portfolio_value_display"],
        "positions_count": portfolio_data["positions_count"],

        "allocation_labels": portfolio_data["allocation_labels"],
        "allocation_values": portfolio_data["allocation_values"],

        "perf_dates": portfolio_data["perf_dates"],
        "perf_values": portfolio_data["perf_values"],
        "perf_sma7": portfolio_data["perf_sma7"],
        "perf_sma30": portfolio_data["perf_sma30"],

        "drawdowns": portfolio_data["drawdowns"],
        "max_drawdown": portfolio_data["max_drawdown"],
        "ytd_return": portfolio_data["ytd_return"],
        "one_year_return": portfolio_data["one_year_return"],
    })


# =========================================================
# RESET ACCOUNT VIEW
# =========================================================
@login_required
def reset_account(request):
    """
    Reset the user's account back to the default state:
    - cash balance reset to 100,000
    - holdings deleted
    - trade history deleted
    - portfolio snapshots deleted
    """
    if request.method == "POST":
        portfolio, _ = Portfolio.objects.get_or_create(user=request.user)

        portfolio.cash_balance = Decimal("100000.00")
        portfolio.save()

        Holding.objects.filter(portfolio=portfolio).delete()
        portfolio.trade_set.all().delete()
        PortfolioSnapshot.objects.filter(user=request.user).delete()

        messages.success(request, "Account has been reset.")
        return redirect("home")

    return render(request, "reset_confirm.html")