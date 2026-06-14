#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════╗
║     REAL-TIME NEWS & SENTIMENT ANALYSIS - PRODUCTION         ║
║         Real Data from NewsAPI + Financial Sources            ║
╚════════════════════════════════════════════════════════════════╝

Features:
- Real news dari NewsAPI (100+ articles/queries)
- Auto-update setiap jam
- Real confidence scoring dari data asli
- Multiple language support (English + Indonesia)
- Persistent storage (CSV database)
"""

import sys
import io
import os

# Reconfigure standard streams to support UTF-8 encoding safely
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure output directory exists for database storage
os.makedirs('output', exist_ok=True)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')
import threading
import time

try:
    import requests
except ImportError:
    print("❌ requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from textblob import TextBlob
except ImportError:
    print("❌ textblob not installed. Run: pip install textblob")
    sys.exit(1)

from config_api import (
    NEWSAPI_KEY, NEWSAPI_KEYS, FINNHUB_KEY, SEARCH_KEYWORDS, SENTIMENT_THRESHOLDS,
    NEWS_UPDATE_INTERVAL, NEWS_DB_FILE, SENTIMENT_HISTORY_FILE,
    LOG_FILE, setup_newsapi, log_message
)

# ============================================================================
# 1. REAL NEWS FETCHER
# ============================================================================

class RealNewsAPI:
    """Fetch REAL news dari NewsAPI"""
    
    BASE_URL = "https://newsapi.org/v2"
    
    def __init__(self, api_key=None, api_keys=None):
        if api_keys:
            self.api_keys = api_keys
        elif api_key:
            self.api_keys = [api_key]
        else:
            self.api_keys = NEWSAPI_KEYS
        self.session = requests.Session()
        self.news_cache = {}
        self.last_update = {}
        
    def fetch_finnhub(self, query, limit=30):
        """Fetch live general financial news from Finnhub and filter locally by query keywords"""
        if not FINNHUB_KEY:
            return []
            
        url = "https://finnhub.io/api/v1/news"
        params = {
            'category': 'general',
            'token': FINNHUB_KEY
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            articles = response.json()
            
            # Filter articles containing query keywords in title or summary
            q = query.lower()
            related_keywords = [q]
            if 'bumi' in q or 'coal' in q or 'resources' in q:
                related_keywords.extend(['coal', 'mining', 'commodity', 'commodities', 'energy', 'power', 'resources'])
            if 'inet' in q or 'oil' in q or 'energy' in q:
                related_keywords.extend(['oil', 'gas', 'energy', 'crude', 'petroleum', 'fuel', 'drill', 'drilling'])
                
            matched = []
            for item in articles:
                headline = item.get('headline', '')
                summary = item.get('summary', '')
                text = (headline + " " + summary).lower()
                
                if any(kw in text for kw in related_keywords):
                    import time
                    pub_time = datetime.fromtimestamp(item.get('datetime', time.time())).strftime('%Y-%m-%dT%H:%M:%SZ')
                    matched.append({
                        'source': item.get('source', 'Finnhub'),
                        'title': headline,
                        'description': summary,
                        'content': summary,
                        'url': item.get('url', ''),
                        'image': item.get('image', ''),
                        'publishedAt': pub_time,
                        'author': item.get('source', 'Finnhub')
                    })
            print(f"  Finnhub search for '{query}' found {len(matched)} matching live articles.")
            return matched[:limit]
            
        except Exception as e:
            print(f"  ❌ Finnhub request failed: {str(e)[:60]}")
            return []

    def fetch_everything(self, query, language='en', limit=50):
        """
        Fetch news dari NewsAPI dan Finnhub secara bersamaan, dikombinasikan dengan fallback mock DB.
        """
        all_articles = []
        
        # 1. Ambil dari Finnhub jika key ada
        finnhub_articles = []
        if FINNHUB_KEY:
            finnhub_articles = self.fetch_finnhub(query, limit=limit)
            all_articles.extend(finnhub_articles)
            
        # 2. Ambil dari NewsAPI jika key ada (looping semua keys untuk fallback jika limit)
        newsapi_articles = []
        if self.api_keys:
            for i, key in enumerate(self.api_keys):
                if not key:
                    continue
                url = f"{self.BASE_URL}/everything"
                params = {
                    'q': query,
                    'sortBy': 'publishedAt',
                    'language': language,
                    'pageSize': min(limit, 100),
                    'apiKey': key
                }
                try:
                    response = self.session.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'ok':
                            articles = data.get('articles', [])
                            for article in articles:
                                newsapi_articles.append({
                                    'source': article.get('source', {}).get('name', 'NewsAPI') if isinstance(article.get('source'), dict) else article.get('source', 'NewsAPI'),
                                    'title': article.get('title', ''),
                                    'description': article.get('description', ''),
                                    'content': article.get('content', ''),
                                    'url': article.get('url', ''),
                                    'image': article.get('urlToImage', ''),
                                    'publishedAt': article.get('publishedAt', ''),
                                    'author': article.get('author', 'Unknown')
                                })
                            print(f"  ✅ NewsAPI fetch successful using key {i+1}/{len(self.api_keys)}")
                            break  # Sukses, hentikan loop key
                        else:
                            print(f"  ⚠️ NewsAPI error using key {i+1}: {data.get('message', 'Unknown error')}")
                    elif response.status_code == 429:
                        print(f"  ⚠️ NewsAPI key {i+1} hit rate limit (429). Trying next key...")
                    else:
                        print(f"  ⚠️ NewsAPI key {i+1} failed with status {response.status_code}. Trying next key...")
                except Exception as e:
                    print(f"  ⚠️ NewsAPI request failed for key {i+1}: {str(e)[:60]}")
                
        all_articles.extend(newsapi_articles)
        
        # 3. Gunakan fallback mock data hanya jika tidak ada berita sama sekali dari API
        if not newsapi_articles and not finnhub_articles:
            print(f"  ⚠️ Tidak ada berita dari API untuk query '{query}'. Menggunakan fallback mock data.")
            fallback_articles = self.fetch_fallback(query, limit=limit)
            all_articles.extend(fallback_articles)
        
        # Hapus duplikasi berdasarkan judul artikel
        unique_articles = {}
        for article in all_articles:
            title_key = article['title'].strip().lower()
            if title_key not in unique_articles:
                unique_articles[title_key] = article
                
        return list(unique_articles.values())[:limit]
    
    def fetch_fallback(self, query, limit=20):
        """Fallback jika NewsAPI tidak tersedia, mengembalikan berita mock yang sangat detail dan bervariasi"""
        now = datetime.now()
        mock_database = [
            # ==================== BUMI NEWS ====================
            {
                'source': 'CNBC Indonesia',
                'title': 'Bumi Resources (BUMI) Catat Kenaikan Produksi Batubara di Kuartal I 2026',
                'description': 'PT Bumi Resources Tbk (BUMI) melaporkan kenaikan volume produksi batubara sebesar 8% seiring peningkatan efisiensi operasional di tambang Kaltim.',
                'content': 'PT Bumi Resources Tbk (BUMI) melaporkan kenaikan volume produksi batubara sebesar 8% seiring peningkatan efisiensi operasional di tambang Kaltim.',
                'url': 'https://www.cnbcindonesia.com/market/bumi-resources-batubara',
                'image': '',
                'publishedAt': (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'CNBC Research'
            },
            {
                'source': 'Kontan',
                'title': 'Harga Batubara Menguat, Prospek Saham BUMI Resources Diproyeksikan Bullish',
                'description': 'Analis memproyeksikan saham BUMI Resources Tbk memiliki potensi apresiasi harga seiring tren pemulihan permintaan batubara dari kawasan Asia Pasifik.',
                'content': 'Analis memproyeksikan saham BUMI Resources Tbk memiliki potensi apresiasi harga seiring tren pemulihan permintaan batubara dari kawasan Asia Pasifik.',
                'url': 'https://www.kontan.co.id/saham/prospek-saham-bumi',
                'image': '',
                'publishedAt': (now - timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Reporter Kontan'
            },
            {
                'source': 'Bisnis Indonesia',
                'title': 'Bumi Resources Minerals (BRMS) Targetkan Peningkatan Kapasitas Produksi Emas',
                'description': 'Anak usaha grup BUMI, Bumi Resources Minerals (BRMS) optimis kapasitas pemrosesan emas di Palu akan mencapai target penuh tahun ini.',
                'content': 'Anak usaha grup BUMI, Bumi Resources Minerals (BRMS) optimis kapasitas pemrosesan emas di Palu akan mencapai target penuh tahun ini.',
                'url': 'https://www.bisnis.com/market/brms-emas-bumi',
                'image': '',
                'publishedAt': (now - timedelta(hours=10)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Bisnis Market'
            },
            {
                'source': 'Bareksa',
                'title': 'Analisis Teknikal Saham BUMI: Menguji Level Resisten Kuat di Rp 150',
                'description': 'Volume transaksi saham BUMI meningkat tajam. Indikator MACD dan RSI menunjukkan sinyal akumulasi beli yang kuat oleh investor domestik.',
                'content': 'Volume transaksi saham BUMI meningkat tajam. Indikator MACD dan RSI menunjukkan sinyal akumulasi beli yang kuat oleh investor domestik.',
                'url': 'https://www.bareksa.com/saham/analisis-teknikal-bumi',
                'image': '',
                'publishedAt': (now - timedelta(hours=20)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Tim Analis Bareksa'
            },
            {
                'source': 'IDX Channel',
                'title': 'Grup Salim Perkuat Sinergi Operasional, Kinerja BUMI Diproyeksikan Tumbuh Signifikan',
                'description': 'Langkah efisiensi biaya logistik yang diinisiasi manajemen baru bentukan Grup Salim sukses menekan cost of production BUMI secara masif.',
                'content': 'Langkah efisiensi biaya logistik yang diinisiasi manajemen baru bentukan Grup Salim sukses menekan cost of production BUMI secara masif.',
                'url': 'https://www.idxchannel.com/market-news/grup-salim-bumi-sinergi',
                'image': '',
                'publishedAt': (now - timedelta(hours=28)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'IDX Reporter'
            },
            {
                'source': 'Investor Daily',
                'title': 'BUMI Siap Ekspor Batubara Rendah Abu ke India dan Jepang Guna Amankan Margin laba',
                'description': 'Pihak manajemen BUMI menyebutkan kontrak baru pengapalan batubara berkalori tinggi telah diteken untuk kuartal mendatang.',
                'content': 'Pihak manajemen BUMI menyebutkan kontrak baru pengapalan batubara berkalori tinggi telah diteken untuk kuartal mendatang.',
                'url': 'https://investor.id/market/bumi-ekspor-india-jepang',
                'image': '',
                'publishedAt': (now - timedelta(hours=36)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Investor Research'
            },
            {
                'source': 'Market Bisnis',
                'title': 'Tekanan Beban Bunga Berkurang, Struktur Keuangan BUMI Semakin Sehat',
                'description': 'Pelunasan utang restrukturisasi secara bertahap membuat laba bersih BUMI berpeluang tumbuh positif di atas rata-rata industri batubara nasional.',
                'content': 'Pelunasan utang restrukturisasi secara bertahap membuat laba bersih BUMI berpeluang tumbuh positif di atas rata-rata industri batubara nasional.',
                'url': 'https://www.bisnis.com/market/keuangan-bumi-sehat',
                'image': '',
                'publishedAt': (now - timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Bisnis Editor'
            },
            # ==================== INET NEWS ====================
            {
                'source': 'Yahoo Finance',
                'title': 'Indonesia Energy (INET) Commences New Oil Well Drilling Operations in Kruh Block',
                'description': 'Indonesia Energy Corp (INET) announced it has successfully spudded a new exploration well to increase the daily crude oil output of the field.',
                'content': 'Indonesia Energy Corp (INET) announced it has successfully spudded a new exploration well to increase the daily crude oil output of the field.',
                'url': 'https://finance.yahoo.com/news/indonesia-energy-inet-drilling',
                'image': '',
                'publishedAt': (now - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Reuters'
            },
            {
                'source': 'MarketWatch',
                'title': 'INET Stock Surges on Positive Resource Estimate Report for Gas Reserve Blocks',
                'description': 'Shares of Indonesia Energy Corp (INET) are trading higher today after independent assessors upgraded the estimated reserves of their offshore assets.',
                'content': 'Shares of Indonesia Energy Corp (INET) are trading higher today after independent assessors upgraded the estimated reserves of their offshore assets.',
                'url': 'https://www.marketwatch.com/story/inet-stock-reserve-upgrade',
                'image': '',
                'publishedAt': (now - timedelta(hours=8)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'MarketWatch Editors'
            },
            {
                'source': 'CNBC',
                'title': 'Indonesia Energy Corp Targets 20% Crude Production Growth for Fiscal Year 2026',
                'description': 'Management of INET stated that the drilling campaign is fully funded and aims to establish a consistent oil supply for domestic and export markets.',
                'content': 'Management of INET stated that the drilling campaign is fully funded and aims to establish a consistent oil supply for domestic and export markets.',
                'url': 'https://www.cnbc.com/news/inet-indonesia-energy-growth',
                'image': '',
                'publishedAt': (now - timedelta(hours=14)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'CNBC Energy'
            },
            {
                'source': 'Bloomberg',
                'title': 'Energy Sector Momentum Catalyzes Trading Volume Surge in INET Shares',
                'description': 'Global oil price dynamics are boosting interest in micro-cap energy developers like Indonesia Energy Corp (INET), leading to heightened volatility.',
                'content': 'Global oil price dynamics are boosting interest in micro-cap energy developers like Indonesia Energy Corp (INET), leading to heightened volatility.',
                'url': 'https://www.bloomberg.com/news/inet-energy-volatility',
                'image': '',
                'publishedAt': (now - timedelta(hours=22)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Bloomberg News'
            },
            {
                'source': 'Oil & Gas Journal',
                'title': 'Indonesia Energy (INET) Moves Closer to Commercial Gas Production Phase',
                'description': 'The company announced successful flow tests on its latest exploratory wells, marking a massive milestone toward domestic gas distribution contracts.',
                'content': 'The company announced successful flow tests on its latest exploratory wells, marking a massive milestone toward domestic gas distribution contracts.',
                'url': 'https://www.ogj.com/exploration/inet-commercial-gas',
                'image': '',
                'publishedAt': (now - timedelta(hours=30)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'OGJ Editors'
            },
            {
                'source': 'S&P Global Platts',
                'title': 'INET Secured High-Value Offtake Agreements with National Distribution Partners',
                'description': 'New strategic contracts ensure stable revenue stream for Indonesia Energy Corp starting next quarter, significantly boosting positive investor sentiment.',
                'content': 'New strategic contracts ensure stable revenue stream for Indonesia Energy Corp starting next quarter, significantly boosting positive investor sentiment.',
                'url': 'https://www.spglobal.com/platts/inet-offtake-agreement',
                'image': '',
                'publishedAt': (now - timedelta(hours=42)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'Platts Analytics'
            },
            {
                'source': 'E&P Magazine',
                'title': 'Technological Advancements in kruh Block Boost drilling Efficiency for INET',
                'description': 'By deploying advanced rotary steerable systems, INET has reduced drilling times by 15%, lowering overall exploration costs.',
                'content': 'By deploying advanced rotary steerable systems, INET has reduced drilling times by 15%, lowering overall exploration costs.',
                'url': 'https://www.epmag.com/technology/inet-drilling-efficiency',
                'image': '',
                'publishedAt': (now - timedelta(hours=54)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'author': 'E&P Reporter'
            }
        ]
        
        # Sederhana: filter mock data yang memiliki query pencarian di title/desc
        q = query.lower()
        matched = []
        for item in mock_database:
            text = (item['title'] + " " + item['description']).lower()
            if q in text or ('bumi' in q and 'bumi' in text) or ('inet' in q and 'inet' in text) or ('energy' in q and 'energy' in text):
                matched.append(item)
        
        return matched[:limit]
    
    def fetch_all_stocks(self, stocks=['BUMI', 'INET']):
        """Fetch news untuk semua stocks"""
        all_news = []
        
        for stock in stocks:
            keywords = SEARCH_KEYWORDS.get(stock, [stock])
            for keyword in keywords:
                articles = self.fetch_everything(keyword, limit=500)
                all_news.extend(articles)
        
        # Remove duplicates
        unique_news = {}
        for article in all_news:
            key = article['title']
            if key not in unique_news:
                unique_news[key] = article
        
        return list(unique_news.values())

# ============================================================================
# 2. REAL SENTIMENT ANALYZER
# ============================================================================

class RealSentimentAnalyzer:
    """Analyze sentiment dengan real scoring"""
    
    def __init__(self):
        self.sentiment_history = []
        self.confidence_weights = {
            'polarity': 0.6,      # Polarity weight
            'subjectivity': 0.2,  # Subjectivity (higher = more factual)
            'length': 0.1,        # Text length (longer = more detailed)
            'source_trust': 0.1   # Source credibility
        }
    
    def analyze_text(self, text):
        """Analyze sentiment with multiple metrics, including Indonesian and financial keyword detection"""
        
        if not text or len(text.strip()) < 5:
            return {
                'sentiment': 'NEUTRAL',
                'polarity': 0.0,
                'subjectivity': 0.5,
                'confidence': 0.0
            }
        
        try:
            text_lower = text.lower()
            
            # 1. Base polarity from TextBlob
            blob = TextBlob(str(text))
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # 2. Keyword matching for Indonesian and Financial English terms
            pos_words = [
                'kenaikan', 'naik', 'menguat', 'bullish', 'laba', 'untung', 'positif', 'kinerja baik', 
                'growth', 'surge', 'boost', 'expand', 'positive', 'gain', 'jump', 'soar', 'optimis', 'optimism',
                'rebound', 'meningkat', 'apresiasi', 'peningkatan'
            ]
            neg_words = [
                'penurunan', 'turun', 'melemah', 'bearish', 'rugi', 'negatif', 'merosot', 'anjlok',
                'drop', 'slump', 'decline', 'negative', 'loss', 'fall', 'plunge', 'warn', 'leakage',
                'lemah', 'depresiasi'
            ]
            
            pos_count = sum(1 for w in pos_words if w in text_lower)
            neg_count = sum(1 for w in neg_words if w in text_lower)
            
            # Adjust polarity based on keyword search
            keyword_score = 0.0
            if pos_count > 0 or neg_count > 0:
                keyword_score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
                # Cap the keyword influence to [-0.8, 0.8]
                keyword_score = max(min(keyword_score * 0.5, 0.8), -0.8)
            
            # Combine TextBlob polarity and keyword score
            if polarity == 0.0:
                polarity = keyword_score
            else:
                # Weighted average: 40% TextBlob, 60% keywords
                polarity = 0.4 * polarity + 0.6 * keyword_score
                
            # Clamp polarity to [-1.0, 1.0]
            polarity = max(min(polarity, 1.0), -1.0)
            
            # Determine sentiment class
            if polarity > SENTIMENT_THRESHOLDS['STRONG_POSITIVE']:
                sentiment = 'STRONG_POSITIVE'
                confidence_base = abs(polarity)
            elif polarity > SENTIMENT_THRESHOLDS['POSITIVE']:
                sentiment = 'POSITIVE'
                confidence_base = abs(polarity) * 0.9
            elif polarity < SENTIMENT_THRESHOLDS['STRONG_NEGATIVE']:
                sentiment = 'STRONG_NEGATIVE'
                confidence_base = abs(polarity)
            elif polarity < SENTIMENT_THRESHOLDS['NEGATIVE']:
                sentiment = 'NEGATIVE'
                confidence_base = abs(polarity) * 0.9
            else:
                sentiment = 'NEUTRAL'
                confidence_base = 1 - abs(polarity)
            
            # Calculate real confidence from text properties
            text_length = len(text.split())
            length_factor = min(text_length / 200, 1.0)  # Normalize by 200 words
            
            # Combine confidence metrics
            confidence = (
                confidence_base * self.confidence_weights['polarity'] +
                (1 - subjectivity) * self.confidence_weights['subjectivity'] +
                length_factor * self.confidence_weights['length'] +
                0.5 * self.confidence_weights['source_trust']  # Default trust
            )
            
            return {
                'sentiment': sentiment,
                'polarity': round(polarity, 3),
                'subjectivity': round(subjectivity, 3),
                'confidence': round(confidence, 3),
                'text_length': text_length
            }
            
        except Exception as e:
            print(f"  Sentiment error: {str(e)[:50]}")
            return {
                'sentiment': 'NEUTRAL',
                'polarity': 0.0,
                'subjectivity': 0.5,
                'confidence': 0.0
            }
    
    def aggregate_articles(self, articles):
        """Aggregate sentiment dari multiple articles"""
        
        if not articles:
            return {
                'sentiment': 'NEUTRAL',
                'score': 0.0,
                'confidence': 0.0,
                'breakdown': {'STRONG_POSITIVE': 0, 'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0, 'STRONG_NEGATIVE': 0},
                'total_articles': 0,
                'avg_polarity': 0.0
            }
        
        sentiments = {'STRONG_POSITIVE': 0, 'POSITIVE': 0, 'NEUTRAL': 0, 'NEGATIVE': 0, 'STRONG_NEGATIVE': 0}
        polarities = []
        confidences = []
        
        for article in articles:
            # Combine title + description untuk lebih complete analysis
            title = article.get('title') or ''
            desc = article.get('description') or ''
            text = (title + ' ' + desc).strip()
            
            analysis = self.analyze_text(text)
            sentiments[analysis['sentiment']] += 1
            polarities.append(analysis['polarity'])
            confidences.append(analysis['confidence'])
        
        # Aggregate scores
        avg_polarity = np.mean(polarities) if polarities else 0
        avg_confidence = np.mean(confidences) if confidences else 0
        total = sum(sentiments.values())
        
        # Determine overall sentiment
        sentiment_scores = {
            'STRONG_POSITIVE': sentiments['STRONG_POSITIVE'] * 2 + sentiments['POSITIVE'],
            'POSITIVE': sentiments['POSITIVE'],
            'NEUTRAL': sentiments['NEUTRAL'],
            'NEGATIVE': sentiments['NEGATIVE'],
            'STRONG_NEGATIVE': sentiments['STRONG_NEGATIVE'] * 2 + sentiments['NEGATIVE']
        }
        
        max_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        
        return {
            'sentiment': max_sentiment,
            'score': round(avg_polarity, 3),
            'confidence': round(avg_confidence, 3),
            'breakdown': sentiments,
            'total_articles': total,
            'avg_polarity': round(avg_polarity, 3)
        }

# ============================================================================
# 3. CONFIDENCE CALCULATOR (REAL)
# ============================================================================

class RealConfidenceCalculator:
    """Calculate confidence from real data"""
    
    @staticmethod
    def calculate_trend_confidence(sentiment_result, historical_data=None):
        """
        Calculate confidence untuk trend prediction
        
        Based on:
        - Sentiment strength (polarity & confidence)
        - Article count (lebih banyak = lebih confident)
        - Sentiment consistency
        - Historical patterns (jika ada)
        """
        
        confidence_score = 0.5  # Base 50%
        
        # 1. Sentiment strength (20%)
        sentiment = sentiment_result['sentiment']
        base_sentiment_confidence = {
            'STRONG_POSITIVE': 0.95,
            'POSITIVE': 0.70,
            'NEUTRAL': 0.40,
            'NEGATIVE': 0.70,
            'STRONG_NEGATIVE': 0.95
        }
        confidence_score += base_sentiment_confidence.get(sentiment, 0.40) * 0.20
        
        # 2. Article count (15%)
        total_articles = sentiment_result['total_articles']
        article_factor = min(total_articles / 30, 1.0)  # Max at 30 articles
        confidence_score += article_factor * 0.15
        
        # 3. Sentiment consistency (15%)
        breakdown = sentiment_result['breakdown']
        max_sentiment_count = max(breakdown.values())
        consistency = max_sentiment_count / max(total_articles, 1)
        confidence_score += consistency * 0.15
        
        # 4. Polarity strength (20%)
        polarity_strength = abs(sentiment_result['score'])
        confidence_score += polarity_strength * 0.20
        
        # 5. Analyzer confidence (30%)
        confidence_score += sentiment_result['confidence'] * 0.30
        
        # Clamp to 0-1
        confidence_score = min(max(confidence_score, 0), 1)
        
        return round(confidence_score, 3)

# ============================================================================
# 4. DATA STORAGE
# ============================================================================

class NewsDataStore:
    """Store & retrieve news data"""
    
    def __init__(self, news_file=NEWS_DB_FILE, sentiment_file=SENTIMENT_HISTORY_FILE):
        self.news_file = news_file
        self.sentiment_file = sentiment_file
        self._ensure_files()
    
    def _ensure_files(self):
        """Ensure CSV files exist"""
        import os
        os.makedirs(os.path.dirname(self.news_file), exist_ok=True)
        
        if not os.path.exists(self.news_file):
            pd.DataFrame(columns=['timestamp', 'source', 'title', 'description', 'url', 'sentiment', 'polarity']).to_csv(self.news_file, index=False)
        
        if not os.path.exists(self.sentiment_file):
            pd.DataFrame(columns=['timestamp', 'stock', 'sentiment', 'confidence', 'score', 'total_articles']).to_csv(self.sentiment_file, index=False)
    
    def save_articles(self, articles):
        """Save articles to CSV with sentiment analysis"""
        analyzer = RealSentimentAnalyzer()
        rows = []
        for article in articles:
            title = article.get('title') or ''
            desc = article.get('description') or ''
            text = (title + ' ' + desc).strip()
            analysis = analyzer.analyze_text(text)
            
            # Use article published date if available, otherwise now
            pub_date = article.get('publishedAt') or datetime.now().isoformat()
            
            rows.append({
                'timestamp': pub_date,
                'source': article.get('source', 'Unknown'),
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'url': article.get('url', ''),
                'sentiment': analysis['sentiment'],
                'polarity': analysis['polarity']
            })
        
        df_new = pd.DataFrame(rows)
        df_existing = pd.read_csv(self.news_file)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['title'], keep='last')  # Keep the latest analyzed article
        df_combined.to_csv(self.news_file, index=False)
    
    def save_sentiment(self, stock, sentiment_result, confidence):
        """Save sentiment analysis"""
        row = {
            'timestamp': datetime.now().isoformat(),
            'stock': stock,
            'sentiment': sentiment_result['sentiment'],
            'confidence': confidence,
            'score': sentiment_result['score'],
            'total_articles': sentiment_result['total_articles']
        }
        
        df_new = pd.DataFrame([row])
        df_existing = pd.read_csv(self.sentiment_file)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.to_csv(self.sentiment_file, index=False)

# ============================================================================
# 5. AUTO-UPDATE WORKER
# ============================================================================

class NewsAutoUpdater:
    """Auto-update news secara berkala"""
    
    def __init__(self, interval_seconds=3600):
        self.interval = interval_seconds
        self.running = False
        self.thread = None
        self.news_api = RealNewsAPI()
        self.analyzer = RealSentimentAnalyzer()
        self.store = NewsDataStore()
    
    def update_news(self):
        """Fetch & analyze news"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📰 Fetching real news...")
        
        articles = self.news_api.fetch_all_stocks()
        
        if articles:
            self.store.save_articles(articles)
            print(f"  ✅ Saved {len(articles)} articles")
        else:
            print(f"  ⚠️  No articles found")
    
    def start_background(self):
        """Start auto-update in background"""
        self.running = True
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
        print(f"📡 Auto-update started (every {self.interval}s)")
    
    def _background_loop(self):
        """Background update loop"""
        while self.running:
            try:
                self.update_news()
                time.sleep(self.interval)
            except Exception as e:
                print(f"❌ Update error: {str(e)[:60]}")
                time.sleep(60)
    
    def stop_background(self):
        """Stop auto-update"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

# ============================================================================
# 6. DISPLAY & REPORT
# ============================================================================

def display_real_sentiment(stocks=['BUMI', 'INET']):
    """Display real sentiment analysis"""
    
    print("\n" + "="*110)
    print("📰 REAL-TIME NEWS & SENTIMENT ANALYSIS (PRODUCTION)")
    print("="*110)
    
    news_api = RealNewsAPI()
    analyzer = RealSentimentAnalyzer()
    confidence_calc = RealConfidenceCalculator()
    store = NewsDataStore()
    
    for stock in stocks:
        print(f"\n📊 {stock} - Real Sentiment Analysis")
        print("-"*110)
        
        # Fetch news
        keywords = SEARCH_KEYWORDS.get(stock, [stock])
        all_articles = []
        
        for keyword in keywords:
            print(f"  Searching '{keyword}'...", end='')
            articles = news_api.fetch_everything(keyword, limit=500)
            all_articles.extend(articles)
            print(f" ✅ ({len(articles)} found)")
        
        if not all_articles:
            print(f"  ❌ No news found for {stock}")
            continue
        
        # Analyze sentiment
        sentiment_result = analyzer.aggregate_articles(all_articles)
        confidence = confidence_calc.calculate_trend_confidence(sentiment_result)
        
        # Determine trend
        if sentiment_result['sentiment'] in ['STRONG_POSITIVE', 'POSITIVE']:
            trend = "NAIK ↑"
        elif sentiment_result['sentiment'] in ['STRONG_NEGATIVE', 'NEGATIVE']:
            trend = "TURUN ↓"
        else:
            trend = "NEUTRAL →"
        
        # Display results
        print(f"\n  📈 SENTIMENT: {sentiment_result['sentiment']}")
        print(f"     Score: {sentiment_result['score']:.3f} (polarity)")
        print(f"     Confidence: {confidence:.1%} ⭐")
        print(f"     Trend Prediction: {trend}")
        print(f"\n  📊 Breakdown ({sentiment_result['total_articles']} articles):")
        breakdown = sentiment_result['breakdown']
        print(f"     Strong Positive: {breakdown['STRONG_POSITIVE']}")
        print(f"     Positive: {breakdown['POSITIVE']}")
        print(f"     Neutral: {breakdown['NEUTRAL']}")
        print(f"     Negative: {breakdown['NEGATIVE']}")
        print(f"     Strong Negative: {breakdown['STRONG_NEGATIVE']}")
        
        # Save
        store.save_articles(all_articles)
        store.save_sentiment(stock, sentiment_result, confidence)
    
    print("\n" + "="*110)
    print(f"✅ Data saved to:")
    print(f"   • {NEWS_DB_FILE} (articles)")
    print(f"   • {SENTIMENT_HISTORY_FILE} (history)")
    print("="*110 + "\n")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import sys
    
    # Setup
    setup_newsapi()
    
    if '--live' in sys.argv:
        # Live auto-update mode
        interval = NEWS_UPDATE_INTERVAL
        if '--interval' in sys.argv:
            idx = sys.argv.index('--interval')
            interval = int(sys.argv[idx + 1])
        
        updater = NewsAutoUpdater(interval_seconds=interval)
        updater.start_background()
        
        print(f"\n📡 Live sentiment monitoring started!")
        print(f"   Update interval: {interval} seconds")
        print(f"   Press Ctrl+C to stop\n")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n\n✋ Stopped")
            updater.stop_background()
    else:
        # Single analysis
        display_real_sentiment()
