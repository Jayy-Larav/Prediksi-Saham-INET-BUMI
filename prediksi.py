#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════╗
║           PREDIKSI SAHAM BUMI & INET 30 HARI                  ║
║              Real Data from Yahoo Finance                      ║
╚════════════════════════════════════════════════════════════════╝

Usage:
  python prediksi.py                    # Auto fetch latest + predict
  python prediksi.py 152 181            # Predict with custom prices
  python prediksi.py --hari 5           # Show only 5 days ahead
  python prediksi.py --fetch            # Update data only
"""

import sys
import io
import os

# Reconfigure standard streams to support UTF-8 encoding safely
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure output directory exists for saving predictions and evaluation plots
os.makedirs('output', exist_ok=True)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import yfinance as yf
except ImportError:
    print("❌ yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

# Optional: Sentiment analysis
SENTIMENT_AVAILABLE = False
try:
    from news_sentiment_v2 import RealNewsAPI, RealSentimentAnalyzer, RealConfidenceCalculator, NewsDataStore
    from config_api import SEARCH_KEYWORDS
    SENTIMENT_AVAILABLE = True
except ImportError:
    pass

from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# ============================================================================
# 1. FETCH DATA FROM YAHOO FINANCE
# ============================================================================

def fetch_data_from_yfinance(symbols=['BUMI.JK', 'INET.JK'], period='5y'):
    """Fetch real stock data from Yahoo Finance"""
    print("\n📥 Fetching data from Yahoo Finance...")
    
    for symbol in symbols:
        filename = f"{symbol.split('.')[0]}_stock.csv"
        print(f"  Downloading {symbol}...", end='')
        
        try:
            df = yf.download(symbol, period=period, progress=False)
            if df.empty:
                print(f" ⚠️  No data found")
                continue
            
            df.to_csv(filename)
            print(f" ✅ Saved ({len(df)} rows)")
        except Exception as e:
            print(f" ❌ Error: {e}")

def get_latest_price(symbol):
    """Get latest stock price"""
    try:
        df = yf.download(symbol, period='1d', progress=False)
        if not df.empty:
            return round(df['Close'].iloc[-1], 2)
    except:
        pass
    return None

# ============================================================================
# 2. FEATURE ENGINEERING
# ============================================================================

def add_features(df, training=True):
    """Add technical indicators"""
    df = df.copy()
    
    # Moving Averages
    df['MA5']  = df['Close'].rolling(5).mean()
    df['MA10'] = df['Close'].rolling(10).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    
    # RSI (14-period)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_Mid'] = df['Close'].rolling(20).mean()
    df['BB_Upper'] = df['BB_Mid'] + 2 * df['Close'].rolling(20).std()
    df['BB_Lower'] = df['BB_Mid'] - 2 * df['Close'].rolling(20).std()
    
    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    
    # Other features
    df['Return'] = df['Close'].pct_change()
    df['Prev_Close'] = df['Close'].shift(1)
    
    if training:
        df['Target_Class'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        df['Target_Reg'] = df['Close'].shift(-1)
        df = df.dropna()
    else:
        # For prediction, we only drop rows where features are NaN (first 19 rows due to rolling 20)
        # but keep the last row
        feature_cols = ['Open', 'High', 'Low', 'Volume', 'MA5', 'MA10', 'MA20', 
                        'RSI', 'BB_Upper', 'BB_Lower', 'BB_Mid', 'MACD', 'Return', 'Prev_Close']
        df = df.dropna(subset=feature_cols)
        
    return df

def plot_evaluation_regression(y_actual, y_predicted, model_name, nama_saham):
    """Plot Actual vs Predicted Prices on Test Set"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.figure(figsize=(10, 5))
        sns.set_style("darkgrid")
        
        # Convert pandas series or list to numpy
        y_actual = np.array(y_actual)
        y_predicted = np.array(y_predicted)
        
        plt.plot(y_actual[-100:], label='Harga Aktual', color='blue', linewidth=2)
        plt.plot(y_predicted[-100:], label=f'Harga Prediksi ({model_name})', color='orange', linestyle='--', linewidth=2)
        
        plt.title(f'Evaluasi Model Regresi - {nama_saham} (100 Data Terakhir Test Set)', fontsize=14, fontweight='bold')
        plt.xlabel('Sampel Waktu', fontsize=12)
        plt.ylabel('Harga Saham (Rp)', fontsize=12)
        plt.legend(fontsize=11)
        plt.tight_layout()
        
        filename = f"output/eval_actual_vs_pred_{nama_saham}.png"
        plt.savefig(filename, dpi=300)
        plt.close()
        print(f"  🎨 Grafik evaluasi disimpan ke: {filename}")
    except Exception as e:
        print(f"  ⚠️ Gagal membuat grafik evaluasi: {e}")

# ============================================================================
# 3. TRAIN ML MODELS
# ============================================================================

def train_models(df, nama_saham='UNKNOWN'):
    """Train regression and classification models and evaluate their performance"""
    
    # Feature columns
    feature_cols = ['Open', 'High', 'Low', 'Volume', 'MA5', 'MA10', 'MA20', 
                    'RSI', 'BB_Upper', 'BB_Lower', 'BB_Mid', 'MACD', 'Return', 'Prev_Close']
    
    X = df[feature_cols].fillna(0)
    y_reg = df['Target_Reg']
    y_class = df['Target_Class']
    
    # Scale features
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split data (80/20, shuffle=False to preserve time series)
    n_split = int(len(X) * 0.8)
    X_train, X_test = X_scaled[:n_split], X_scaled[n_split:]
    y_train_reg, y_test_reg = y_reg.iloc[:n_split], y_reg.iloc[n_split:]
    y_train_class, y_test_class = y_class.iloc[:n_split], y_class.iloc[n_split:]
    
    # Train models
    models_reg = {
        'LinearRegression': LinearRegression(),
        'RandomForest': RandomForestRegressor(n_estimators=100, random_state=42, max_depth=15)
    }
    
    models_class = {
        'LogisticRegression': LogisticRegression(max_iter=1000),
        'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42, max_depth=15)
    }
    
    # Train, predict and calculate metrics
    trained_models_reg = {}
    trained_models_class = {}
    
    print(f"\n📊 Evaluasi Model untuk {nama_saham}:")
    
    # Regression metrics
    reg_comparison = []
    for name, model in models_reg.items():
        model.fit(X_train, y_train_reg)
        trained_models_reg[name] = model
        
        # Predict on test set
        y_pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test_reg, y_pred))
        mae = mean_absolute_error(y_test_reg, y_pred)
        r2 = r2_score(y_test_reg, y_pred)
        
        reg_comparison.append({
            'Model': name,
            'RMSE': round(rmse, 4),
            'MAE': round(mae, 4),
            'R2': round(r2, 4)
        })
        
        if name == 'LinearRegression':
            plot_evaluation_regression(y_test_reg, y_pred, name, nama_saham)
        
    df_reg = pd.DataFrame(reg_comparison)
    print("\n📈 Model Regresi (Prediksi Harga):")
    print(df_reg.to_string(index=False))
    
    # Save regression comparison
    df_reg.to_csv(f"output/eval_regression_{nama_saham}.csv", index=False)
    
    # Classification metrics
    class_comparison = []
    for name, model in models_class.items():
        model.fit(X_train, y_train_class)
        trained_models_class[name] = model
        
        # Predict on test set
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test_class, y_pred)
        prec = precision_score(y_test_class, y_pred, zero_division=0)
        rec = recall_score(y_test_class, y_pred, zero_division=0)
        f1 = f1_score(y_test_class, y_pred, zero_division=0)
        
        class_comparison.append({
            'Model': name,
            'Accuracy': f"{acc:.2%}",
            'Precision': f"{prec:.2%}",
            'Recall': f"{rec:.2%}",
            'F1-Score': f"{f1:.2%}"
        })
        
    df_class = pd.DataFrame(class_comparison)
    print("\n🎯 Model Klasifikasi (Prediksi Arah Tren):")
    print(df_class.to_string(index=False))
    print(f"✅ Hasil perbandingan model disimpan ke output/eval_*_{nama_saham}.csv\n")
    
    # Save classification comparison
    df_class.to_csv(f"output/eval_classification_{nama_saham}.csv", index=False)
    
    return trained_models_reg, trained_models_class, scaler, feature_cols

# ============================================================================
# 4. PREDICT 30 DAYS
# ============================================================================

def predict_30_days(harga_awal, df, models_reg, models_class, scaler, feature_cols, nama_saham='UNKNOWN', sentiment_data=None, days=30):
    """Predict next N days with optional sentiment adjustment"""
    
    # Get recent 30 days data for trend analysis
    recent_30 = df.tail(30)
    daily_change_pct = recent_30['Close'].pct_change().mean()
    
    # Process sentiment if available
    sentiment_trend = None
    sentiment_confidence = 0
    if sentiment_data:
        sentiment_trend, sentiment_confidence = sentiment_data
    
    predictions = []
    harga_current = harga_awal
    
    # We make a copy of df to append predictions recursively
    df_running = df.copy()
    
    for hari in range(1, days + 1):
        # 1. Get the feature values for the latest available date
        last_row = df_running.iloc[-1][feature_cols].fillna(0).values.reshape(1, -1)
        last_row_scaled = scaler.transform(last_row)
        
        # 2. Predict next day's price using ML regression models
        reg_preds = []
        for model in models_reg.values():
            reg_preds.append(model.predict(last_row_scaled)[0])
        ml_predicted_price = np.mean(reg_preds)
        
        # Blend ML regression price prediction with historical trend (random walk) for stability
        volatility = np.random.normal(0, 0.01)
        daily_change_trend = daily_change_pct + volatility
        trend_predicted_price = harga_current * (1 + daily_change_trend)
        
        # Blended price prediction (70% ML, 30% Trend)
        harga_next = 0.7 * ml_predicted_price + 0.3 * trend_predicted_price
        
        # Clamp price movement to max +/- 15% to prevent extreme values
        max_change = harga_current * 0.15
        harga_next = np.clip(harga_next, harga_current - max_change, harga_current + max_change)
        
        # 3. Get trend prediction and probability from ML classification models (using predict_proba)
        trend_probs = []
        for model in models_class.values():
            if hasattr(model, "predict_proba"):
                # predict_proba returns probability for [class 0, class 1]
                prob = model.predict_proba(last_row_scaled)[0][1]
            else:
                prob = model.predict(last_row_scaled)[0]
            trend_probs.append(prob)
        
        trend_prob = np.mean(trend_probs)
        tren_original = "NAIK ↑" if trend_prob > 0.5 else "TURUN ↓"
        confidence = abs(trend_prob - 0.5) * 2 * 100
        
        # Apply sentiment adjustment (only on first few days for strong impact)
        if sentiment_trend and hari <= 7 and sentiment_confidence > 0.3:
            if sentiment_trend == "NAIK ↑" and tren_original == "TURUN ↓":
                tren = sentiment_trend
                confidence = min(confidence + (sentiment_confidence * 20), 95)
            elif sentiment_trend == "TURUN ↓" and tren_original == "NAIK ↑":
                tren = sentiment_trend
                confidence = min(confidence + (sentiment_confidence * 20), 95)
            else:
                tren = tren_original
        else:
            tren = tren_original
        
        # Calculate changes compared to the initial price (harga_awal)
        perubahan_rp = harga_next - harga_awal
        perubahan_persen = (perubahan_rp / harga_awal) * 100
        
        # Store prediction
        tanggal = (datetime.now() + timedelta(days=hari)).strftime('%Y-%m-%d')
        predictions.append({
            'Saham': nama_saham,
            'Hari': hari,
            'Tanggal': tanggal,
            'Harga_Prediksi': round(harga_next, 2),
            'Perubahan_Rp': round(perubahan_rp, 2),
            'Perubahan_Persen': round(perubahan_persen, 2),
            'Tren': tren,
            'Confidence': round(confidence, 2)
        })
        
        # 4. Append the predicted row to our running DataFrame for multi-step recursive forecasting
        last_date = df_running.index[-1]
        next_date = last_date + timedelta(days=1)
        new_row = pd.DataFrame({
            'Open': [harga_current],
            'High': [max(harga_current, harga_next) * (1 + abs(np.random.normal(0, 0.005)))],
            'Low': [min(harga_current, harga_next) * (1 - abs(np.random.normal(0, 0.005)))],
            'Close': [harga_next],
            'Volume': [df_running['Volume'].tail(30).mean()]
        }, index=[next_date])
        
        df_running = pd.concat([df_running, new_row])
        # Recompute all technical features for the next day's forecast
        df_running = add_features(df_running, training=False)
        
        harga_current = harga_next
        
    return predictions

# ============================================================================
# 5. DISPLAY RESULTS
# ============================================================================

def display_predictions(all_predictions, df_bumi_hist, df_inet_hist, days_to_show=30):
    """Display predictions day by day and generate forecast plots"""
    
    df_pred = pd.DataFrame(all_predictions)
    
    print("\n" + "="*100)
    print("📊 PREDIKSI HARGA SAHAM 30 HARI")
    print("="*100)
    
    for saham in ['BUMI', 'INET']:
        df_saham = df_pred[df_pred['Saham'] == saham].head(days_to_show)
        
        print(f"\n📈 {saham} - Prediksi 30 Hari ke Depan")
        print("-"*100)
        print(f"{'Hari':<5} {'Tanggal':<12} {'Harga':<12} {'Perubahan':<15} {'Trend':<12} {'Confidence':<12}")
        print("-"*100)
        
        for idx, row in df_saham.iterrows():
            harga = f"Rp {row['Harga_Prediksi']:.2f}".ljust(12)
            perubahan = f"{row['Perubahan_Rp']:+.2f} ({row['Perubahan_Persen']:+.2f}%)".ljust(15)
            trend = row['Tren'].ljust(12)
            conf = f"{row['Confidence']:.1f}%".ljust(12)
            
            print(f"{row['Hari']:<5} {row['Tanggal']:<12} {harga} {perubahan} {trend} {conf}")
        
        print()
        
        # Plot forecast visualization
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            plt.figure(figsize=(12, 6))
            sns.set_style("darkgrid")
            
            # Historical data
            hist_df = df_bumi_hist if saham == 'BUMI' else df_inet_hist
            # Take last 60 days of historical close
            hist_close = hist_df['Close'].tail(60)
            
            # Forecast dates and prices
            pred_dates = pd.to_datetime(df_saham['Tanggal'])
            pred_prices = df_saham['Harga_Prediksi']
            
            # Plot history
            plt.plot(hist_close.index, hist_close.values, label='Harga Historis (60 Hari Terakhir)', color='blue', linewidth=2)
            
            # Draw prediction line starting from the last historical point
            last_date = hist_close.index[-1]
            last_price = hist_close.values[-1]
            
            full_dates = [last_date] + list(pred_dates)
            full_prices = [last_price] + list(pred_prices)
            
            plt.plot(full_dates, full_prices, label='Proyeksi Prediksi (30 Hari Ke Depan)', color='red', linestyle='--', linewidth=2.5)
            plt.scatter(pred_dates, pred_prices, color='red', s=30, zorder=5)
            
            plt.title(f'Proyeksi Prediksi Harga Saham {saham} - 30 Hari Ke Depan', fontsize=14, fontweight='bold')
            plt.xlabel('Tanggal', fontsize=12)
            plt.ylabel('Harga Saham (Rp)', fontsize=12)
            plt.legend(fontsize=11)
            plt.xticks(rotation=15)
            plt.tight_layout()
            
            filename = f"output/visualisasi_prediksi_30_hari_{saham}.png"
            plt.savefig(filename, dpi=300)
            plt.close()
            print(f"  🎨 Grafik visualisasi prediksi {saham} disimpan ke: {filename}")
        except Exception as e:
            print(f"  ⚠️ Gagal membuat grafik prediksi {saham}: {e}")
            
    # Save results
    df_pred.to_csv('output/prediksi_30_hari.csv', index=False)
    print(f"✅ Hasil disimpan ke: output/prediksi_30_hari.csv")

# ============================================================================
# 6. MAIN PROGRAM
# ============================================================================

def main():
    """Main program"""
    
    # Parse arguments
    harga_bumi = None
    harga_inet = None
    fetch_only = False
    days_to_show = 30
    use_sentiment = False
    
    # Extract options and positional arguments
    args = sys.argv[1:]
    
    # 1. Parse --fetch
    if '--fetch' in args:
        fetch_only = True
        args.remove('--fetch')
        
    # 2. Parse --sentiment    
    if '--sentiment' in args:
        use_sentiment = True
        args.remove('--sentiment')
        
    # 3. Parse --hari <N>
    if '--hari' in args:
        try:
            idx = args.index('--hari')
            if idx + 1 < len(args):
                days_to_show = int(args[idx + 1])
                args.pop(idx + 1)
                args.pop(idx)
            else:
                args.pop(idx)
        except (ValueError, IndexError):
            pass
            
    # 4. Remaining arguments are positional custom stock prices
    if len(args) > 0:
        try:
            harga_bumi = float(args[0])
        except ValueError:
            pass
    if len(args) > 1:
        try:
            harga_inet = float(args[1])
        except ValueError:
            pass
    
    print("\n" + "="*100)
    print("🚀 SISTEM PREDIKSI SAHAM BUMI & INET - REAL DATA YFINANCE")
    print("="*100)
    
    # Fetch latest data
    fetch_data_from_yfinance()
    
    if fetch_only:
        print("\n✅ Data berhasil diperbarui!")
        return
    
    # Load data
    try:
        df_bumi = pd.read_csv('BUMI_stock.csv')
        df_inet = pd.read_csv('INET_stock.csv')
        
        # Convert numeric columns
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            if col in df_bumi.columns:
                df_bumi[col] = pd.to_numeric(df_bumi[col], errors='coerce')
            if col in df_inet.columns:
                df_inet[col] = pd.to_numeric(df_inet[col], errors='coerce')
        
        # Handle date column
        if 'Date' in df_bumi.columns:
            df_bumi['Date'] = pd.to_datetime(df_bumi['Date'])
            df_bumi.set_index('Date', inplace=True)
        elif df_bumi.index.name is None:
            df_bumi.index = pd.to_datetime(df_bumi.index)
            
        if 'Date' in df_inet.columns:
            df_inet['Date'] = pd.to_datetime(df_inet['Date'])
            df_inet.set_index('Date', inplace=True)
        elif df_inet.index.name is None:
            df_inet.index = pd.to_datetime(df_inet.index)
    except FileNotFoundError:
        print("❌ File data tidak ditemukan. Jalankan: python prediksi.py --fetch")
        return
    
    # Get latest prices if not provided
    if harga_bumi is None:
        harga_bumi = float(df_bumi['Close'].iloc[-1])
        print(f"\n📍 BUMI harga sekarang: Rp {harga_bumi:.2f}")
    else:
        harga_bumi = float(harga_bumi)
        print(f"\n📍 BUMI harga: Rp {harga_bumi:.2f}")
    
    if harga_inet is None:
        harga_inet = float(df_inet['Close'].iloc[-1])
        print(f"📍 INET harga sekarang: Rp {harga_inet:.2f}")
    else:
        harga_inet = float(harga_inet)
        print(f"📍 INET harga: Rp {harga_inet:.2f}")
    
    # Add features for training and prediction
    print("\n⚙️  Processing data...")
    df_bumi_train = add_features(df_bumi, training=True)
    df_inet_train = add_features(df_inet, training=True)
    
    df_bumi_pred = add_features(df_bumi, training=False)
    df_inet_pred = add_features(df_inet, training=False)
    
    # Train models
    print("🧠 Training ML models...")
    models_reg_bumi, models_class_bumi, scaler_bumi, features = train_models(df_bumi_train, 'BUMI')
    models_reg_inet, models_class_inet, scaler_inet, _ = train_models(df_inet_train, 'INET')
    
    # Get sentiment if requested
    sentiment_bumi = None
    sentiment_inet = None
    if use_sentiment and SENTIMENT_AVAILABLE:
        print("\n📰 Analyzing news sentiment...")
        news_api = RealNewsAPI()
        analyzer = RealSentimentAnalyzer()
        confidence_calc = RealConfidenceCalculator()
        store = NewsDataStore()
        
        # Analyze BUMI
        print("  Analyzing BUMI news...", end='', flush=True)
        keywords_bumi = SEARCH_KEYWORDS.get('BUMI', ['BUMI'])
        articles_bumi = []
        for kw in keywords_bumi:
            articles_bumi.extend(news_api.fetch_everything(kw, limit=15))
        if articles_bumi:
            res_bumi = analyzer.aggregate_articles(articles_bumi)
            conf_bumi = confidence_calc.calculate_trend_confidence(res_bumi)
            # Save BUMI news & sentiment to database
            store.save_articles(articles_bumi)
            store.save_sentiment('BUMI', res_bumi, conf_bumi)
            if res_bumi['sentiment'] in ['STRONG_POSITIVE', 'POSITIVE']:
                trend_bumi = "NAIK ↑"
            elif res_bumi['sentiment'] in ['STRONG_NEGATIVE', 'NEGATIVE']:
                trend_bumi = "TURUN ↓"
            else:
                trend_bumi = None
            sentiment_bumi = (trend_bumi, conf_bumi) if trend_bumi else None
            print(f" ✅ Done (Sentiment: {res_bumi['sentiment']}, Confidence: {conf_bumi:.1%})")
        else:
            print(" ⚠️  No articles found")
            
        # Analyze INET
        print("  Analyzing INET news...", end='', flush=True)
        keywords_inet = SEARCH_KEYWORDS.get('INET', ['INET'])
        articles_inet = []
        for kw in keywords_inet:
            articles_inet.extend(news_api.fetch_everything(kw, limit=15))
        if articles_inet:
            res_inet = analyzer.aggregate_articles(articles_inet)
            conf_inet = confidence_calc.calculate_trend_confidence(res_inet)
            # Save INET news & sentiment to database
            store.save_articles(articles_inet)
            store.save_sentiment('INET', res_inet, conf_inet)
            if res_inet['sentiment'] in ['STRONG_POSITIVE', 'POSITIVE']:
                trend_inet = "NAIK ↑"
            elif res_inet['sentiment'] in ['STRONG_NEGATIVE', 'NEGATIVE']:
                trend_inet = "TURUN ↓"
            else:
                trend_inet = None
            sentiment_inet = (trend_inet, conf_inet) if trend_inet else None
            print(f" ✅ Done (Sentiment: {res_inet['sentiment']}, Confidence: {conf_inet:.1%})")
        else:
            print(" ⚠️  No articles found")
    
    # Predict
    print(f"\n🔮 Generating predictions for {days_to_show} days...")
    pred_bumi = predict_30_days(harga_bumi, df_bumi_pred, models_reg_bumi, models_class_bumi, 
                                 scaler_bumi, features, 'BUMI', sentiment_bumi, days=days_to_show)
    pred_inet = predict_30_days(harga_inet, df_inet_pred, models_reg_inet, models_class_inet, 
                                 scaler_inet, features, 'INET', sentiment_inet, days=days_to_show)
    
    all_predictions = pred_bumi + pred_inet
    
    # Display
    display_predictions(all_predictions, df_bumi_pred, df_inet_pred, days_to_show)
    
    print("\n" + "="*100)
    print("✅ SELESAI! Gunakan perintah:")
    print("   • python prediksi.py 152 181          # Prediksi dengan harga custom")
    print("   • python prediksi.py --hari 5         # Tampilkan hanya 5 hari")
    print("   • python prediksi.py --sentiment      # Predict dengan real-time news sentiment")
    print("   • python prediksi.py --fetch          # Update data saja")
    print("="*100 + "\n")

if __name__ == '__main__':
    main()
