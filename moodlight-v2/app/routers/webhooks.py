"""
Webhook handlers - Stripe subscription webhooks.
"""
import stripe
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import User

settings = get_settings()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key

# Map Stripe price IDs to tiers
# Update these with your actual Stripe price IDs
PRICE_TO_TIER = {
    "price_1SgsGD1OGs3ZkUZaGMYsURSQ": "starter",
    "price_1SgsGs1OGs3ZkUZauDjOAwdL": "pro",
    "price_1SgsID1OGs3ZkUZazlD10RZN": "enterprise",
}


async def update_user_tier_by_email(
    email: str,
    tier: str,
    customer_id: str,
    subscription_id: str
) -> bool:
    """Update user tier in database by email."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(User)
            .where(User.email == email)
            .values(
                tier=tier,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id
            )
            .returning(User.id)
        )
        await db.commit()
        return result.fetchone() is not None


async def update_user_tier_by_subscription(
    subscription_id: str,
    tier: str
) -> bool:
    """Update user tier by subscription ID."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(User)
            .where(User.stripe_subscription_id == subscription_id)
            .values(tier=tier)
            .returning(User.id)
        )
        await db.commit()
        return result.fetchone() is not None


async def downgrade_user_by_subscription(subscription_id: str) -> bool:
    """Downgrade user to starter on cancellation."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(User)
            .where(User.stripe_subscription_id == subscription_id)
            .values(
                tier="starter",
                stripe_subscription_id=None
            )
            .returning(User.id)
        )
        await db.commit()
        return result.fetchone() is not None


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for subscription management.

    Events handled:
    - checkout.session.completed: New subscription created
    - customer.subscription.updated: Subscription upgraded/downgraded
    - customer.subscription.deleted: Subscription cancelled
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]

    # Handle checkout.session.completed (new subscription)
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        if subscription_id and customer_email:
            # Get subscription to find the price/tier
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription["items"]["data"][0]["price"]["id"]
            tier = PRICE_TO_TIER.get(price_id, "starter")

            success = await update_user_tier_by_email(
                customer_email, tier, customer_id, subscription_id
            )
            if success:
                print(f"Updated {customer_email} to {tier}")
            else:
                print(f"User not found for email: {customer_email}")

    # Handle subscription updates (upgrade/downgrade)
    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        price_id = subscription["items"]["data"][0]["price"]["id"]
        tier = PRICE_TO_TIER.get(price_id, "starter")

        success = await update_user_tier_by_subscription(subscription_id, tier)
        if success:
            print(f"Updated subscription {subscription_id} to {tier}")

    # Handle cancellation
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]

        success = await downgrade_user_by_subscription(subscription_id)
        if success:
            print(f"Downgraded subscription {subscription_id}")

    # Handle payment failures (optional)
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_email = invoice.get("customer_email")
        print(f"Payment failed for {customer_email}")
        # Could send email notification here

    return {"status": "success", "event": event_type}
