from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Portfolio, Trade, Holding
from decimal import Decimal
import yfinance as yf
import math, json

@login_required
def home(request):
    portfolio = Portfolio.objects.get(user=request.user)
    holdings = Holding.objects.filter(portfolio=portfolio)

    symbol = request.GET.get('symbol') or ''
    range_option = request.GET.get('range', '1mo')

    # -----------------------------
    # 1. PORTFOLIO DASHBOARD LOGIC
    # -----------------------------
    holdings_data = []
    total_value = Decimal("0")
   
    for h in holdings:
        stock = yf.Ticker(h.symbol)
        data = stock.history(period="1d")

        # fallback for symbols with limited data
        if data.empty and range_option =="1y":
            data = stock.history(period="12mo")
        # ---------------------------------------
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

        total_value += market_value

        holdings_data.append({
            "symbol": h.symbol,
            "shares": h.shares,
            "current_price": current_price,
            "market_value": market_value,
            "avg_cost": avg_cost,
            "profit_loss": profit_loss,
        })

    total_portfolio_value = portfolio.cash_balance + total_value

    # -----------------------------
    # 2. STOCK LOOKUP + CHART LOGIC (Step 7A)
    # -----------------------------
    price = None
    # symbol = request.GET.get('symbol') or ''
    # range_option = request.GET.get('range', '1mo')  # <-- MUST be here
    timestamp = None
    change = None
    dates = []
    closes = []
    volumes = []
    sma20 = []

    if symbol:
        stock = yf.Ticker(symbol)
        data = stock.history(period=range_option)

        if not data.empty:
            price = data['Close'].iloc[-1]
            timestamp = data.index[-1]

            if len(data) > 1:
                prev_close = data['Close'].iloc[-2]
                change = price - prev_close

            dates = [d.strftime("%Y-%m-%d") for d in data.index]
            closes = [float(c) for c in data['Close']]
            volumes = [int(v) for v in data['Volume']]

            # 20-day moving average
            data['SMA20'] = data['Close'].rolling(window=20).mean()
            # sma20 = [float(x) if not str(x) == 'nan' else None for x in data['SMA20']]
            # sma20 = [float(x) if x and not math.isnan(x) else None for x in data['SMA20']]
            # sma20= []
            for x in data['SMA20']:
                if x is None:
                    sma20.append(None)
                else:
                    try:
                        if math.isnan(x):
                            sma20.append(None)
                        else:
                            sma20.append(float(x))
                    except:
                        sma20.append(None)
    # -----------------------------
    # 3. RENDER EVERYTHING TOGETHER
    # -----------------------------
    print("DATES:", dates)
    print("CLOSES:", closes)
    print("VOLUMES:", volumes)
    print("SMA20:", sma20)
       
     # Convert Python lists to JSON-safe strings for JavaScript
    dates = json.dumps(dates)
    closes = json.dumps(closes)
    volumes = json.dumps(volumes)
    sma20 = json.dumps(sma20)
    
    return render(request, "home.html", {
        # Dashboard
        "portfolio": portfolio,
        "holdings": holdings_data,
        "total_value": total_value,
        "total_portfolio_value": total_portfolio_value,

        # Stock lookup + chart
        "price": price,
        "symbol": symbol,
        "timestamp": timestamp,
        "change": change,
        "dates": dates,
        "closes": closes,

        # NEW Step 7 variables
        "range_option": range_option,
        "volumes": volumes,
        "sma20": sma20,
    })

@login_required
def trade(request):
    if request.method == "POST":
        symbol = request.POST.get("symbol")
        shares = Decimal(request.POST.get("shares"))
        trade_type = request.POST.get("trade_type")

        # Get user portfolio
        portfolio = Portfolio.objects.get(user=request.user)

        # Get current price
        stock = yf.Ticker(symbol)
        data = stock.history(period="1d")
        price = Decimal(str(data['Close'].iloc[-1]))

        # BUY logic
        if trade_type == "BUY":
            cost = price * shares
            if portfolio.cash_balance < cost:
                return render(request, "trade_error.html", {
                    "message": "Not enough cash to complete this trade."
                })
            portfolio.cash_balance -= cost

            # Update holdings
            holding, created = Holding.objects.get_or_create(
                portfolio=portfolio,
                symbol=symbol
            )
            holding.shares += shares
            holding.save()

        # SELL logic
        if trade_type == "SELL":
            holding = Holding.objects.filter(
                portfolio=portfolio,
                symbol=symbol
            ).first()

            if not holding or holding.shares < shares:
                return render(request, "trade_error.html", {
                    "message": "You do not have enough shares to sell."
                })
        # Adds cash from the Sale
            portfolio.cash_balance += price * shares
        # Substracts shares
            holding.shares -= shares
        # - New logic added: delete holdings if shares reaches zero
            if holding.shares == 0:
                holding.delete()
            else:
                holding.save()

        # Save portfolio and trade
        portfolio.save()
        Trade.objects.create(
            portfolio=portfolio,
            symbol=symbol,
            shares=shares,
            price=price,
            trade_type=trade_type
        )

        return redirect("home")

    return redirect("home")