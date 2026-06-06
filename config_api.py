#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONFIG - API KEYS & SETTINGS
Untuk real-time news fetching
"""

import os
from datetime import datetime

# ============================================================================
# NEWSAPI Configuration
# ============================================================================
# Get FREE API key dari: https://newsapi.org/ (free tier = 100 requests/day)
NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY', "bd4abc51085b47a9bbe5f0d95496facf")  # Environment variable or fallback

# ============================================================================
# ALTERNATIVE NEWS SOURCES (Jika NewsAPI tidak tersedia)
# ============================================================================
ALTERNATIVE_SOURCES = [
    'https://finance.yahoo.com',  # Yahoo Finance
    'https://www.cnbc.com',       # CNBC
    'https://www.bloomberg.com',  # Bloomberg
]

# ============================================================================
# UPDATE INTERVALS (dalam detik)
# ============================================================================
NEWS_UPDATE_INTERVAL = 3600  # Update berita setiap 1 jam
SENTIMENT_CACHE_DURATION = 300  # Cache sentiment 5 menit

# ============================================================================
# NEWS SEARCH KEYWORDS
# ============================================================================
SEARCH_KEYWORDS = {
    'BUMI': ['BUMI.JK', 'PT Bumi Resources', 'Bumi Resources Mineral', 'coal Indonesia'],
    'INET': ['INET.JK', 'PT Indonesia Energy', 'Indonesia Energy', 'INET stock'],
    'GENERAL': ['Indonesia stock market', 'IDX', 'Jakarta stock exchange', 'Indonesian economy']
}

# ============================================================================
# SENTIMENT THRESHOLDS
# ============================================================================
SENTIMENT_THRESHOLDS = {
    'STRONG_POSITIVE': 0.7,   # Polarity > 0.7
    'POSITIVE': 0.3,          # Polarity > 0.3
    'NEUTRAL': (-0.3, 0.3),   # Between -0.3 and 0.3
    'NEGATIVE': -0.3,         # Polarity < -0.3
    'STRONG_NEGATIVE': -0.7,  # Polarity < -0.7
}

# ============================================================================
# DATA STORAGE
# ============================================================================
NEWS_DB_FILE = 'output/news_database.csv'
SENTIMENT_HISTORY_FILE = 'output/sentiment_history.csv'

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE = 'output/news_sentiment_log.txt'
ENABLE_LOGGING = True

def log_message(message):
    """Log message ke file"""
    if ENABLE_LOGGING:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
        print(f"[{timestamp}] {message}")

def setup_newsapi():
    """Check & setup NewsAPI key"""
    if not NEWSAPI_KEY:
        print("\n⚠️  NEWSAPI_KEY tidak ditemukan!")
        print("Cara setup:")
        print("1. Daftar gratis di: https://newsapi.org/")
        print("2. Copy API key Anda")
        print("3. Set environment variable:")
        print("   Windows: set NEWSAPI_KEY=your-key-here")
        print("   Linux/Mac: export NEWSAPI_KEY=your-key-here")
        print("4. Atau edit file ini dan set NEWSAPI_KEY secara langsung")
        print("\n💡 Tanpa key, sistem akan gunakan fallback (limited)")
        return False
    return True

if __name__ == '__main__':
    setup_newsapi()
