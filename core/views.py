from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Portfolio, PortfolioSnapshot, Trade, Holding
from decimal import Decimal
from datetime import date
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
        pl_per_share = current_price - avg_cost
        percent_gain = (pl_per_share / avg_cost * 100) if avg_cost > 0 else Decimal("0")

        total_value += market_value
    total_portfolio_value = portfolio.cash_balance + total_value
    
    # Save snapshot only once per day
    today = date.today()
    existing = PortfolioSnapshot.objects.filter(user=request.user, date=today).first
    if not existing:
        PortfolioSnapshot.objects.create(
            user=request.user,
            total_value=total_portfolio_value
        )
    snapshots = PortfolioSnapshot.objects.filter(user=request.user).order_by("date")

    dates = [s.date.strftime("%Y-%m-%d") for s in snapshots]
    values = [float(s.total_value) for s in snapshots]
    
    # -- the dictionary --- 
    holdings_data({
        "symbol": h.symbol,
        "shares": h.shares,
        "current_price": current_price,
        "market_value": market_value,
        "avg_cost": avg_cost,
        "profit_loss": profit_loss,
        "pl_per_share": pl_per_share,
        "percent_gain": percent_gain,
        "perf_dates": dates,
        "perf_values": values,
    })
    

    # -----------------------------------------
    # 2. STOCK LOOKUP + CHART LOGIC (Step 7A)
    # -----------------------------------------
    price = None
    # symbol = request.GET.get('symbol') or ''
    # range_option = request.GET.get('range', '1mo')  # <-- MUST be here

    # --- Python lists  ---
    timestamp = None
    change = None
    dates = []
    closes = []
    volumes = []
    sma20 = []
    sma50 = []
    sma150 = []
    sma200 = []
    volume_ma30 = []

    # -----------------

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
            # Volume MA30
            for i in range(len(volumes)):
                if i < 30:
                    volume_ma30.append(None)
                else:
                    window = volumes[i-30:i]
                    volume_ma30.append(sum(window)/ 30)

            # -----------------------------------------------------
            #                 -- MOVING AVERAGES -----
            #------------------------------------------------------
            # 20-day moving average
            data['SMA20'] = data['Close'].rolling(window=20).mean()
            #  50-day moving average
            data['SMA50'] = data['Close'].rolling(window=50).mean()
            # 150-day moving average
            data['SMA150'] = data['Close'].rolling(window=150).mean()
            # 200-day moving average
            data['SMA200'] = data['Close'].rolling(window=200).mean()

            # - Convert SMA20 to python list
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
            # - Convert SMA50 to python list
            for x in data['SMA50']:
                if x is None:
                    sma50.append(None)
                else:
                    try:
                        if math.isnan(x):
                            sma50.append(None)
                        else:
                            sma50.append(float(x))
                    except:
                        sma50.append(None)
            # - Convert SMA150 to python list
            for x in data['SMA150']:
                if x is None:
                    sma150.append(None)
                else:
                    try:
                        if math.isnan(x):
                            sma150.append(None)
                        else:
                            sma150.append(float(x))
                    except:
                        sma150.append(None)
            # - Convert SMA20 to python list
            for x in data['SMA200']:
                if x is None:
                    sma200.append(None)
                else:
                    try:
                        if math.isnan(x):
                            sma200.append(None)
                        else:
                            sma200.append(float(x))
                    except:
                        sma200.append(None)
    # -----------------------------
    # 3. RENDER EVERYTHING TOGETHER - for console
    # -----------------------------
    print("DATES:", dates)
    print("CLOSES:", closes)
    print("VOLUMES:", volumes)
    print("SMA20:", sma20)
    print("SMA50:", sma50)
    print("SMA150:", sma150)
    print("SMA200:", sma200)
    print("VOLUME_MA30:", volume_ma30)
    print("LEN VOLUMES:", len(volumes))
    print("VOLUME_MA30 SAMPLE:", volume_ma30[:40])

       
     # Convert Python lists to JSON-safe strings for JavaScript
    dates = json.dumps(dates)
    closes = json.dumps(closes)
    volumes = json.dumps(volumes)
    sma20 = json.dumps(sma20)
    sma50 = json.dumps(sma50)
    sma150 = json.dumps(sma150)
    sma200 = json.dumps(sma200)
    volume_ma30 = json.dumps(volume_ma30)


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

        # NEW Step 7 variables - Context dictionary
        "range_option": range_option,
        "volumes": volumes,
        "sma20": sma20,
        "sma50": sma50,
        "sma150": sma150,
        "sma200": sma200,
        "volume_ma30": volume_ma30,

        # Cash Format
        "cash_balance": portfolio.cash_balance,
        "total_portfolio_value": total_portfolio_value,
        "holdings": holdings_data,
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