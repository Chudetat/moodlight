import os
import stripe
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

app = FastAPI()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

def get_db_engine():
    return create_engine(os.getenv("DATABASE_URL"))

# Map Stripe price IDs to tiers
# Monthly = $899/month (all-access, unlimited briefs)
# Annually = $8,999/year (all-access, unlimited briefs)
PRICE_TO_TIER = {
    "price_1SyI3P1OGs3ZkUZa8IwdSO85": "monthly",     # $899/mo
    "price_1Szgi81OGs3ZkUZaZlFrKOAw": "annually",     # $8,999/yr
}

def _activate_pending_signup(signup_token: str, customer_id: str = None, subscription_id: str = None):
    """Activate a self-service signup: create user in DB from pending_signups."""
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT name, email, username, password_hash, tier FROM pending_signups "
            "WHERE signup_token = :token AND status = 'pending'"
        ), {"token": signup_token}).fetchone()
        if not row:
            print(f"⚠️ No pending signup found for token {signup_token[:8]}...")
            return

        name, email, username, password_hash, tier = row

        # Check user doesn't already exist (safety)
        existing = conn.execute(text(
            "SELECT id FROM users WHERE email = :email OR username = :username"
        ), {"email": email, "username": username}).fetchone()
        if existing:
            print(f"⚠️ User {email} already exists, skipping creation")
            conn.execute(text(
                "UPDATE pending_signups SET status = 'completed' WHERE signup_token = :token"
            ), {"token": signup_token})
            conn.commit()
            return

        # Create the user
        conn.execute(text("""
            INSERT INTO users (username, email, password_hash, tier, stripe_customer_id, stripe_subscription_id)
            VALUES (:username, :email, :password_hash, :tier, :customer_id, :subscription_id)
        """), {
            "username": username, "email": email, "password_hash": password_hash,
            "tier": tier, "customer_id": customer_id, "subscription_id": subscription_id,
        })

        # Mark signup as completed (Streamlit will sync to config.yaml)
        conn.execute(text(
            "UPDATE pending_signups SET status = 'completed' WHERE signup_token = :token"
        ), {"token": signup_token})
        conn.commit()
        print(f"✅ Self-service signup activated: {email} ({tier})")


def update_user_tier_by_email(email: str, tier: str, customer_id: str, subscription_id: str):
    """Update user tier in database"""
    engine = get_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            UPDATE users
            SET tier = :tier,
                stripe_customer_id = :customer_id,
                stripe_subscription_id = :subscription_id,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = :email
            RETURNING id
        """), {
            "email": email,
            "tier": tier,
            "customer_id": customer_id,
            "subscription_id": subscription_id
        })
        conn.commit()
        return result.fetchone() is not None

def add_brief_credits_by_email(email: str, credits: int):
    """Add brief credits after one-time purchase"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users
            SET brief_credits = brief_credits + :credits,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = :email
        """), {"email": email, "credits": credits})
        conn.commit()

def downgrade_user_by_subscription(subscription_id: str):
    """Remove user tier on cancellation"""
    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE users
            SET tier = 'cancelled',
                stripe_subscription_id = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE stripe_subscription_id = :subscription_id
        """), {"subscription_id": subscription_id})
        conn.commit()

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle checkout.session.completed (new subscription or one-time purchase)
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        client_ref = session.get("client_reference_id")

        # Check for self-service signup via client_reference_id
        if client_ref:
            _activate_pending_signup(client_ref, customer_id, subscription_id)

        if subscription_id:
            # Subscription purchase (Monthly or Annually)
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription["items"]["data"][0]["price"]["id"]
            tier = PRICE_TO_TIER.get(price_id, "monthly")

            if customer_email:
                update_user_tier_by_email(customer_email, tier, customer_id, subscription_id)
                print(f"✅ Updated {customer_email} to {tier}")

    # Handle subscription updates (upgrade/downgrade)
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        price_id = subscription["items"]["data"][0]["price"]["id"]
        tier = PRICE_TO_TIER.get(price_id, "monthly")

        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE users
                SET tier = :tier, updated_at = CURRENT_TIMESTAMP
                WHERE stripe_subscription_id = :subscription_id
            """), {"tier": tier, "subscription_id": subscription_id})
            conn.commit()
        print(f"✅ Updated subscription {subscription_id} to {tier}")

    # Handle cancellation
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        downgrade_user_by_subscription(subscription_id)
        print(f"✅ Downgraded subscription {subscription_id}")

    return {"status": "success"}

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """Create a Stripe Checkout session for new subscriptions."""
    data = await request.json()
    price_id = data.get("price_id")
    username = data.get("username")
    email = data.get("email")

    if not price_id or not email:
        raise HTTPException(status_code=400, detail="price_id and email are required")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=email,
        success_url=data.get("success_url", "https://moodlight.streamlit.app/?checkout=success"),
        cancel_url=data.get("cancel_url", "https://moodlight.streamlit.app/?checkout=cancel"),
        metadata={"username": username or ""},
    )
    return {"url": session.url}


@app.post("/create-portal-session")
async def create_portal_session(request: Request):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    data = await request.json()
    customer_id = data.get("customer_id")

    if not customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=data.get("return_url", "https://moodlight.streamlit.app/"),
    )
    return {"url": session.url}


@app.get("/health")
def health():
    from datetime import datetime, timezone
    result = {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "pipelines": {}}
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT ON (pipeline_name)
                    pipeline_name, status, row_count, started_at, completed_at
                FROM pipeline_runs
                ORDER BY pipeline_name, started_at DESC
            """)).fetchall()
            for row in rows:
                name, status, row_count, started_at, completed_at = row
                age_hours = None
                if completed_at:
                    age_hours = round((datetime.now(timezone.utc) - completed_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
                result["pipelines"][name] = {
                    "status": status,
                    "row_count": row_count,
                    "last_run": started_at.isoformat() if started_at else None,
                    "age_hours": age_hours,
                }
            # Mark degraded if any pipeline failed or is stale
            for p in result["pipelines"].values():
                if p["status"] == "failed" or (p["age_hours"] and p["age_hours"] > 25):
                    result["status"] = "degraded"
                    break
    except Exception:
        pass
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
