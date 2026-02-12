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
        customer_email = session.get("customer_email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

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

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
