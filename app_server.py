#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lightweight Backend Server for BUMI & INET Stock Prediction System
Hosts static web dashboard and REST API endpoints.
Zero external dependencies.
"""

import os
import json
import csv
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get('PORT', 8000))
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, 'output')

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def read_csv_to_json(filepath):
    """Safely reads CSV file and converts it to list of dicts"""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"Error reading CSV {filepath}: {e}")
        return []

def load_historical_data(filepath, limit=150):
    """Custom parser for yfinance CSVs (handling multi-index headers)"""
    if not os.path.exists(filepath):
        return []
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            parts = line.strip().split(',')
            if not parts or len(parts) < 6:
                continue
            date_str = parts[0]
            # Match date format YYYY-MM-DD
            if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
                try:
                    data.append({
                        'Date': date_str,
                        'Close': round(float(parts[1]), 2),
                        'High': round(float(parts[2]), 2),
                        'Low': round(float(parts[3]), 2),
                        'Open': round(float(parts[4]), 2),
                        'Volume': int(float(parts[5])) if parts[5] else 0
                    })
                except ValueError:
                    pass
        # Return the last N items
        return data[-limit:]
    except Exception as e:
        print(f"Error parsing historical CSV {filepath}: {e}")
        return []

class StockDashboardHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to prevent clogging the console with standard GET requests
        pass

    def send_json(self, data, status=200):
        try:
            response_bytes = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)
        except Exception as e:
            print(f"Error sending JSON: {e}")

    def send_static_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        try:
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Static routing
        if path == '/' or path == '/index.html':
            self.send_static_file(os.path.join(WORKSPACE_DIR, 'public', 'index.html'), 'text/html; charset=utf-8')
        elif path == '/index.css':
            self.send_static_file(os.path.join(WORKSPACE_DIR, 'public', 'index.css'), 'text/css; charset=utf-8')
        elif path == '/app.js':
            self.send_static_file(os.path.join(WORKSPACE_DIR, 'public', 'app.js'), 'application/javascript; charset=utf-8')
        
        # Serve static images from output directory
        elif path.startswith('/output/'):
            filename = os.path.basename(path)
            content_type = 'image/png' if filename.endswith('.png') else 'text/plain'
            self.send_static_file(os.path.join(OUTPUT_DIR, filename), content_type)

        # API Endpoints
        elif path == '/api/stock_info':
            # Get latest price and date for BUMI & INET
            bumi_hist = load_historical_data(os.path.join(WORKSPACE_DIR, 'BUMI_stock.csv'), limit=1)
            inet_hist = load_historical_data(os.path.join(WORKSPACE_DIR, 'INET_stock.csv'), limit=1)
            
            info = {
                'BUMI': {
                    'symbol': 'BUMI.JK',
                    'current_price': bumi_hist[0]['Close'] if bumi_hist else None,
                    'date': bumi_hist[0]['Date'] if bumi_hist else None
                },
                'INET': {
                    'symbol': 'INET.JK',
                    'current_price': inet_hist[0]['Close'] if inet_hist else None,
                    'date': inet_hist[0]['Date'] if inet_hist else None
                }
            }
            self.send_json(info)

        elif path == '/api/historical':
            symbol = query_params.get('symbol', ['BUMI'])[0]
            filename = f"{symbol}_stock.csv"
            filepath = os.path.join(WORKSPACE_DIR, filename)
            limit = int(query_params.get('limit', [150])[0])
            self.send_json(load_historical_data(filepath, limit))

        elif path == '/api/predictions':
            filepath = os.path.join(OUTPUT_DIR, 'prediksi_30_hari.csv')
            self.send_json(read_csv_to_json(filepath))

        elif path == '/api/sentiment':
            filepath = os.path.join(OUTPUT_DIR, 'sentiment_history.csv')
            history = read_csv_to_json(filepath)
            
            # Aggregate latest record for each stock
            latest_sentiment = {}
            for item in reversed(history):
                stock = item.get('stock')
                if stock not in latest_sentiment:
                    latest_sentiment[stock] = item
                if len(latest_sentiment) >= 2:
                    break
            self.send_json(latest_sentiment)

        elif path == '/api/news':
            filepath = os.path.join(OUTPUT_DIR, 'news_database.csv')
            news = read_csv_to_json(filepath)
            
            # Sort news by timestamp descending (assuming ISO format strings)
            # If timestamp field exists, sort by it
            try:
                news.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            except:
                pass
            
            # Optionally filter by symbol
            symbol = query_params.get('symbol', [None])[0]
            if symbol:
                filtered_news = []
                # Simple keyword matching for filtering news
                keywords = [symbol.lower()]
                if symbol.upper() == 'BUMI':
                    keywords.extend(['resources', 'coal', 'mineral'])
                elif symbol.upper() == 'INET':
                    keywords.extend(['energy', 'indonesia energy'])
                
                for item in news:
                    text_to_search = (item.get('title', '') + ' ' + item.get('description', '')).lower()
                    if any(kw in text_to_search for kw in keywords):
                        filtered_news.append(item)
                self.send_json(filtered_news[:30]) # limit to 30 articles
            else:
                self.send_json(news[:40])

        elif path == '/api/evaluation':
            eval_data = {}
            for stock in ['BUMI', 'INET']:
                eval_data[stock] = {
                    'regression': read_csv_to_json(os.path.join(OUTPUT_DIR, f'eval_regression_{stock}.csv')),
                    'classification': read_csv_to_json(os.path.join(OUTPUT_DIR, f'eval_classification_{stock}.csv'))
                }
            self.send_json(eval_data)
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        
        params = {}
        if post_data:
            try:
                params = json.loads(post_data)
            except json.JSONDecodeError:
                # Handle form data if JSON decoding fails
                params = urllib.parse.parse_qs(post_data)
                params = {k: v[0] for k, v in params.items()}

        if path == '/api/run_prediction':
            # Trigger prediction process
            harga_bumi = params.get('harga_bumi')
            harga_inet = params.get('harga_inet')
            sentiment = params.get('sentiment', True)
            days = params.get('days', 30)

            # Construct commands
            cmd = [sys.executable, 'prediksi.py']
            
            # If custom prices are provided, add them as positional args
            if harga_bumi is not None and harga_inet is not None:
                cmd.append(str(harga_bumi))
                cmd.append(str(harga_inet))
            
            if sentiment:
                cmd.append('--sentiment')
            
            cmd.extend(['--hari', str(days)])
            
            try:
                print(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=WORKSPACE_DIR, encoding='utf-8')
                
                success = result.returncode == 0
                self.send_json({
                    'success': success,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'code': result.returncode
                })
            except Exception as e:
                self.send_json({
                    'success': False,
                    'stderr': f"Execution error: {e}",
                    'stdout': "",
                    'code': -1
                })

        elif path == '/api/run_news_fetch':
            # Trigger news fetching process
            cmd = [sys.executable, 'news_sentiment_v2.py']
            
            try:
                print(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=WORKSPACE_DIR, encoding='utf-8')
                
                success = result.returncode == 0
                self.send_json({
                    'success': success,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'code': result.returncode
                })
            except Exception as e:
                self.send_json({
                    'success': False,
                    'stderr': f"Execution error: {e}",
                    'stdout': "",
                    'code': -1
                })
        else:
            self.send_error(404, "Page Not Found")

def run(server_class=HTTPServer, handler_class=StockDashboardHandler, port=PORT):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Stock Prediction Dashboard Server running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()

if __name__ == '__main__':
    run()
