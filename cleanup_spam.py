#!/usr/bin/env python3
"""One-time cleanup of spam from existing data"""
import pandas as pd

SPAM_PATTERNS = [
    "available at these retailers", "shop now", "buy now",
    "air jordan", "releasing at", "drops at", "nike dunk", "yeezy",
    "@idos_network", "stablecoin", "tokenomics", "airdrop",
    "zero stress", "clean entries", "#STOCK", "#Finance",
    "#AHLBruins", "#NHLBruins", "#PITvsBAL", "@Sports_Musik",
    "Liverpool", "Brighton", "Salah", "Bruins", "Providence",
    "nfl", "nba", "mlb", "nhl", "fifa", "uefa", "premier league"
]

for filename in ["social.csv", "social_scored.csv"]:
    try:
        df = pd.read_csv(filename)
        original = len(df)
        
        # Filter out spam
        mask = ~df["text"].str.lower().str.contains("|".join(SPAM_PATTERNS), na=False, regex=True)
        df = df[mask]
        
        removed = original - len(df)
        df.to_csv(filename, index=False)
        print(f"{filename}: Removed {removed} spam entries, kept {len(df)}")
    except Exception as e:
        print(f"{filename}: {e}")

print("Cleanup complete!")
