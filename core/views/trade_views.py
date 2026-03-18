from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from ..trade_services import execute_trade


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