"""
Customer management CLI for Moodlight.

Usage:
  Add a customer:
    python add_customer.py add --email "jane@company.com" --name "Jane Smith" --tier professional

  List all customers:
    python add_customer.py list

  Update credits for existing customer:
    python add_customer.py credits --email "jane@company.com" --add 10
"""
import os
import argparse
import bcrypt
import secrets
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_engine():
    return create_engine(os.getenv("DATABASE_URL"))

def add_customer(email, name=None, tier="professional", credits=0):
    """Add a new customer to the database"""
    engine = get_engine()
    username = name.lower().replace(" ", "_") if name else email.split("@")[0]
    # Generate a random temporary password
    temp_password = secrets.token_urlsafe(12)
    password_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()

    with engine.connect() as conn:
        # Check if user already exists
        result = conn.execute(text(
            "SELECT id, email, tier, brief_credits FROM users WHERE email = :email"
        ), {"email": email})
        existing = result.fetchone()

        if existing:
            print(f"⚠️  User already exists: {email}")
            print(f"   Tier: {existing[2]} | Credits: {existing[3]}")
            print(f"   Use 'python add_customer.py credits --email \"{email}\" --add N' to add credits")
            return

        conn.execute(text("""
            INSERT INTO users (username, email, password_hash, tier, brief_credits)
            VALUES (:username, :email, :password_hash, :tier, :credits)
        """), {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "tier": tier,
            "credits": credits
        })
        conn.commit()

    print(f"✅ Customer added successfully")
    print(f"   Name:     {name or username}")
    print(f"   Email:    {email}")
    print(f"   Username: {username}")
    print(f"   Tier:     {tier}")
    print(f"   Credits:  {credits}")
    print(f"   Password: {temp_password}")
    print(f"\n   Share the password with the customer. They can log in at moodlightintel.com")

def list_customers():
    """List all customers with tier and credits"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT username, email, tier, brief_credits, created_at
            FROM users ORDER BY created_at DESC
        """))
        rows = result.fetchall()

    if not rows:
        print("No customers found.")
        return

    print(f"\n{'Username':<20} {'Email':<35} {'Tier':<15} {'Credits':<10} {'Created'}")
    print("-" * 110)
    for row in rows:
        username, email, tier, credits, created_at = row
        credits_display = "unlimited" if tier in ("professional", "enterprise") else str(credits)
        created = str(created_at)[:10] if created_at else "N/A"
        print(f"{username:<20} {email:<35} {tier:<15} {credits_display:<10} {created}")
    print(f"\nTotal: {len(rows)} customers")

def update_credits(email, add_credits):
    """Add brief credits to an existing customer"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT username, tier, brief_credits FROM users WHERE email = :email"
        ), {"email": email})
        user = result.fetchone()

        if not user:
            print(f"❌ No user found with email: {email}")
            return

        if user[1] in ("professional", "enterprise"):
            print(f"ℹ️  {email} is on {user[1].title()} tier (unlimited briefs). No credits needed.")
            return

        conn.execute(text("""
            UPDATE users SET brief_credits = brief_credits + :credits, updated_at = CURRENT_TIMESTAMP
            WHERE email = :email
        """), {"email": email, "credits": add_credits})
        conn.commit()

    new_total = user[2] + add_credits
    print(f"✅ Added {add_credits} credits to {email}")
    print(f"   Previous: {user[2]} | New total: {new_total}")

def main():
    parser = argparse.ArgumentParser(description="Moodlight customer management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add customer
    add_parser = subparsers.add_parser("add", help="Add a new customer")
    add_parser.add_argument("--email", required=True, help="Customer email")
    add_parser.add_argument("--name", help="Customer name (optional)")
    add_parser.add_argument("--tier", default="professional", choices=["professional", "enterprise"], help="Tier (default: professional)")
    add_parser.add_argument("--credits", type=int, default=0, help="Initial brief credits (default: 0)")

    # List customers
    subparsers.add_parser("list", help="List all customers")

    # Update credits
    credits_parser = subparsers.add_parser("credits", help="Add brief credits to a customer")
    credits_parser.add_argument("--email", required=True, help="Customer email")
    credits_parser.add_argument("--add", type=int, required=True, help="Number of credits to add")

    args = parser.parse_args()

    if args.command == "add":
        add_customer(args.email, args.name, args.tier, args.credits)
    elif args.command == "list":
        list_customers()
    elif args.command == "credits":
        update_credits(args.email, args.add)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
