#!/usr/bin/env python
"""
fetch_news_rss.py
Fetches news + Reddit via RSS -> news.csv
With fallback dates so 48h filter works.
"""

import csv
import hashlib
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import pandas as pd
import sys

# -------------------------------
# HTTP Session with retry + timeout
# -------------------------------
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)


# -------------------------------
# Spam Filter
# -------------------------------
SPAM_KEYWORDS = [
    "sneaker", "yeezy", "air jordan", "nike air", "adidas",
    "red carpet", "gown", "runway", "fashion week", "wore a",
    "fast and furious", "soccer star", "football star",
    "chanel", "prada", "gucci", "louis vuitton",
    "celebrity", "actress", "actor", "hollywood star",
    "met gala", "golden globes", "best dressed", "worst dressed",
    "grammy", "oscar outfit", "emmy outfit",
    "dating", "boyfriend", "girlfriend", "married", "divorce",
    "baby bump", "pregnant", "engagement ring"
]

def is_spam(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in SPAM_KEYWORDS)

# -------------------------------
# RSS feeds (including Reddit)
# -------------------------------
FEEDS: List[tuple[str, str]] = [
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Politics", "http://feeds.bbci.co.uk/news/politics/rss.xml"),
    ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Technology", "http://feeds.bbci.co.uk/news/technology/rss.xml"),

    ("CNN Top", "http://rss.cnn.com/rss/edition.rss"),
    ("CNN World", "http://rss.cnn.com/rss/edition_world.rss"),
    ("CNN Business", "http://rss.cnn.com/rss/edition_business.rss"),
    ("CNN Tech", "http://rss.cnn.com/rss/edition_technology.rss"),

    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("Guardian Politics", "https://www.theguardian.com/politics/rss"),

    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),

    ("Japan Times", "https://www.japantimes.co.jp/feed/"),

    ("ESPN", "https://www.espn.com/espn/rss/news"),

    ("TechCrunch", "http://feeds.feedburner.com/TechCrunch/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),

    # REDDIT
    ("Reddit World News", "https://www.reddit.com/r/worldnews/.rss"),
    ("Reddit Uplifting News", "https://www.reddit.com/r/UpliftingNews/.rss"),
    ("Reddit News", "https://www.reddit.com/r/news/.rss"),
    
    # Fashion/Luxury Reddit
    
    # Marketing/Advertising Reddit
    ("Reddit Marketing", "https://www.reddit.com/r/marketing/.rss"),
    ("Reddit Advertising", "https://www.reddit.com/r/advertising/.rss"),
    ("Reddit PPC", "https://www.reddit.com/r/PPC/.rss"),
    
    # Business/Finance Reddit
    ("Reddit Business", "https://www.reddit.com/r/business/.rss"),
    ("Reddit Stocks", "https://www.reddit.com/r/stocks/.rss"),
    ("Reddit Investing", "https://www.reddit.com/r/investing/.rss"),
    
    # Tech Reddit
    ("Reddit Technology", "https://www.reddit.com/r/technology/.rss"),
    ("Reddit Apple", "https://www.reddit.com/r/apple/.rss"),
    ("Reddit Android", "https://www.reddit.com/r/Android/.rss"),
    
    # Business/Finance Trade
    ("Business Insider", "https://www.businessinsider.com/rss"),
    ("Fast Company", "https://www.fastcompany.com/latest/rss"),
    ("Inc", "https://www.inc.com/rss"),
    ("Entrepreneur", "https://www.entrepreneur.com/latest.rss"),
    ("Forbes", "https://www.forbes.com/innovation/feed/"),
    
    # Retail/Consumer
    ("Retail Dive", "https://www.retaildive.com/feeds/news/"),
    ("Modern Retail", "https://www.modernretail.co/feed/"),
    ("Glossy", "https://www.glossy.co/feed/"),
    
    # Tech Trade
    ("VentureBeat", "https://venturebeat.com/feed/"),
    ("ZDNet", "https://www.zdnet.com/news/rss.xml"),
    
    # PR/Comms
    ("PR Week", "https://www.prweek.com/rss"),
    ("Ragan", "https://www.ragan.com/feed/"),

    # E-commerce/DTC
    ("Retail Dive", "https://www.retaildive.com/feeds/news/"),
    ("Modern Retail", "https://www.modernretail.co/feed/"),
    ("Practical Ecommerce", "https://www.practicalecommerce.com/feed"),
    ("Digital Commerce 360", "https://www.digitalcommerce360.com/feed/"),
    ("2PM", "https://2pml.com/feed/"),

    # Health/Wellness/Fitness
    ("STAT News", "https://www.statnews.com/feed/"),
    ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml"),
    ("Healthcare Dive", "https://www.healthcaredive.com/feeds/news/"),
    ("MobiHealthNews", "https://www.mobihealthnews.com/feed"),
    ("Digital Health", "https://www.digitalhealth.net/feed/"),
    ("Well+Good", "https://www.wellandgood.com/feed/"),
    
    # Fitness/Wearables
    ("Wareable", "https://www.wareable.com/feed"),
    ("DC Rainmaker", "https://www.dcrainmaker.com/feed"),
    ("Fitness Industry", "https://www.fitnessindustry.com/feed/"),
    
    # Nutrition/Food Industry
    ("Food Dive", "https://www.fooddive.com/feeds/news/"),
    
    # Sustainability/Climate
    ("GreenBiz", "https://www.greenbiz.com/rss"),
    ("CleanTechnica", "https://cleantechnica.com/feed/"),
    ("Carbon Brief", "https://www.carbonbrief.org/feed"),

    # Culture/Lifestyle/Trends
    ("Hypebeast", "https://hypebeast.com/feed"),
    ("Highsnobiety", "https://www.highsnobiety.com/feed/"),
    ("Refinery29", "https://www.refinery29.com/rss.xml"),
    ("Vox", "https://www.vox.com/rss/index.xml"),
    ("The Atlantic", "https://www.theatlantic.com/feed/all/"),
    
    # Gen Z/Youth Culture
    ("Dazed", "https://www.dazeddigital.com/rss"),
    
    # Design/Creativity
    ("Dezeen", "https://www.dezeen.com/feed/"),
    ("Creative Review", "https://www.creativereview.co.uk/feed/"),
    ("Communication Arts", "https://www.commarts.com/feed"),
    
    # Music/Entertainment
    ("Pitchfork", "https://pitchfork.com/feed/feed-news/rss"),
    ("Rolling Stone", "https://www.rollingstone.com/feed/"),
    ("Variety", "https://variety.com/feed/"),
    ("The Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),
    
    
    # Parenting/Family
    ("Fatherly", "https://www.fatherly.com/feed"),
    
    # Travel/Hospitality
    ("Skift", "https://skift.com/feed/"),
    
    # Real Estate/Home
    ("Curbed", "https://www.curbed.com/rss/index.xml"),
    ("Dwell", "https://www.dwell.com/feed"),
    
    # Gaming
    
    # Crypto/Web3/Fintech
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    
    # Diversity/Inclusion
    ("Blavity", "https://blavity.com/feed"),
    
    # Future/Emerging Trends
    ("Singularity Hub", "https://singularityhub.com/feed/"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    ("Quartz", "https://qz.com/feed"),

    # Replacement feeds
    ("Financial Times via Google", "https://news.google.com/rss/search?q=site:ft.com&hl=en-US"),
    ("Korea Times", "https://www.koreatimes.co.kr/www/rss/rss.xml"),
    ("MindBodyGreen Alt", "https://news.google.com/rss/search?q=mindbodygreen&hl=en-US"),
    ("Triple Pundit", "https://www.triplepundit.com/feed"),
    ("GreenBiz", "https://www.greenbiz.com/feed"),
    ("Bustle", "https://www.bustle.com/rss"),
    ("Eye on Design Alt", "https://news.google.com/rss/search?q=graphic+design+trends&hl=en-US"),
    ("Condé Nast Traveler", "https://www.cntraveler.com/feed/rss"),
    ("The Points Guy", "https://thepointsguy.com/feed/"),
    ("Domino", "https://www.domino.com/feed"),
    ("Game Informer", "https://www.gameinformer.com/rss.xml"),
    ("Finextra", "https://www.finextra.com/rss/headlines.aspx"),
    ("The Grio", "https://thegrio.com/feed/"),

    # Industry/Trade Publications
    ("AdWeek", "https://www.adweek.com/feed/"),
    ("Digiday", "https://digiday.com/feed/"),
    ("Campaign US", "https://www.campaignus.com/rss"),
    ("Marketing Dive", "https://www.marketingdive.com/feeds/news/"),
    ("Jalopnik", "https://jalopnik.com/rss"),
    ("Engadget", "https://www.engadget.com/rss.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Wired", "https://www.wired.com/feed/rss"),

    # Reddit - Popular Subreddits
    ("Reddit News", "https://www.reddit.com/r/news/.rss"),
    ("Reddit World News", "https://www.reddit.com/r/worldnews/.rss"),
    ("Reddit Technology", "https://www.reddit.com/r/technology/.rss"),
    ("Reddit Business", "https://www.reddit.com/r/business/.rss"),
    ("Reddit Marketing", "https://www.reddit.com/r/marketing/.rss"),
    ("Reddit Advertising", "https://www.reddit.com/r/advertising/.rss"),
    ("Reddit Stocks", "https://www.reddit.com/r/stocks/.rss"),
    ("Reddit Economics", "https://www.reddit.com/r/economics/.rss"),
    ("Reddit Futurology", "https://www.reddit.com/r/Futurology/.rss"),
    ("Reddit Brands", "https://www.reddit.com/r/brands/.rss"),

    # Wire Services & Financial News
    ("PR Newswire", "https://www.prnewswire.com/rss/news-releases-list.rss"),
    ("GlobeNewswire", "https://www.globenewswire.com/RssFeed/subjectcode/01-Business%20Corporate/feedTitle/GlobeNewswire%20-%20Business%20Corporate"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Yahoo Finance Tech", "https://finance.yahoo.com/rss/topfinstories"),
    ("Business Wire", "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEF9RWA=="),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),

    # Government & Policy
    ("SEC Press Releases", "https://www.sec.gov/news/pressreleases.rss"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("FTC News", "https://www.ftc.gov/feeds/press-release-consumer-protection.xml"),
    
    # Business & Finance
    ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
    ("Financial Times", "https://www.ft.com/rss/home"),
    ("Fortune", "https://fortune.com/feed/"),
    ("Inc Magazine", "https://www.inc.com/rss/"),
    ("Fast Company", "https://www.fastcompany.com/latest/rss"),
    
    # PR & Marketing Industry
    ("PRWeek", "https://www.prweek.com/rss"),
    ("Ad Age", "https://adage.com/arc/outboundfeeds/rss/"),
    
    # Investment & Markets
    ("Motley Fool", "https://www.fool.com/feeds/index.aspx"),
    ("Benzinga", "https://www.benzinga.com/feed"),

    # Intelligence / Think Tanks
    ("Brookings", "https://www.brookings.edu/feed/"),
    ("Pew Research", "https://www.pewresearch.org/feed/"),
    ("Carnegie Endowment", "https://carnegieendowment.org/rss/solr/?fa=recentPubs"),

    # Healthcare / Pharma
    ("STAT News", "https://www.statnews.com/feed/"),
    ("Fierce Pharma", "https://www.fiercepharma.com/rss/xml"),
    ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml"),
    ("Healthcare Dive", "https://www.healthcaredive.com/feeds/news/"),
    ("Pharma Times", "https://www.pharmatimes.com/rss"),

    # Tech / AI Deep Dive
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("VentureBeat", "https://venturebeat.com/feed/"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("AI News", "https://www.artificialintelligence-news.com/feed/"),

    # Retail / Consumer
    ("Retail Dive", "https://www.retaildive.com/feeds/news/"),
    ("Retail Wire", "https://retailwire.com/feed/"),
    ("Consumer Goods Technology", "https://consumergoods.com/rss.xml"),

    # Sustainability / ESG
    ("GreenBiz", "https://www.greenbiz.com/rss.xml"),
    ("ESG Today", "https://www.esgtoday.com/feed/"),

    # Media / Entertainment
    ("Variety", "https://variety.com/feed/"),
    ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),

    # Legal
    ("Above the Law", "https://abovethelaw.com/feed/"),

    # Energy
    ("Oil & Gas Journal", "https://www.ogj.com/rss"),
    ("Utility Dive", "https://www.utilitydive.com/feeds/news/"),
    ("CleanTechnica", "https://cleantechnica.com/feed/"),

    # Automotive
    ("Motor Trend", "https://www.motortrend.com/feed/"),
    ("Car and Driver", "https://www.caranddriver.com/rss/all.xml"),
    ("Electrek", "https://electrek.co/feed/"),
    ("InsideEVs", "https://insideevs.com/rss/"),


    # Real Estate / Property
    ("Commercial Observer", "https://commercialobserver.com/feed/"),
    ("The Real Deal", "https://therealdeal.com/feed/"),

    # Supply Chain / Logistics
    ("Supply Chain Dive", "https://www.supplychaindive.com/feeds/news/"),
    ("FreightWaves", "https://www.freightwaves.com/feed"),

    # Food & Beverage
    ("Food Dive", "https://www.fooddive.com/feeds/news/"),
    ("Nation's Restaurant News", "https://www.nrn.com/rss.xml"),
    ("Beverage Industry", "https://www.bevindustry.com/rss"),

    # Travel & Hospitality
    ("Skift", "https://skift.com/feed/"),

    # Cybersecurity
    ("Dark Reading", "https://www.darkreading.com/rss.xml"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("Threatpost", "https://threatpost.com/feed/"),

    # Fintech
    ("Finextra", "https://www.finextra.com/rss/headlines.aspx"),
    ("PaymentsSource", "https://www.paymentssource.com/feed"),
    ("Finovate", "https://finovate.com/feed/"),

    # Aerospace / Defense
    ("Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/"),
    ("Aviation Week", "https://aviationweek.com/rss.xml"),
    ("SpaceNews", "https://spacenews.com/feed/"),
    ("Air Force Magazine", "https://www.airandspaceforces.com/feed/"),

    # Education
    ("Education Week", "https://www.edweek.org/feed"),
    ("Higher Ed Dive", "https://www.highereddive.com/feeds/news/"),
    ("Inside Higher Ed", "https://www.insidehighered.com/rss.xml"),
    ("EdSurge", "https://www.edsurge.com/rss"),

    # Telecom
    ("Fierce Telecom", "https://www.fiercetelecom.com/rss/xml"),
    ("Light Reading", "https://www.lightreading.com/rss.xml"),
    ("RCR Wireless", "https://www.rcrwireless.com/feed"),
    ("Capacity Media", "https://www.capacitymedia.com/rss"),

    # Insurance
    ("Insurance Journal", "https://www.insurancejournal.com/rss/"),
    ("Carrier Management", "https://www.carriermanagement.com/rss/"),
    ("Risk & Insurance", "https://riskandinsurance.com/feed/"),

    # HR / Workforce
    ("HR Dive", "https://www.hrdive.com/feeds/news/"),
    ("Workforce", "https://www.workforce.com/feed"),

    # Banking / Financial Services
    ("American Banker", "https://www.americanbanker.com/feed"),
    ("Banking Dive", "https://www.bankingdive.com/feeds/news/"),
    ("Bank Director", "https://www.bankdirector.com/feed/"),

    # Biotech / Life Sciences
    ("Fierce Biotech", "https://www.fiercebiotech.com/rss/xml"),
    ("Endpoints News", "https://endpts.com/feed/"),
    ("GEN News", "https://www.genengnews.com/feed/"),

    # Construction / Infrastructure
    ("Construction Dive", "https://www.constructiondive.com/feeds/news/"),
    ("ENR", "https://www.enr.com/rss"),

    # Agriculture / Food Production
    ("Ag Funder News", "https://agfundernews.com/feed"),
    ("Farm Journal", "https://www.agweb.com/rss.xml"),
    ("AgriPulse", "https://www.agri-pulse.com/rss"),
    ("World Grain", "https://www.world-grain.com/rss"),

    # Mining / Commodities
    ("Mining.com", "https://www.mining.com/feed/"),

    # Luxury / Fashion
    ("WWD", "https://wwd.com/feed/"),

    ("Polygon", "https://www.polygon.com/rss/index.xml"),
    ("GameSpot", "https://www.gamespot.com/feeds/news/"),

    # Nonprofit / Philanthropy
    ("Chronicle of Philanthropy", "https://www.philanthropy.com/feed"),
    ("Inside Philanthropy", "https://www.insidephilanthropy.com/feed"),

    # Packaging / CPG
    ("Packaging Dive", "https://www.packagingdive.com/feeds/news/"),

]

OUTPUT_CSV = "news.csv"
MAX_ITEMS_PER_FEED = 30

# -------------------------------
# Google News Dynamic Feeds (for brand coverage)
# -------------------------------
GOOGLE_NEWS_QUERIES = [
    # Luxury/Fashion
    "Louis Vuitton",
    "LVMH",
    "Gucci",
    "Hermès",
    "Chanel",
    "Prada",
    "Burberry",
    "Dior",
    "Cartier",
    "Rolex",
    "Tiffany",
    "Balenciaga",
    "Versace",
    "Fendi",
    "Valentino",
    "Givenchy",
    "Saint Laurent",
    "Bottega Veneta",
    "Moncler",
    "Kering",
    
    # Automotive
    "Porsche",
    "Hyundai",
    "Toyota",
    "Ford",
    "Tesla",
    "BMW",
    "Mercedes-Benz",
    "Honda",
    "Chevrolet",
    "Audi",
    "Lexus",
    "Volkswagen",
    "Kia",
    "Nissan",
    "Rivian",
    "Lucid Motors",
    "Ferrari",
    "Lamborghini",
    "Bentley",
    "Rolls-Royce",
    "Maserati",
    "Jaguar",
    "Land Rover",
    
    # Tech
    "Apple",
    "Samsung",
    "Google",
    "Microsoft",
    "Meta",
    "Amazon",
    "Nvidia",
    "OpenAI",
    "Anthropic",
    "IBM",
    "Intel",
    "AMD",
    "Salesforce",
    "Adobe",
    "Oracle",
    "Cisco",
    "Netflix",
    "Spotify",
    "TikTok",
    "Snapchat",
    "Twitter",
    "LinkedIn",
    
    # Apparel/Retail
    "Nike",
    "Adidas",
    "Lululemon",
    "Under Armour",
    "Puma",
    "New Balance",
    "Zara",
    "H&M",
    "Uniqlo",
    "Gap",
    "Nordstrom",
    "Sephora",
    "Ulta Beauty",
    
    # Big Retail
    "Walmart",
    "Target",
    "Costco",
    "Home Depot",
    "Lowes",
    "Best Buy",
    "Amazon",
    "Whole Foods",
    "Trader Joes",
    "Kroger",
    "Walgreens",
    "CVS",
    
    # Food & Beverage
    "Starbucks",
    "McDonalds",
    "Coca-Cola",
    "Pepsi",
    "Chipotle",
    "Chick-fil-A",
    "Dunkin",
    "Subway",
    "Wendys",
    "Burger King",
    "Taco Bell",
    "KFC",
    "Dominos",
    "Papa Johns",
    
    # Entertainment/Media
    "Disney",
    "Warner Bros",
    "Paramount",
    "Sony",
    "Nintendo",
    "Xbox",
    "Playstation",
    "HBO",
    "Hulu",
    "YouTube",
    "ESPN",
    "Fox News",
    "CNN",
    "New York Times",
    
    # Airlines/Travel
    "Delta Airlines",
    "United Airlines",
    "American Airlines",
    "Southwest Airlines",
    "JetBlue",
    "Airbnb",
    "Marriott",
    "Hilton",
    "Hyatt Hotels",
    "Uber",
    "Lyft",
    "Expedia",
    "Booking.com",
    
    # Finance
    "JPMorgan",
    "Goldman Sachs",
    "Bank of America",
    "Wells Fargo",
    "Citibank",
    "Morgan Stanley",
    "Visa",
    "Mastercard",
    "American Express",
    "PayPal",
    "Stripe",
    "Square",
    "Robinhood",
    "Coinbase",
    "BlackRock",
    "Fidelity",
    
    # Pharma/Health
    "Pfizer",
    "Johnson & Johnson",
    "Moderna",
    "Merck",
    "AbbVie",
    "UnitedHealth",
    "Cigna",
    "Aetna",
    "Kaiser Permanente",
    
    # Agencies/Marketing
    "Omnicom",
    "WPP",
    "Publicis",
    "IPG",
    "Dentsu",
    "Havas",
    
    # Consumer Goods
    "Procter & Gamble",
    "Unilever",
    "Nestle",
    "Colgate",
    "LOreal",
    "Estee Lauder",

    # Agencies/Marketing
    "Omnicom",
    "WPP",
    "Publicis",
    "IPG",
    "Dentsu",
    "Havas",
    "Ogilvy",
    "BBDO",
    "DDB",
    "TBWA",
    "McCann",
    "FCB",
    "Leo Burnett",
    "Saatchi & Saatchi",
    "Grey Advertising",
    "Wieden Kennedy",
    "Droga5",
    "R/GA",
    "AKQA",
    "Huge",
    "72andSunny",
    "Crispin Porter",
    "Goodby Silverstein",
    "Mother",
    "Anomaly",
    "VaynerMedia",
    "Horizon Media",
    "Mediacom",
    "Mindshare",
    "Wavemaker",
    "Essence",
    "GroupM",
]

def get_google_news_feeds() -> List[tuple[str, str]]:
    """Generate Google News RSS feeds for brand queries"""
    feeds = []
    for query in GOOGLE_NEWS_QUERIES:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
        feeds.append((f"Google News: {query}", url))
    return feeds

# -------------------------------
# Topic classification
# -------------------------------
TOPIC_KEYWORDS = {
    "politics": ["election", "president", "congress", "senate", "vote", "democrat", "republican", "political"],
    "government": ["government", "minister", "prime minister", "white house", "regulation", "policy", "administration"],
    "economics": ["economy", "inflation", "recession", "gdp", "markets", "stocks", "finance", "economic", "federal reserve"],
    "education": ["school", "teacher", "student", "university", "college", "campus", "education"],
    "culture & identity": ["culture", "identity", "values", "tradition", "community", "heritage"],
    "branding & advertising": ["branding", "brand", "marketing", "advertising", "commercial", "campaign"],
    "creative & design": ["design", "designer", "creative", "art direction", "illustration", "graphic"],
    "technology & ai": ["technology", "tech", "software", "hardware", "ai", "artificial intelligence", "startup", "app", "digital"],
    "climate & environment": ["climate", "environment", "warming", "emissions", "pollution", "flood", "weather", "storm", "wildfire"],
    "healthcare & wellbeing": ["healthcare", "hospital", "doctor", "mental health", "vaccine", "covid", "medical", "pandemic"],
    "immigration": ["immigration", "migrant", "refugee", "asylum", "border", "visa", "deportation"],
    "crime & safety": ["crime", "police", "shooting", "violence", "homicide", "murder", "robbery", "arrest"],
    "war & foreign policy": ["war", "conflict", "military", "israel", "gaza", "ukraine", "russia", "attack", "troops", "nuclear"],
    "media & journalism": ["media", "journalism", "reporter", "press", "headline", "newspaper"],
    "race & ethnicity": ["race", "racism", "ethnicity", "minority", "black", "asian", "discrimination"],
    "gender & sexuality": ["gender", "feminist", "lgbtq", "queer", "trans", "women", "abortion"],
    "business & corporate": ["business", "company", "ceo", "merger", "earnings", "profit", "revenue", "corporate"],
    "labor & work": ["labor", "union", "strike", "worker", "job", "wage", "employment", "unemployment"],
    "housing": ["housing", "rent", "landlord", "mortgage", "eviction", "real estate", "property"],
    "religion & values": ["religion", "church", "faith", "spiritual", "bible", "religious", "muslim", "christian"],
    "sports": ["sports", "game", "match", "team", "player", "athlete", "championship", "football", "basketball"],
    "entertainment": ["movie", "film", "tv", "music", "concert", "celebrity", "actor", "entertainment"],
}

def classify_topic(text: str) -> str:
    """Classify topic with priority ordering (more specific first)"""
    t = text.lower()

    # Priority order - check specific topics first
    priority_topics = [
        "war & foreign policy",
        "climate & environment", 
        "technology & ai",
        "healthcare & wellbeing",
        "crime & safety",
        "immigration",
    ]

    for topic in priority_topics:
        if any(kw in t for kw in TOPIC_KEYWORDS[topic]):
            return topic

    # Then check remaining topics
    for topic, kws in TOPIC_KEYWORDS.items():
        if topic not in priority_topics:
            if any(kw in t for kw in kws):
                return topic
# -------------------------------
# Country detection
# -------------------------------
COUNTRY_KEYWORDS = {
    "United States": ["united states", "u.s.", "usa", "america", "washington dc", "white house", "congress", "pentagon", "california", "texas", "new york", "florida"],
    "China": ["china", "chinese", "beijing", "shanghai", "xi jinping", "ccp"],
    "Russia": ["russia", "russian", "moscow", "putin", "kremlin"],
    "Ukraine": ["ukraine", "ukrainian", "kyiv", "kiev", "zelensky"],
    "Israel": ["israel", "israeli", "tel aviv", "jerusalem", "netanyahu", "idf"],
    "Palestine": ["palestine", "palestinian", "gaza", "west bank", "hamas"],
    "Iran": ["iran", "iranian", "tehran", "khamenei"],
    "North Korea": ["north korea", "pyongyang", "kim jong"],
    "South Korea": ["south korea", "korean", "seoul"],
    "Japan": ["japan", "japanese", "tokyo"],
    "India": ["india", "indian", "delhi", "mumbai", "modi"],
    "Pakistan": ["pakistan", "pakistani", "islamabad", "karachi"],
    "Afghanistan": ["afghanistan", "afghan", "kabul", "taliban"],
    "Iraq": ["iraq", "iraqi", "baghdad"],
    "Syria": ["syria", "syrian", "damascus", "assad"],
    "Yemen": ["yemen", "yemeni", "houthi", "sanaa"],
    "Saudi Arabia": ["saudi", "riyadh", "mbs"],
    "Turkey": ["turkey", "turkish", "ankara", "erdogan"],
    "Egypt": ["egypt", "egyptian", "cairo"],
    "Indonesia": ["indonesia", "indonesian", "jakarta", "aceh", "sumatra"],
    "Philippines": ["philippines", "filipino", "manila"],
    "Malaysia": ["malaysia", "malaysian", "kuala lumpur"],
    "Thailand": ["thailand", "thai", "bangkok"],
    "Vietnam": ["vietnam", "vietnamese", "hanoi"],
    "Myanmar": ["myanmar", "burma", "burmese", "yangon"],
    "Sri Lanka": ["sri lanka", "sri lankan", "colombo"],
    "Bangladesh": ["bangladesh", "bangladeshi", "dhaka"],
    "Germany": ["germany", "german", "berlin", "scholz"],
    "France": ["france", "french", "paris", "macron"],
    "Britain": ["britain", "british", "uk", "england", "london", "sunak"],
    "Italy": ["italy", "italian", "rome", "meloni"],
    "Spain": ["spain", "spanish", "madrid"],
    "Poland": ["poland", "polish", "warsaw"],
    "Netherlands": ["netherlands", "dutch", "amsterdam"],
    "Belgium": ["belgium", "belgian", "brussels"],
    "Sweden": ["sweden", "swedish", "stockholm"],
    "Norway": ["norway", "norwegian", "oslo"],
    "Finland": ["finland", "finnish", "helsinki"],
    "Denmark": ["denmark", "danish", "copenhagen"],
    "Estonia": ["estonia", "estonian", "tallinn"],
    "Latvia": ["latvia", "latvian", "riga"],
    "Lithuania": ["lithuania", "lithuanian", "vilnius"],
    "Hungary": ["hungary", "hungarian", "budapest", "orban"],
    "Romania": ["romania", "romanian", "bucharest"],
    "Bulgaria": ["bulgaria", "bulgarian", "sofia"],
    "Greece": ["greece", "greek", "athens"],
    "Serbia": ["serbia", "serbian", "belgrade"],
    "Bosnia": ["bosnia", "bosnian", "sarajevo"],
    "Kosovo": ["kosovo", "pristina"],
    "Croatia": ["croatia", "croatian", "zagreb"],
    "Australia": ["australia", "australian", "sydney", "melbourne", "canberra"],
    "New Zealand": ["new zealand", "wellington", "auckland"],
    "Canada": ["canada", "canadian", "ottawa", "toronto", "trudeau"],
    "Mexico": ["mexico", "mexican", "mexico city"],
    "Brazil": ["brazil", "brazilian", "brasilia", "lula"],
    "Argentina": ["argentina", "argentine", "buenos aires", "milei"],
    "Venezuela": ["venezuela", "venezuelan", "caracas", "maduro"],
    "Colombia": ["colombia", "colombian", "bogota"],
    "Chile": ["chile", "chilean", "santiago"],
    "Peru": ["peru", "peruvian", "lima"],
    "Cuba": ["cuba", "cuban", "havana"],
    "Haiti": ["haiti", "haitian", "port-au-prince"],
    "South Africa": ["south africa", "johannesburg", "cape town"],
    "Nigeria": ["nigeria", "nigerian", "lagos", "abuja"],
    "Kenya": ["kenya", "kenyan", "nairobi"],
    "Ethiopia": ["ethiopia", "ethiopian", "addis ababa"],
    "Sudan": ["sudan", "sudanese", "khartoum"],
    "Libya": ["libya", "libyan", "tripoli"],
    "Morocco": ["morocco", "moroccan", "rabat"],
    "Algeria": ["algeria", "algerian", "algiers"],
    "Tunisia": ["tunisia", "tunisian", "tunis"],
    "Niger": ["niger", "niamey"],
    "Mali": ["mali", "malian", "bamako"],
    "Somalia": ["somalia", "somali", "mogadishu"],
    "Congo": ["congo", "congolese", "kinshasa"],
    "Zimbabwe": ["zimbabwe", "harare"],
    "Oman": ["oman", "omani", "muscat"],
    "Qatar": ["qatar", "qatari", "doha"],
    "UAE": ["uae", "emirates", "dubai", "abu dhabi"],
    "Kuwait": ["kuwait", "kuwaiti"],
    "Bahrain": ["bahrain", "bahraini", "manama"],
    "Jordan": ["jordan", "jordanian", "amman"],
    "Lebanon": ["lebanon", "lebanese", "beirut", "hezbollah"],
    "Hong Kong": ["hong kong"],
    "Taiwan": ["taiwan", "taiwanese", "taipei"],
    "Singapore": ["singapore", "singaporean"],
    "Nepal": ["nepal", "nepali", "kathmandu"],
}

def detect_country(text: str) -> str:
    """Detect primary country mentioned in text"""
    t = text.lower()
    
    # Priority countries (conflict zones and major news makers)
    priority_countries = [
        "Ukraine", "Russia", "Israel", "Palestine", "Iran", "China", 
        "North Korea", "Syria", "Yemen", "Taiwan", "Indonesia", "Sri Lanka"
    ]
    
    for country in priority_countries:
        if any(kw in t for kw in COUNTRY_KEYWORDS[country]):
            return country
    
    # Check remaining countries
    for country, keywords in COUNTRY_KEYWORDS.items():
        if country not in priority_countries:
            if any(kw in t for kw in keywords):
                return country
    
    return "Unknown"

# -------------------------------
# Threat intensity scoring
# -------------------------------
INTENSITY_KEYWORDS = {
    5: ["war", "invasion", "massacre", "genocide", "nuclear strike", "mass casualty", "terrorist attack", "death toll", "killed", "deaths", "dead", "bombing", "airstrike", "missile strike", "chemical weapon", "biological weapon"],
    4: ["conflict", "military", "troops", "soldiers", "attack", "explosion", "crisis", "emergency", "disaster", "catastrophe", "flood", "earthquake", "hurricane", "cyclone", "tsunami", "famine", "epidemic", "pandemic", "coup", "assassination", "hostage", "kidnap"],
    3: ["tension", "threat", "warning", "sanction", "protest", "riot", "unrest", "violence", "clash", "dispute", "confrontation", "arrest", "detained", "refugee", "displaced", "evacuation", "shortage", "inflation", "recession"],
    2: ["concern", "fear", "worry", "uncertainty", "risk", "challenge", "issue", "problem", "investigation", "allegation", "accusation", "controversy", "debate", "opposition", "criticism"],
    1: ["stable", "peace", "agreement", "deal", "cooperation", "partnership", "growth", "recovery", "improvement", "success", "celebration", "achievement"],
}

def calculate_intensity(text: str) -> int:
    """Calculate threat intensity score 1-5 based on content"""
    t = text.lower()
    
    # Check from highest to lowest intensity
    for score in [5, 4, 3, 2, 1]:
        if any(kw in t for kw in INTENSITY_KEYWORDS[score]):
            return score
    
    # Default to moderate intensity for news
    return 2

# -------------------------------
# Text cleaning
# -------------------------------
def clean_text(text: Any) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    text = str(text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Remove URLs
    text = re.sub(r"http\S+|www\.\S+", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove common RSS artifacts
    text = re.sub(r"\[CDATA\[|\]\]", "", text)

    return text[:5000]

# -------------------------------
# Date parsing with better fallback
# -------------------------------
def parse_pubdate(date_str: str) -> str | None:
    """Parse publication date with multiple fallback methods"""
    if not date_str:
        return None

    # Try feedparser's built-in parser first
    try:
        parsed = feedparser._parse_date(date_str)
        if parsed:
            dt = datetime(*parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
    except Exception:
        pass

    # Try common date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            continue

    return None

# -------------------------------
# Deduplicate by content similarity
# -------------------------------
def deduplicate_entries(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate entries based on text similarity"""
    seen_hashes = set()
    unique_rows = []

    for row in rows:
        # Create hash from first 200 chars of text
        text_hash = hashlib.md5(row["text"][:200].lower().encode()).hexdigest()
        
        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            unique_rows.append(row)

    removed = len(rows) - len(unique_rows)
    if removed > 0:
        print(f"   Removed {removed} duplicate entries")

    return unique_rows

# -------------------------------
# Fetch one feed
# -------------------------------
def fetch_feed(source: str, url: str) -> List[Dict[str, Any]]:
    """Fetch and parse a single RSS feed"""
    print(f"Fetching {source} -> {url}")

    try:
        response = session.get(
            url, 
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml"
            }
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"   Timeout (skipping)")
        return []
    except requests.exceptions.RequestException as e:
        print(f"   Failed: {str(e)[:100]}")
        return []

    try:
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"   Parse error: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"   Parse warning: {feed.bozo_exception}")
        return []

    entries = feed.entries[:MAX_ITEMS_PER_FEED]
    rows = []
    now = datetime.now(timezone.utc)

    for entry in entries:
        try:
            # Get title and summary
            title = clean_text(entry.get("title", ""))
            
            # Try multiple fields for content
            summary = clean_text(
                entry.get("summary")
                or entry.get("description")
                or (entry.get("content", [{}])[0].get("value") if entry.get("content") else "")
                or ""
            )
            
            # Combine title and summary
            text = f"{title}. {summary}".strip() if summary else title
            
            # Skip if too short or empty
            if not text or len(text) < 20:
                continue

            # Get link
            link = entry.get("link", "")
            if isinstance(link, dict):
                link = link.get("href", "")

            # Generate ID
            eid = entry.get("id") or link or hashlib.md5(text.encode()).hexdigest()

            # Parse date with fallback
            pubdate = entry.get("published") or entry.get("updated") or ""
            created_at = parse_pubdate(pubdate)
            
            # Fallback: use current time if parsing failed
            if not created_at:
                # Skip Google News entries without valid publish date
                if "google_news" in source.lower():
                    continue
                created_at = now.isoformat()
            else:
                # Validate date isn't in the future or too old
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if dt > now:
                    created_at = now.isoformat()
                elif dt < now - timedelta(days=30):
                    continue  # Skip all old articles

            # Classify topic
            topic = classify_topic(text)

            # Detect country and calculate intensity
            country = detect_country(text)
            intensity = calculate_intensity(text)

            # Skip spam
            if is_spam(text):
                continue
                
            rows.append({
                "id": eid,
                "text": text,
                "created_at": created_at,
                "link": link,
                "source": source.lower().replace(" ", "_"),
                "topic": topic,
                "engagement": 0,
                "country": country,
                "intensity": intensity,
            })
        
        except Exception as e:
            print(f"   Skipped entry: {str(e)[:50]}")
            continue

    print(f"   Got {len(rows)} items")
    return rows

# -------------------------------
# Load existing data to preserve history
# -------------------------------
def load_existing_data() -> pd.DataFrame:
    """Load existing news.csv to preserve older entries"""
    try:
        df = pd.read_csv(OUTPUT_CSV)
        print(f"Loaded {len(df)} existing entries from {OUTPUT_CSV}")

        # Keep entries from last 7 days only
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            df = df[df["created_at"] >= cutoff]
            print(f"Kept {len(df)} entries from last 7 days")
        
        return df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        print("No existing data found (will create new file)")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading existing data: {e}")
        return pd.DataFrame()

# -------------------------------
# Main
# -------------------------------
def main():
    print("=" * 60)
    print("FETCHING NEWS & REDDIT RSS FEEDS")
    print("=" * 60)

    # Load existing data
    existing_df = load_existing_data()

    # Fetch new data
    all_rows = []
    successful_feeds = 0
    failed_feeds = 0

    # Combine static feeds with dynamic Google News feeds
    all_feeds = FEEDS + get_google_news_feeds()

    for source, url in all_feeds:

        rows = fetch_feed(source, url)
        if rows:
            all_rows.extend(rows)
            successful_feeds += 1
        else:
            failed_feeds += 1

    if not all_rows:
        print("\nNo new items fetched")
        if existing_df.empty:
            print("No existing data either - writing empty CSV")
            columns = ["id", "text", "created_at", "link", "source", "topic", "engagement", "country", "intensity"]
            df = pd.DataFrame(columns=columns)
            df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
            print(f"Saved empty file to {OUTPUT_CSV}")
            sys.exit(1)
        else:
            print(f"Keeping {len(existing_df)} existing entries")
            existing_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
            print(f"Saved to {OUTPUT_CSV}")
            sys.exit(0)

    print(f"\nSummary:")
    print(f"   Feeds attempted: {len(all_feeds)}")
    print(f"   Successful: {successful_feeds}")
    print(f"   Failed: {failed_feeds}")
    print(f"   New items fetched: {len(all_rows)}")

    # Deduplicate new entries
    all_rows = deduplicate_entries(all_rows)

    # Create DataFrame from new entries
    columns = ["id", "text", "created_at", "link", "source", "topic", "engagement", "country", "intensity"]
    new_df = pd.DataFrame(all_rows, columns=columns)

    # Combine with existing data
    if not existing_df.empty:
        # Ensure same columns
        for col in columns:
            if col not in existing_df.columns:
                existing_df[col] = ""
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Remove duplicates based on ID
        combined_df = combined_df.drop_duplicates(subset=["id"], keep="last")
        
        print(f"   Combined with existing: {len(combined_df)} total items")
    else:
        combined_df = new_df

    # Sort by date (newest first)
    if "created_at" in combined_df.columns:
        combined_df["created_at"] = pd.to_datetime(combined_df["created_at"], errors="coerce")
        combined_df = combined_df.sort_values("created_at", ascending=False)
        # Convert back to ISO format strings
        # Only convert if it's actually datetime type
        if pd.api.types.is_datetime64_any_dtype(combined_df["created_at"]):
            combined_df["created_at"] = combined_df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    # Save to CSV
    combined_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC)
    print(f"\nSaved {len(combined_df)} entries to {OUTPUT_CSV}")

    # Show topic breakdown
    if "topic" in combined_df.columns:
        print(f"\nTopic breakdown:")
        topic_counts = combined_df["topic"].value_counts().head(10)
        for topic, count in topic_counts.items():
            print(f"   {topic}: {count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)# Note: Adding these feeds
