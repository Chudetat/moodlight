"""
Stock Data Service.
Fetches stock quotes from Yahoo Finance and AlphaVantage.
"""
import httpx
from typing import Optional
from functools import lru_cache
from datetime import datetime, timedelta

from app.config import get_settings

settings = get_settings()

# Simple in-memory cache with TTL
_ticker_cache: dict[str, tuple[str, datetime]] = {}
_stock_cache: dict[str, tuple[dict, datetime]] = {}

TICKER_CACHE_TTL = timedelta(hours=24)
STOCK_CACHE_TTL = timedelta(hours=1)


class TickerNotFoundError(Exception):
    """Raised when ticker lookup fails."""
    pass


class StockDataError(Exception):
    """Raised when stock data fetch fails."""
    pass


async def search_ticker(brand_name: str) -> Optional[str]:
    """
    Search for a stock ticker symbol using Yahoo Finance.

    Args:
        brand_name: Company or brand name to search for

    Returns:
        Ticker symbol if found, None otherwise
    """
    # Check cache first
    cache_key = brand_name.lower().strip()
    if cache_key in _ticker_cache:
        ticker, cached_at = _ticker_cache[cache_key]
        if datetime.utcnow() - cached_at < TICKER_CACHE_TTL:
            return ticker

    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": brand_name, "quotesCount": 5, "newsCount": 0}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=5.0)
            data = response.json()

        if data.get("quotes"):
            # Return first stock result (not ETF/fund)
            for quote in data["quotes"]:
                if quote.get("quoteType") in ["EQUITY", "INDEX"]:
                    ticker = quote.get("symbol")
                    _ticker_cache[cache_key] = (ticker, datetime.utcnow())
                    return ticker
            # Fallback to first result
            ticker = data["quotes"][0].get("symbol")
            _ticker_cache[cache_key] = (ticker, datetime.utcnow())
            return ticker

        return None

    except Exception as e:
        print(f"Ticker search error for '{brand_name}': {e}")
        return None


async def fetch_stock_data(ticker: str) -> Optional[dict]:
    """
    Fetch stock quote data from AlphaVantage.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with symbol, price, change_percent, latest_day or None
    """
    if not settings.alphavantage_api_key:
        return None

    # Check cache first
    cache_key = ticker.upper()
    if cache_key in _stock_cache:
        data, cached_at = _stock_cache[cache_key]
        if datetime.utcnow() - cached_at < STOCK_CACHE_TTL:
            return data

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": ticker,
        "apikey": settings.alphavantage_api_key
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            data = response.json()

        if "Global Quote" in data and data["Global Quote"]:
            quote = data["Global Quote"]
            result = {
                "symbol": quote.get("01. symbol", ticker),
                "price": float(quote.get("05. price", 0)),
                "change_percent": float(quote.get("10. change percent", "0").replace("%", "")),
                "latest_day": quote.get("07. latest trading day", ""),
                "open": float(quote.get("02. open", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
            }
            _stock_cache[cache_key] = (result, datetime.utcnow())
            return result

        return None

    except Exception as e:
        print(f"Stock fetch error for '{ticker}': {e}")
        return None


async def get_brand_stock_data(brand_name: str) -> Optional[dict]:
    """
    Search for a brand's ticker and fetch its stock data.

    Args:
        brand_name: Company or brand name

    Returns:
        Dict with stock data and ticker, or None
    """
    ticker = await search_ticker(brand_name)
    if not ticker:
        return None

    stock_data = await fetch_stock_data(ticker)
    if not stock_data:
        return None

    stock_data["searched_brand"] = brand_name
    return stock_data


def stock_change_to_mood_score(change_percent: float) -> int:
    """
    Convert stock change percentage to 0-100 mood scale.

    50 = neutral
    +5 points per 1% change

    Args:
        change_percent: Stock change as percentage (e.g., 2.5 for +2.5%)

    Returns:
        Score from 0-100
    """
    score = int(50 + (change_percent * 5))
    return max(0, min(100, score))


async def get_market_index() -> Optional[dict]:
    """
    Get S&P 500 (SPY) as default market index.

    Returns:
        Dict with SPY stock data or None
    """
    return await fetch_stock_data("SPY")
