# core/market_data_services.py

import math

import yfinance as yf


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


def get_stock_lookup_data(symbol, range_option):
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

    if not symbol:
        return {
            "price": price,
            "timestamp": timestamp,
            "change": change,
            "stock_name": stock_name,
            "chart_dates": chart_dates,
            "closes": closes,
            "sma20": sma20,
            "sma50": sma50,
            "sma150": sma150,
            "sma200": sma200,
            "volumes": volumes,
            "volume_colors": volume_colors,
        }

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

    return {
        "price": price,
        "timestamp": timestamp,
        "change": change,
        "stock_name": stock_name,
        "chart_dates": chart_dates,
        "closes": closes,
        "sma20": sma20,
        "sma50": sma50,
        "sma150": sma150,
        "sma200": sma200,
        "volumes": volumes,
        "volume_colors": volume_colors,
    }