#!/usr/bin/env python3
"""
ADD NEW SUBSCRIBER
Run: python add_user.py

This script:
1. Asks for username and email
2. Generates a secure password
3. Creates the hashed password
4. Outputs the config.yaml entry to copy/paste
5. Outputs the email template to send to subscriber
"""

import bcrypt
import secrets
import string

def generate_password(length=12):
    """Generate a secure random password"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def main():
    print("\n" + "="*50)
    print("🌙 MOODLIGHT - ADD NEW SUBSCRIBER")
    print("="*50 + "\n")
    
    # Get user info
    username = input("Username (lowercase, no spaces): ").strip().lower().replace(" ", "")
    email = input("Email: ").strip()
    name = input("Display name: ").strip()
    
    # Generate password
    password = generate_password()
    hashed = hash_password(password)
    
    print("\n" + "="*50)
    print("✅ STEP 1: Add to config.yaml")
    print("="*50)
    print(f"""
    {username}:
      email: {email}
      name: {name}
      password: {hashed}
      failed_login_attempts: 0
      logged_in: False
""")
    
    print("="*50)
    print("✅ STEP 2: Push to GitHub")
    print("="*50)
    print("""
git add config.yaml
git commit -m "Add new subscriber"
git push
""")
    
    print("="*50)
    print("✅ STEP 3: Send this email to subscriber")
    print("="*50)
    print(f"""
TO: {email}
SUBJECT: Your Moodlight Intelligence Access

Hi {name},

Welcome to Moodlight Intelligence!

Your login credentials:
---------------------------
URL: https://moodlight.app
Username: {username}
Password: {password}
---------------------------

Please log in and let me know if you have any questions.

Best,
Sonny
""")
    
    print("="*50)
    print("📋 SUMMARY")
    print("="*50)
    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"Email: {email}")
    print("\nDON'T FORGET: git push after editing config.yaml!")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
