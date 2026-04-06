#!/usr/bin/env python
"""
trade_executor.py
Executes trade recommendations from trade_analyst.py via Alpaca API.
Supports paper trading and live trading (controlled by ALPACA_BASE_URL).
Logs all trades to the database for portfolio tracking.
"""

import os
import sys
import json
import requests
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy import create_engine, text as sql_text
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY or "",
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY or "",
    "Content-Type": "application/json",
}


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)


def ensure_trade_tables(engine):
    """Create trade tracking tables if they don't exist."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS trade_log (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                action VARCHAR(10) NOT NULL,
                qty FLOAT NOT NULL,
                price FLOAT,
                amount_usd FLOAT,
                conviction INTEGER,
                stop_loss_pct FLOAT,
                take_profit_pct FLOAT,
                hold_days INTEGER,
                reasoning TEXT,
                alpaca_order_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                pnl FLOAT,
                closed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS trade_portfolio (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) UNIQUE NOT NULL,
                qty FLOAT NOT NULL DEFAULT 0,
                avg_entry FLOAT NOT NULL,
                current_price FLOAT,
                unrealized_pnl FLOAT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS trade_daily_snapshot (
                id SERIAL PRIMARY KEY,
                snapshot_date DATE UNIQUE NOT NULL,
                cash FLOAT,
                portfolio_value FLOAT,
                total_equity FLOAT,
                positions_json TEXT,
                trades_today INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()
    print("  Trade tables ensured")


# ── Alpaca API helpers ──────────────────────────────────────────────

def get_account():
    """Get Alpaca account info (cash, equity, etc.)."""
    url = f"{ALPACA_BASE_URL}/v2/account"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Failed to get account: {e}")
        return None


def get_positions():
    """Get all open positions."""
    url = f"{ALPACA_BASE_URL}/v2/positions"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Failed to get positions: {e}")
        return []


def get_position(symbol):
    """Get a specific position."""
    url = f"{ALPACA_BASE_URL}/v2/positions/{symbol}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Failed to get position {symbol}: {e}")
        return None


def place_order(symbol, qty=None, notional=None, side="buy", order_type="market", time_in_force="day"):
    """Place an order on Alpaca.

    Args:
        symbol: Stock ticker
        qty: Number of shares (use for sell)
        notional: Dollar amount (use for buy — supports fractional shares)
        side: 'buy' or 'sell'
        order_type: 'market', 'limit', 'stop', 'stop_limit'
        time_in_force: 'day', 'gtc', 'ioc'
    """
    url = f"{ALPACA_BASE_URL}/v2/orders"
    payload = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }

    if notional and side == "buy":
        payload["notional"] = str(round(notional, 2))
    elif qty:
        payload["qty"] = str(qty)
    else:
        print(f"  ERROR: Must specify qty or notional for {symbol}")
        return None

    try:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
        order = resp.json()
        print(f"  Order placed: {side.upper()} {symbol} — order ID: {order['id']}")
        return order
    except requests.exceptions.HTTPError as e:
        print(f"  Order failed for {symbol}: {e}")
        print(f"  Response: {e.response.text if e.response else 'No response'}")
        return None
    except Exception as e:
        print(f"  Order failed for {symbol}: {e}")
        return None


def close_position(symbol):
    """Close an entire position."""
    url = f"{ALPACA_BASE_URL}/v2/positions/{symbol}"
    try:
        resp = requests.delete(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        print(f"  Closed position: {symbol}")
        return resp.json()
    except Exception as e:
        print(f"  Failed to close {symbol}: {e}")
        return None


# ── Trade execution ─────────────────────────────────────────────────

def execute_trades(recommendations, engine):
    """Execute trade recommendations from trade_analyst."""
    ensure_trade_tables(engine)

    if not recommendations:
        print("  No recommendations to execute")
        return []

    trades = recommendations.get("trades", [])
    if not trades:
        print(f"  HOLD — {recommendations.get('hold_reason', 'No compelling setups')}")
        return []

    # Check account
    account = get_account()
    if not account:
        print("  ERROR: Cannot connect to Alpaca")
        return []

    cash = float(account.get("cash", 0))
    equity = float(account.get("equity", 0))
    print(f"  Account — Cash: ${cash:,.2f} | Equity: ${equity:,.2f}")

    executed = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for trade in trades:
        ticker = trade["ticker"]
        action = trade["action"].upper()
        amount = float(trade["amount_usd"])
        conviction = trade.get("conviction", 5)

        # Only execute high-conviction trades
        if conviction < 7:
            print(f"  SKIP {ticker} — conviction {conviction}/10 too low (min 7)")
            continue

        # Check we have enough cash for buys
        if action == "BUY" and amount > cash:
            print(f"  SKIP BUY {ticker} — need ${amount:.2f} but only ${cash:.2f} cash")
            continue

        print(f"\n  Executing: {action} {ticker} — ${amount:.2f} (conviction: {conviction}/10)")

        order = None
        if action == "BUY":
            order = place_order(ticker, notional=amount, side="buy")
        elif action == "SELL":
            # For sells, close the position or sell specific qty
            pos = get_position(ticker)
            if pos:
                order = close_position(ticker)
            else:
                print(f"  SKIP SELL {ticker} — no position to sell")
                continue

        if order:
            # Log to database
            order_id = order.get("id", "")
            filled_price = float(order.get("filled_avg_price") or 0)

            with engine.connect() as conn:
                conn.execute(sql_text("""
                    INSERT INTO trade_log
                        (trade_date, ticker, action, qty, price, amount_usd,
                         conviction, stop_loss_pct, take_profit_pct, hold_days,
                         reasoning, alpaca_order_id, status)
                    VALUES
                        (:date, :ticker, :action, :qty, :price, :amount,
                         :conviction, :sl, :tp, :hold,
                         :reasoning, :order_id, 'submitted')
                """), {
                    "date": today,
                    "ticker": ticker,
                    "action": action,
                    "qty": float(order.get("qty") or order.get("notional") or 0),
                    "price": filled_price,
                    "amount": amount,
                    "conviction": conviction,
                    "sl": trade.get("stop_loss_pct"),
                    "tp": trade.get("take_profit_pct"),
                    "hold": trade.get("hold_days"),
                    "reasoning": trade.get("reasoning", ""),
                    "order_id": order_id,
                })
                conn.commit()

            executed.append(trade)
            if action == "BUY":
                cash -= amount

    return executed


# ── Daily snapshot ──────────────────────────────────────────────────

def take_daily_snapshot(engine):
    """Record daily portfolio snapshot."""
    ensure_trade_tables(engine)

    account = get_account()
    if not account:
        print("  Cannot snapshot — Alpaca unreachable")
        return

    positions = get_positions()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cash = float(account.get("cash", 0))
    equity = float(account.get("equity", 0))
    portfolio_value = equity - cash

    positions_data = []
    for p in positions:
        positions_data.append({
            "symbol": p["symbol"],
            "qty": float(p["qty"]),
            "avg_entry": float(p["avg_entry_price"]),
            "current_price": float(p["current_price"]),
            "unrealized_pnl": float(p["unrealized_pl"]),
            "unrealized_pnl_pct": float(p["unrealized_plpc"]) * 100,
        })

    with engine.connect() as conn:
        conn.execute(sql_text("""
            INSERT INTO trade_daily_snapshot
                (snapshot_date, cash, portfolio_value, total_equity, positions_json)
            VALUES (:date, :cash, :pv, :equity, :positions)
            ON CONFLICT (snapshot_date) DO UPDATE SET
                cash = EXCLUDED.cash,
                portfolio_value = EXCLUDED.portfolio_value,
                total_equity = EXCLUDED.total_equity,
                positions_json = EXCLUDED.positions_json
        """), {
            "date": today,
            "cash": cash,
            "pv": portfolio_value,
            "equity": equity,
            "positions": json.dumps(positions_data),
        })
        conn.commit()

    print(f"  Snapshot saved — Cash: ${cash:,.2f} | Positions: ${portfolio_value:,.2f} | Total: ${equity:,.2f}")

    # Sync positions to trade_portfolio table
    with engine.connect() as conn:
        conn.execute(sql_text("DELETE FROM trade_portfolio"))
        for p in positions_data:
            conn.execute(sql_text("""
                INSERT INTO trade_portfolio (symbol, qty, avg_entry, current_price, unrealized_pnl)
                VALUES (:symbol, :qty, :entry, :price, :pnl)
            """), {
                "symbol": p["symbol"],
                "qty": p["qty"],
                "entry": p["avg_entry"],
                "price": p["current_price"],
                "pnl": p["unrealized_pnl"],
            })
        conn.commit()

    return {
        "cash": cash,
        "portfolio_value": portfolio_value,
        "equity": equity,
        "positions": positions_data,
    }


# ── Email summary ──────────────────────────────────────────────────

def send_trade_email(recommendations, executed, snapshot=None):
    """Email trade summary to Daniel."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("  Email credentials not configured — skipping email")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    market_read = recommendations.get("market_assessment", "N/A") if recommendations else "N/A"

    # Build email body
    lines = [
        f"<h2>Moodlight Trade Analyst — {today}</h2>",
        f"<p><strong>Market Assessment:</strong> {market_read}</p>",
    ]

    if snapshot:
        lines.append(f"<p><strong>Portfolio:</strong> Cash: ${snapshot['cash']:,.2f} | "
                      f"Positions: ${snapshot['portfolio_value']:,.2f} | "
                      f"Total Equity: ${snapshot['equity']:,.2f}</p>")

    if executed:
        lines.append("<h3>Trades Executed:</h3><ul>")
        for t in executed:
            lines.append(f"<li><strong>{t['action']} {t['ticker']}</strong> — ${t['amount_usd']} "
                         f"(conviction: {t['conviction']}/10)<br>"
                         f"Stop: {t.get('stop_loss_pct', '?')}% | Target: {t.get('take_profit_pct', '?')}%<br>"
                         f"<em>{t.get('reasoning', '')}</em></li>")
        lines.append("</ul>")
    else:
        hold_reason = recommendations.get("hold_reason", "No compelling setups") if recommendations else "No recommendations"
        lines.append(f"<h3>No trades today.</h3><p>{hold_reason}</p>")

    warnings = recommendations.get("risk_warnings", []) if recommendations else []
    if warnings:
        lines.append("<h3>Risk Warnings:</h3><ul>")
        for w in warnings:
            lines.append(f"<li>{w}</li>")
        lines.append("</ul>")

    html = "\n".join(lines)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Moodlight Trade] {today} — {len(executed)} trade(s)"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"  Trade email sent to {recipient}")
    except Exception as e:
        print(f"  Failed to send email: {e}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("MOODLIGHT TRADE EXECUTOR")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        sys.exit(1)

    engine = _get_engine()
    ensure_trade_tables(engine)

    # Step 1: Check account
    account = get_account()
    if not account:
        print("ERROR: Cannot connect to Alpaca")
        sys.exit(1)
    print(f"  Connected to Alpaca ({'PAPER' if 'paper' in ALPACA_BASE_URL else 'LIVE'})")
    print(f"  Cash: ${float(account['cash']):,.2f} | Equity: ${float(account['equity']):,.2f}")

    # Step 2: Get recommendations from analyst
    from trade_analyst import generate_trade_recommendations
    recommendations = generate_trade_recommendations(engine)

    # Step 3: Execute trades
    executed = execute_trades(recommendations, engine)

    # Step 4: Take daily snapshot
    snapshot = take_daily_snapshot(engine)

    # Step 5: Email summary
    send_trade_email(recommendations, executed, snapshot)

    print("\nDone.")
    sys.exit(0)


if __name__ == "__main__":
    main()
