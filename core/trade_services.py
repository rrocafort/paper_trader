from decimal import Decimal

import yfinance as yf
from django.db import transaction

from .models import Portfolio, Trade, Holding
from .portfolio_services import fmt_money, fmt_shares


def get_latest_price(symbol):
    stock = yf.Ticker(symbol)
    data = stock.history(period="1d")

    if data.empty:
        return None

    return Decimal(str(data["Close"].iloc[-1]))


@transaction.atomic
def execute_trade(*, user, symbol, shares, trade_type):
    portfolio, _ = Portfolio.objects.get_or_create(user=user)

    price = get_latest_price(symbol)
    if price is None:
        return {
            "ok": False,
            "message": "Could not retrieve a valid stock price for that symbol.",
        }

    trade_value = (price * shares).quantize(Decimal("0.01"))

    if trade_type == "BUY":
        cost = trade_value

        if portfolio.cash_balance < cost:
            return {
                "ok": False,
                "message": "Not enough cash to complete this trade.",
            }

        portfolio.cash_balance -= cost

        holding, _ = Holding.objects.get_or_create(
            portfolio=portfolio,
            symbol=symbol,
            defaults={"shares": Decimal("0")},
        )
        holding.shares += shares
        holding.save()

        action_word = "Bought"

    elif trade_type == "SELL":
        holding = Holding.objects.filter(
            portfolio=portfolio,
            symbol=symbol,
        ).first()

        if not holding:
            return {
                "ok": False,
                "message": f"You do not own any shares of {symbol} to sell.",
            }

        if holding.shares < shares:
            return {
                "ok": False,
                "message": (
                    f"You can only sell up to {fmt_shares(holding.shares)} shares of {symbol}."
                ),
            }       

        portfolio.cash_balance += trade_value
        holding.shares -= shares

        if holding.shares == 0:
            holding.delete()
        else:
            holding.save()

        action_word = "Sold"

    else:
        return {
            "ok": False,
            "message": "Invalid trade type.",
        }

    portfolio.save()

    Trade.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        shares=shares,
        price=price,
        trade_type=trade_type,
    )

    return {
        "ok": True,
        "message": (
            f"{action_word} {fmt_shares(shares)} shares of {symbol} at "
            f"{fmt_money(price)} for {fmt_money(trade_value)}. "
            f"Cash balance: {fmt_money(portfolio.cash_balance)}."
        ),
    }