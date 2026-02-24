from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Portfolio, Trade, Holding
from decimal import Decimal
import yfinance as yf

def home(request):
    price = None
    symbol = request.GET.get('symbol') or ''
    timestamp = None
    change = None
    dates = []
    closes = []

    if symbol:
        stock = yf.Ticker(symbol)
        data = stock.history(period="1mo")

        if not data.empty:
            # Latest price
            price = data['Close'].iloc[-1]
            timestamp = data.index[-1]

            # Price Change
            if len(data) > 1:
                prev_close = data['Close'].iloc[-2]
                change = price - prev_close   # FIXED

            # Prepare Chart Data
            dates = [d.strftime("%Y-%m-%d") for d in data.index]
            closes = [float(c) for c in data['Close']]

    return render(request, 'home.html', {
        'price': price,
        'symbol': symbol,
        'timestamp': timestamp,
        'change': change,
        'dates': dates,
        'closes': closes,
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

            portfolio.cash_balance += price * shares

            holding.shares -= shares
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