// State Management
const state = {
  activeStock: 'BUMI',
  stockInfo: {},
  historicalData: { BUMI: [], INET: [] },
  predictions: [],
  sentiment: {},
  news: { BUMI: [], INET: [] },
  evaluation: {},
  chartInstance: null,
  chartView: 'price' // Default view (price vs volume)
};

// Colors mapping
const colors = {
  BUMI: 'rgb(234, 179, 8)', // Gold
  INET: 'rgb(6, 182, 212)', // Cyan
  UP: 'rgb(16, 185, 129)',  // Green
  DOWN: 'rgb(239, 68, 68)'  // Red
};

// Logger Helper
function logConsole(message, isError = false) {
  const consoleEl = document.getElementById('logConsole');
  const logTimeEl = document.getElementById('logTime');
  const timestamp = new Date().toLocaleTimeString();
  
  logTimeEl.textContent = timestamp;
  
  const span = document.createElement('span');
  span.style.color = isError ? 'var(--color-down)' : '#a7f3d0';
  span.textContent = `[${timestamp}] ${message}\n`;
  consoleEl.appendChild(span);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

// Fetch Initial Info from Backend
async function fetchAllData() {
  try {
    logConsole('Fetching info from backend APIs...');
    
    // 1. Fetch stock info
    const infoRes = await fetch('/api/stock_info');
    state.stockInfo = await infoRes.json();
    
    // Set live prices display in Control Panel
    if (state.stockInfo.BUMI && state.stockInfo.BUMI.current_price) {
      document.getElementById('livePriceBumi').textContent = `Rp ${state.stockInfo.BUMI.current_price.toFixed(2)}`;
    }
    if (state.stockInfo.INET && state.stockInfo.INET.current_price) {
      document.getElementById('livePriceInet').textContent = `Rp ${state.stockInfo.INET.current_price.toFixed(2)}`;
    }

    // 2. Fetch historical data for both stocks
    const bumiHistRes = await fetch('/api/historical?symbol=BUMI');
    state.historicalData.BUMI = await bumiHistRes.json();
    
    const inetHistRes = await fetch('/api/historical?symbol=INET');
    state.historicalData.INET = await inetHistRes.json();

    // 3. Fetch predictions
    const predRes = await fetch('/api/predictions');
    const rawPreds = await predRes.json();
    state.predictions = rawPreds.map(item => ({
      ...item,
      Hari: parseInt(item.Hari) || 0,
      Harga_Prediksi: parseFloat(item.Harga_Prediksi) || 0,
      Perubahan_Rp: parseFloat(item.Perubahan_Rp) || 0,
      Perubahan_Persen: parseFloat(item.Perubahan_Persen) || 0,
      Confidence: parseFloat(item.Confidence) || 0
    }));

    // 4. Fetch sentiment records
    const sentRes = await fetch('/api/sentiment');
    state.sentiment = await sentRes.json();

    // 5. Fetch news for both
    const bumiNewsRes = await fetch('/api/news?symbol=BUMI');
    state.news.BUMI = await bumiNewsRes.json();
    
    const inetNewsRes = await fetch('/api/news?symbol=INET');
    state.news.INET = await inetNewsRes.json();

    // 6. Fetch evaluation metrics
    const evalRes = await fetch('/api/evaluation');
    state.evaluation = await evalRes.json();

    logConsole('API data successfully loaded.');
    updateUI();
  } catch (error) {
    logConsole(`Error loading dashboard data: ${error.message}`, true);
    console.error(error);
  }
}

// Render sparkline for stock card
function renderSparkline(canvasId, history, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  const last15 = history.slice(-15);
  const prices = last15.map(h => h.Close);
  if (prices.length === 0) return;
  
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }
  
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: prices.map((_, i) => i),
      datasets: [{
        data: prices,
        borderColor: color,
        borderWidth: 2,
        fill: false,
        pointRadius: 0,
        pointHoverRadius: 0,
        tension: 0.3
      }]
    },
    options: {
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      responsive: true,
      maintainAspectRatio: false
    }
  });
}

// Render stock cards
function updateStockCards() {
  ['BUMI', 'INET'].forEach(symbol => {
    const info = state.stockInfo[symbol] || {};
    const preds = state.predictions.filter(p => p.Saham === symbol);
    const sent = state.sentiment[symbol] || {};
    
    const cardPriceCurrent = document.getElementById(`${symbol.toLowerCase()}PriceCurrent`);
    const cardPriceChange = document.getElementById(`${symbol.toLowerCase()}PriceChange`);
    const cardPriceTarget = document.getElementById(`${symbol.toLowerCase()}PriceTarget`);
    const cardTrendBadge = document.getElementById(`${symbol.toLowerCase()}TrendBadge`);
    const cardConfidence = document.getElementById(`${symbol.toLowerCase()}Confidence`);
    const cardSentimentVal = document.getElementById(`${symbol.toLowerCase()}SentimentVal`);

    // Set current price
    const currentPrice = info.current_price || (state.historicalData[symbol].length ? state.historicalData[symbol][state.historicalData[symbol].length - 1].Close : 0);
    cardPriceCurrent.textContent = `Rp ${currentPrice.toFixed(2)}`;

    if (preds.length > 0) {
      const targetDay = preds[preds.length - 1]; // Latest prediction day projection
      const changeRp = targetDay.Harga_Prediksi - currentPrice;
      const changePercent = (changeRp / currentPrice) * 100;
      
      // Update labels
      const targetLabel = cardPriceTarget.previousElementSibling;
      if (targetLabel) {
        targetLabel.textContent = `Target ${preds.length} Hari`;
      }
      
      // Update values
      cardPriceTarget.textContent = `Rp ${targetDay.Harga_Prediksi.toFixed(2)}`;
      cardConfidence.textContent = `${targetDay.Confidence.toFixed(1)}%`;
      
      // Trend Badge
      const overallTrend = targetDay.Harga_Prediksi >= currentPrice ? 'NAIK ↑' : 'TURUN ↓';
      cardTrendBadge.textContent = overallTrend;
      
      if (overallTrend.includes('NAIK')) {
        cardTrendBadge.className = 'trend-badge up';
        cardPriceChange.className = 'price-change up';
        cardPriceChange.textContent = `+${changeRp.toFixed(2)} (+${changePercent.toFixed(2)}%)`;
      } else {
        cardTrendBadge.className = 'trend-badge down';
        cardPriceChange.className = 'price-change down';
        cardPriceChange.textContent = `${changeRp.toFixed(2)} (${changePercent.toFixed(2)}%)`;
      }
    }

    // Sentiment Summary
    if (sent.sentiment) {
      cardSentimentVal.textContent = sent.sentiment;
      if (sent.sentiment.includes('POSITIVE')) {
        cardSentimentVal.style.color = colors.UP;
      } else if (sent.sentiment.includes('NEGATIVE')) {
        cardSentimentVal.style.color = colors.DOWN;
      } else {
        cardSentimentVal.style.color = 'var(--text-muted)';
      }
    } else {
      cardSentimentVal.textContent = 'NEUTRAL';
      cardSentimentVal.style.color = 'var(--text-muted)';
    }

    // Render mini sparkline
    renderSparkline(`${symbol.toLowerCase()}Sparkline`, state.historicalData[symbol], colors[symbol]);
  });
}

// Render Chart
function updateChart() {
  const symbol = state.activeStock;
  const history = state.historicalData[symbol];
  const allPreds = state.predictions.filter(p => p.Saham === symbol);

  // Read user-chosen horizon from paramDays input (default 30)
  const daysInput = document.getElementById('paramDays');
  const selectedDays = Math.min(
    daysInput ? Math.min(Math.max(parseInt(daysInput.value) || 30, 1), 30) : 30,
    allPreds.length > 0 ? allPreds.length : 30
  );
  const preds = allPreds.slice(0, selectedDays);

  // Update chart panel title
  const chartTitleEl = document.querySelector('.chart-panel .panel-title');
  if (chartTitleEl) {
    chartTitleEl.innerHTML = `<span>📈</span> Proyeksi Harga & Prediksi ${selectedDays} Hari ke Depan`;
  }

  if (!history || history.length === 0) {
    logConsole(`No historical data to draw chart for ${symbol}`, true);
    return;
  }

  // Destroy old instance if exists
  if (state.chartInstance) {
    state.chartInstance.destroy();
  }

  const ctx = document.getElementById('stockChart').getContext('2d');
  const activeColor = colors[symbol];
  const labels = [];

  if (state.chartView === 'price') {
    const histDataset = [];
    const predDataset = [];

    // Historical Close Prices — show enough context (2× selected days, min 30)
    const histWindow = Math.max(selectedDays * 2, 30);
    const lastN = history.slice(-histWindow);
    lastN.forEach(item => {
      labels.push(item.Date);
      histDataset.push(item.Close);
      predDataset.push(null);
    });

    // Predictions sliced to selectedDays
    if (preds.length > 0) {
      const lastHistPrice = histDataset[histDataset.length - 1];
      predDataset[predDataset.length - 1] = lastHistPrice;

      preds.forEach(item => {
        labels.push(item.Tanggal);
        histDataset.push(null);
        predDataset.push(item.Harga_Prediksi);
      });
    }

    state.chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: `Harga Historis ${symbol}`,
            data: histDataset,
            borderColor: activeColor,
            backgroundColor: activeColor.replace('rgb', 'rgba').replace(')', ', 0.1)'),
            borderWidth: 2.5,
            tension: 0.1,
            pointRadius: 1,
            pointHoverRadius: 5,
            fill: true
          },
          {
            label: `Prediksi AI ${selectedDays} Hari`,
            data: predDataset,
            borderColor: colors.DOWN,
            borderDash: [6, 4],
            borderWidth: 3,
            tension: 0.1,
            pointRadius: 2,
            pointHoverRadius: 6,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: 'rgba(255, 255, 255, 0.6)', font: { family: 'Inter' }, maxTicksLimit: 12 }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: 'rgba(255, 255, 255, 0.6)', font: { family: 'Inter' } }
          }
        },
        plugins: {
          legend: { labels: { color: 'rgba(255, 255, 255, 0.8)', font: { family: 'Outfit', weight: 'bold' } } },
          tooltip: {
            mode: 'index',
            intersect: false,
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Outfit', size: 14, weight: 'bold' },
            bodyFont: { family: 'Inter', size: 12 },
            callbacks: {
              label: function(context) {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                if (context.parsed.y !== null) {
                  label += new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(context.parsed.y);
                }
                return label;
              }
            }
          }
        }
      }
    });
  } else {
    // Volume view
    const volDataset = [];
    const lastN = history.slice(-60);
    lastN.forEach(item => {
      labels.push(item.Date);
      volDataset.push(item.Volume);
    });

    state.chartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: `Volume Transaksi ${symbol}`,
            data: volDataset,
            backgroundColor: activeColor.replace('rgb', 'rgba').replace(')', ', 0.3)'),
            borderColor: activeColor,
            borderWidth: 1.5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: { color: 'rgba(255, 255, 255, 0.6)', font: { family: 'Inter' }, maxTicksLimit: 12 }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.05)' },
            ticks: {
              color: 'rgba(255, 255, 255, 0.6)',
              font: { family: 'Inter' },
              callback: function(value) {
                return (value / 1e6).toFixed(1) + 'M';
              }
            }
          }
        },
        plugins: {
          legend: { labels: { color: 'rgba(255, 255, 255, 0.8)', font: { family: 'Outfit', weight: 'bold' } } },
          tooltip: {
            mode: 'index',
            intersect: false,
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            titleFont: { family: 'Outfit', size: 14, weight: 'bold' },
            bodyFont: { family: 'Inter', size: 12 },
            callbacks: {
              label: function(context) {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                if (context.parsed.y !== null) {
                  label += new Intl.NumberFormat('id-ID').format(context.parsed.y) + ' Lembar';
                }
                return label;
              }
            }
          }
        }
      }
    });
  }
}

// Render Sentiment Gauges
function updateSentimentPanel() {
  const symbol = state.activeStock;
  const sent = state.sentiment[symbol] || { sentiment: 'NEUTRAL', score: '0.00', confidence: '0.0', total_articles: '0' };
  const articles = state.news[symbol] || [];
  
  const polarityScoreEl = document.getElementById('sentimentPolarityScore');
  const classLabelEl = document.getElementById('sentimentClassLabel');
  
  // Set polarity and class label
  const polarityVal = parseFloat(sent.score || 0);
  polarityScoreEl.textContent = polarityVal.toFixed(3);
  classLabelEl.textContent = sent.sentiment || 'NEUTRAL';
  
  // Update class colors
  if (sent.sentiment.includes('POSITIVE')) {
    classLabelEl.style.color = colors.UP;
    polarityScoreEl.style.color = colors.UP;
  } else if (sent.sentiment.includes('NEGATIVE')) {
    classLabelEl.style.color = colors.DOWN;
    polarityScoreEl.style.color = colors.DOWN;
  } else {
    classLabelEl.style.color = 'var(--text-muted)';
    polarityScoreEl.style.color = 'var(--text-primary)';
  }

  // Count sentiments of articles for local breakdown
  let strongPos = 0, pos = 0, neutral = 0, neg = 0, strongNeg = 0;
  
  articles.forEach(article => {
    const text = (article.title + ' ' + article.description).toLowerCase();
    const polarity = parseFloat(article.polarity || 0.0);
    
    if (polarity > 0.6) strongPos++;
    else if (polarity > 0.1) pos++;
    else if (polarity < -0.6) strongNeg++;
    else if (polarity < -0.1) neg++;
    else neutral++;
  });
  
  const total = articles.length || 1;
  
  // Update counts on UI
  document.getElementById('cntStrongPos').textContent = strongPos;
  document.getElementById('cntPos').textContent = pos;
  document.getElementById('cntNeutral').textContent = neutral;
  document.getElementById('cntNeg').textContent = neg;
  document.getElementById('cntStrongNeg').textContent = strongNeg;
  
  // Update progress bars
  document.getElementById('pbStrongPos').style.width = `${(strongPos / total) * 100}%`;
  document.getElementById('pbPos').style.width = `${(pos / total) * 100}%`;
  document.getElementById('pbNeutral').style.width = `${(neutral / total) * 100}%`;
  document.getElementById('pbNeg').style.width = `${(neg / total) * 100}%`;
  document.getElementById('pbStrongNeg').style.width = `${(strongNeg / total) * 100}%`;
}

// Render News Feed (both BUMI and INET columns always)
function updateNewsFeed() {
  ['BUMI', 'INET'].forEach(sym => {
    const articles = state.news[sym] || [];
    const containerId = sym === 'BUMI' ? 'newsFeedBumi' : 'newsFeedInet';
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = '';

    if (articles.length === 0) {
      container.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 20px;">Tidak ada berita untuk ${sym}.</p>`;
      return;
    }

    articles.slice(0, 15).forEach(article => {
      const card = document.createElement('div');
      card.className = 'news-card';

      const dateStr = article.timestamp ? new Date(article.timestamp).toLocaleString('id-ID') : 'Baru-baru ini';
      const polarity = parseFloat(article.polarity || 0.0);

      let sentBadge = 'NEUTRAL';
      let sentColor = 'var(--text-muted)';

      if (polarity > 0.6)       { sentBadge = 'STRONG POS'; sentColor = colors.UP; }
      else if (polarity > 0.1)  { sentBadge = 'POSITIF';    sentColor = '#34d399'; }
      else if (polarity < -0.6) { sentBadge = 'STRONG NEG'; sentColor = colors.DOWN; }
      else if (polarity < -0.1) { sentBadge = 'NEGATIF';    sentColor = '#f87171'; }

      card.innerHTML = `
        <div class="news-card-header">
          <span class="news-source">${article.source || 'NewsAPI'}</span>
          <span>${dateStr}</span>
        </div>
        <h4 class="news-card-title">
          <a href="${article.url}" target="_blank" rel="noopener noreferrer">${article.title}</a>
        </h4>
        <p class="news-card-desc">${article.description || 'Tidak ada deskripsi.'}</p>
        <div class="news-card-footer">
          <span style="font-size: 0.7rem; color: var(--text-muted);">Polarity: ${polarity.toFixed(2)}</span>
          <span style="font-size: 0.75rem; font-weight: 700; color: ${sentColor}">${sentBadge}</span>
        </div>
      `;

      container.appendChild(card);
    });
  });
}

// Render Model Metrics Table (panel removed from UI — kept as no-op guard)
function updateEvaluationTable() {
  const tbody = document.getElementById('evaluationTableBody');
  if (!tbody) return; // evaluation panel has been removed from the UI
  tbody.innerHTML = '';

  if (!state.evaluation || Object.keys(state.evaluation).length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No evaluation metrics loaded.</td></tr>';
    return;
  }
  
  for (const [stock, info] of Object.entries(state.evaluation)) {
    // Regression models rows
    info.regression.forEach((reg, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        ${idx === 0 ? `<td rowspan="${info.regression.length + info.classification.length}" style="vertical-align: middle; font-weight: bold; font-family: var(--font-display);">${stock}</td>` : ''}
        ${idx === 0 ? `<td rowspan="${info.regression.length}" style="vertical-align: middle; color: var(--text-secondary);">Regresi (Prediksi Harga)</td>` : ''}
        <td class="model-name">${reg.Model}</td>
        <td>RMSE: <strong>${reg.RMSE}</strong> | MAE: <strong>${reg.MAE}</strong> | R²: <strong>${reg.R2}</strong></td>
      `;
      tbody.appendChild(tr);
    });

    // Classification models rows
    info.classification.forEach((cls, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        ${idx === 0 ? `<td rowspan="${info.classification.length}" style="vertical-align: middle; color: var(--text-secondary);">Klasifikasi (Prediksi Tren Arah)</td>` : ''}
        <td class="model-name">${cls.Model}</td>
        <td>Akurasi: <strong>${cls.Accuracy}</strong> | Presisi: <strong>${cls.Precision}</strong> | Recall: <strong>${cls.Recall}</strong> | F1: <strong>${cls.F1Score || cls['F1-Score'] || 'N/A'}</strong></td>
      `;
      tbody.appendChild(tr);
    });
  }
}

// Calculate Technical Indicators from history
function calculateTechnicalIndicators(history) {
  if (!history || history.length < 30) {
    return {
      rsi: '50.0', rsiSignal: 'NEUTRAL',
      ma5: '0.0', ma20: '0.0', maSignal: 'NEUTRAL',
      bbUpper: '0.0', bbLower: '0.0', bbSignal: 'NEUTRAL',
      macd: '0.000', macdSignal: 'NEUTRAL',
      overall: 'NEUTRAL'
    };
  }

  const prices = history.map(h => h.Close);
  const len = prices.length;
  const currentPrice = prices[len - 1];

  // 1. MA5 vs MA20 Crossover
  const ma5 = prices.slice(-5).reduce((a, b) => a + b, 0) / 5;
  const ma20 = prices.slice(-20).reduce((a, b) => a + b, 0) / 20;
  const maSignal = ma5 > ma20 ? 'GOLDEN CROSS (BULLISH)' : 'DEATH CROSS (BEARISH)';

  // 2. RSI (14-period)
  let gains = 0;
  let losses = 0;
  for (let i = len - 14; i < len; i++) {
    const diff = prices[i] - prices[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }
  const rs = gains / (losses || 1e-9);
  const rsi = 100 - (100 / (1 + rs));
  let rsiSignal = 'NEUTRAL';
  if (rsi > 70) rsiSignal = 'OVERBOUGHT';
  else if (rsi < 30) rsiSignal = 'OVERSOLD';

  // 3. Bollinger Bands
  const bbMid = ma20;
  let variance = 0;
  prices.slice(-20).forEach(p => {
    variance += Math.pow(p - bbMid, 2);
  });
  const stdDev = Math.sqrt(variance / 20);
  const bbUpper = bbMid + 2 * stdDev;
  const bbLower = bbMid - 2 * stdDev;
  let bbSignal = 'NORMAL';
  if (currentPrice > bbUpper) bbSignal = 'OVER UPPER BAND';
  else if (currentPrice < bbLower) bbSignal = 'UNDER LOWER BAND';
  else if (stdDev < (bbMid * 0.02)) bbSignal = 'BB SQUEEZE (LOW VOLATILITY)';

  // 4. MACD Simple Approximation
  let ema12 = prices[0];
  let ema26 = prices[0];
  const k12 = 2 / 13;
  const k26 = 2 / 27;
  for (let i = 1; i < len; i++) {
    ema12 = prices[i] * k12 + ema12 * (1 - k12);
    ema26 = prices[i] * k26 + ema26 * (1 - k26);
  }
  const macd = ema12 - ema26;
  const macdSignal = macd > 0 ? 'BULLISH crossover' : 'BEARISH crossover';

  // Overall Recommendation
  let buyVotes = 0;
  let sellVotes = 0;
  if (ma5 > ma20) buyVotes++; else sellVotes++;
  if (rsi < 30) buyVotes += 2;
  if (rsi > 70) sellVotes += 2;
  if (currentPrice < bbLower) buyVotes++;
  if (currentPrice > bbUpper) sellVotes++;
  if (macd > 0) buyVotes++; else sellVotes++;

  let overall = 'NEUTRAL';
  if (buyVotes >= 3) overall = 'STRONG BUY';
  else if (buyVotes === 2) overall = 'BUY';
  else if (sellVotes >= 3) overall = 'STRONG SELL';
  else if (sellVotes === 2) overall = 'SELL';

  return {
    rsi: rsi.toFixed(1),
    rsiSignal,
    ma5: ma5.toFixed(2),
    ma20: ma20.toFixed(2),
    maSignal,
    bbUpper: bbUpper.toFixed(2),
    bbLower: bbLower.toFixed(2),
    bbSignal,
    macd: macd.toFixed(3),
    macdSignal,
    overall
  };
}

// Calculate IDX Stock Exchange hours (Jakarta WIB timezone)
function getIDXSessionStatus() {
  const now = new Date();
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const jktTime = new Date(utc + (3600000 * 7)); // WIB is UTC+7
  
  const day = jktTime.getDay(); // 0: Sun, 1: Mon, ..., 5: Fri, 6: Sat
  const hour = jktTime.getHours();
  const min = jktTime.getMinutes();
  const timeVal = hour * 60 + min; // minutes since midnight
  
  if (day === 0 || day === 6) {
    return { open: false, desc: 'Bursa Tutup (Akhir Pekan)' };
  }
  
  // Monday - Thursday
  if (day >= 1 && day <= 4) {
    if (timeVal >= 540 && timeVal <= 720) {
      return { open: true, desc: 'Bursa Buka (Sesi 1)' };
    }
    if (timeVal > 720 && timeVal < 810) {
      return { open: false, desc: 'Bursa Istirahat (Sesi Break)' };
    }
    if (timeVal >= 810 && timeVal <= 960) {
      return { open: true, desc: 'Bursa Buka (Sesi 2)' };
    }
  }
  
  // Friday
  if (day === 5) {
    if (timeVal >= 540 && timeVal <= 690) {
      return { open: true, desc: 'Bursa Buka (Sesi 1 - Jumat)' };
    }
    if (timeVal > 690 && timeVal < 840) {
      return { open: false, desc: 'Bursa Istirahat (Sesi Break)' };
    }
    if (timeVal >= 840 && timeVal <= 960) {
      return { open: true, desc: 'Bursa Buka (Sesi 2)' };
    }
  }
  
  return { open: false, desc: 'Bursa Tutup (Luar Jam Kerja)' };
}

// Update Technical signals on UI
function updateTechnicalSignals() {
  const symbol = state.activeStock;
  const history = state.historicalData[symbol];
  
  const indicators = calculateTechnicalIndicators(history);
  
  // Update elements
  const rsiEl = document.getElementById('indicatorRSI');
  const rsiSigEl = document.getElementById('indicatorRSISignal');
  const maSigEl = document.getElementById('indicatorMASignal');
  const bbSigEl = document.getElementById('indicatorBBSignal');
  const macdEl = document.getElementById('indicatorMACD');
  const macdSigEl = document.getElementById('indicatorMACDSignal');
  const overallEl = document.getElementById('overallRecommendation');
  
  rsiEl.textContent = indicators.rsi;
  rsiSigEl.textContent = indicators.rsiSignal;
  maSigEl.textContent = indicators.maSignal;
  bbSigEl.textContent = indicators.bbSignal;
  macdEl.textContent = indicators.macd;
  macdSigEl.textContent = indicators.macdSignal;
  overallEl.textContent = indicators.overall;
  
  // Update RSI marker on the visual meter scale
  const rsiMarker = document.getElementById('rsiMarker');
  if (rsiMarker) {
    const rsiVal = parseFloat(indicators.rsi) || 50;
    rsiMarker.style.left = `${Math.min(Math.max(rsiVal, 0), 100)}%`;
    if (indicators.rsiSignal === 'OVERBOUGHT') {
      rsiMarker.style.backgroundColor = colors.DOWN;
    } else if (indicators.rsiSignal === 'OVERSOLD') {
      rsiMarker.style.backgroundColor = colors.UP;
    } else {
      rsiMarker.style.backgroundColor = colors[symbol];
    }
  }

  // Dynamic colors
  if (indicators.rsiSignal === 'OVERBOUGHT') rsiSigEl.style.color = colors.DOWN;
  else if (indicators.rsiSignal === 'OVERSOLD') rsiSigEl.style.color = colors.UP;
  else rsiSigEl.style.color = 'var(--text-muted)';
  
  if (indicators.maSignal.includes('BULLISH')) maSigEl.style.color = colors.UP;
  else maSigEl.style.color = colors.DOWN;
  
  if (indicators.bbSignal.includes('UNDER')) bbSigEl.style.color = colors.UP;
  else if (indicators.bbSignal.includes('OVER')) bbSigEl.style.color = colors.DOWN;
  else bbSigEl.style.color = 'var(--text-muted)';
  
  if (indicators.macdSignal.includes('BULLISH')) macdSigEl.style.color = colors.UP;
  else macdSigEl.style.color = colors.DOWN;

  // Overall Recommendation styling
  overallEl.className = 'recommendation-badge';
  if (indicators.overall.includes('BUY')) {
    overallEl.style.backgroundColor = colors.UP.replace('rgb', 'rgba').replace(')', ', 0.15)');
    overallEl.style.color = colors.UP;
    overallEl.style.border = `1px solid ${colors.UP.replace('rgb', 'rgba').replace(')', ', 0.3)')}`;
  } else if (indicators.overall.includes('SELL')) {
    overallEl.style.backgroundColor = colors.DOWN.replace('rgb', 'rgba').replace(')', ', 0.15)');
    overallEl.style.color = colors.DOWN;
    overallEl.style.border = `1px solid ${colors.DOWN.replace('rgb', 'rgba').replace(')', ', 0.3)')}`;
  } else {
    overallEl.style.backgroundColor = 'rgba(255,255,255,0.05)';
    overallEl.style.color = 'var(--text-secondary)';
    overallEl.style.border = '1px solid var(--border-glass)';
  }
}

// Update IDX Trading session status badge
function updateIDXSessionStatus() {
  const status = getIDXSessionStatus();
  const badge = document.getElementById('idxSessionStatusBadge');
  const desc = document.getElementById('idxSessionDesc');
  
  badge.textContent = status.open ? 'IDX OPEN' : 'IDX CLOSED';
  desc.textContent = status.desc;
  
  if (status.open) {
    badge.style.backgroundColor = colors.UP.replace('rgb', 'rgba').replace(')', ', 0.15)');
    badge.style.color = colors.UP;
    badge.style.borderColor = colors.UP.replace('rgb', 'rgba').replace(')', ', 0.4)');
  } else {
    badge.style.backgroundColor = 'rgba(255,255,255,0.05)';
    badge.style.color = 'var(--text-muted)';
    badge.style.borderColor = 'var(--border-glass)';
  }
}

// Export prediction table to CSV file download
function exportPredictionsToCSV() {
  const symbol = state.activeStock;
  const preds = state.predictions.filter(p => p.Saham === symbol);
  
  if (preds.length === 0) {
    logConsole('No predictions available to export.', true);
    return;
  }
  
  logConsole(`Generating prediction CSV export for ${symbol}...`);
  
  // CSV Headers
  let csvContent = 'Saham,Hari,Tanggal,Harga_Prediksi,Perubahan_Rp,Perubahan_Persen,Tren,Confidence\n';
  
  // CSV Rows
  preds.forEach(p => {
    csvContent += `${p.Saham},${p.Hari},${p.Tanggal},${p.Harga_Prediksi},${p.Perubahan_Rp},${p.Perubahan_Persen},${p.Tren.replace('↑', '').replace('↓', '').trim()},${p.Confidence}\n`;
  });
  
  // Trigger file download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `prediksi_saham_30_hari_${symbol}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  logConsole(`CSV file exported successfully as prediksi_saham_30_hari_${symbol}.csv`);
}

// Global UI refresh
function updateUI() {
  updateStockCards();
  updateChart();
  updateSentimentPanel();
  updateNewsFeed();
  updateTechnicalSignals();
  updateIDXSessionStatus();
}

// Trigger prediction in background
async function runForecastGeneration(hargaBumi = null, hargaInet = null) {
  const loader = document.getElementById('chartLoader');
  const runBtn = document.getElementById('btnGenerateCustomForecast');
  const days = parseInt(document.getElementById('paramDays').value || 30);
  const loaderText = loader.querySelector('p');
  if (loaderText) {
    loaderText.textContent = `Memproses Prediksi ${days} Hari ke Depan...`;
  }
  loader.style.display = 'flex';
  runBtn.disabled = true;
  
  const sentiment = document.getElementById('paramUseSentiment').checked;
  
  logConsole(`Running ML forecast generation (Custom Prices BUMI: ${hargaBumi}, INET: ${hargaInet}, Sentiment: ${sentiment}, Hari: ${days})...`);
  
  try {
    const res = await fetch('/api/run_prediction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        harga_bumi: hargaBumi,
        harga_inet: hargaInet,
        sentiment: sentiment,
        days: days
      })
    });
    
    const result = await res.json();
    
    if (result.success) {
      logConsole('ML Ensemble models prediction successfully completed.');
      if (result.stdout) {
        logConsole('--- subprocess stdout ---');
        result.stdout.split('\n').forEach(line => {
          if (line.trim()) logConsole(line);
        });
      }
      // Re-fetch all predictions and update charts
      await fetchAllData();
    } else {
      logConsole(`Execution failure: ${result.stderr}`, true);
    }
  } catch (err) {
    logConsole(`API error running predictions: ${err.message}`, true);
  } finally {
    loader.style.display = 'none';
    runBtn.disabled = false;
  }
}

// Trigger news scraping & sentiment analysis
async function runNewsFetch() {
  const fetchBtn = document.getElementById('btnRunNewsFetch');
  fetchBtn.disabled = true;
  logConsole('Triggering NewsAPI scraping and NLP sentiment breakdown in background...');
  
  try {
    const res = await fetch('/api/run_news_fetch', { method: 'POST' });
    const result = await res.json();
    
    if (result.success) {
      logConsole('News fetching and NLP sentiment extraction completed.');
      if (result.stdout) {
        logConsole('--- news fetcher stdout ---');
        result.stdout.split('\n').forEach(line => {
          if (line.trim()) logConsole(line);
        });
      }
      await fetchAllData();

      // Scroll smoothly to the news section and briefly highlight it
      const newsSection = document.getElementById('newsSectionRow');
      if (newsSection) {
        newsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        newsSection.style.transition = 'box-shadow 0.4s ease';
        newsSection.style.boxShadow = '0 0 0 2px var(--color-bumi), 0 0 32px rgba(234,179,8,0.3)';
        setTimeout(() => { newsSection.style.boxShadow = ''; }, 2000);
      }
    } else {
      logConsole(`Failed fetching news: ${result.stderr}`, true);
    }
  } catch (err) {
    logConsole(`API error scraping news: ${err.message}`, true);
  } finally {
    fetchBtn.disabled = false;
  }
}

// Initial Wire-up
document.addEventListener('DOMContentLoaded', () => {
  // Tab click listeners
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      // Toggle active states
      tabs.forEach(t => t.classList.remove('active'));
      const targetTab = e.currentTarget;
      targetTab.classList.add('active');
      
      const stock = targetTab.getAttribute('data-stock');
      state.activeStock = stock;
      logConsole(`View switched to ${stock}`);
      updateUI();
    });
  });

  // Action buttons click listeners
  document.getElementById('btnRunNewsFetch').addEventListener('click', runNewsFetch);
  document.getElementById('btnExportCSV').addEventListener('click', exportPredictionsToCSV);

  // Chart toggle buttons
  document.getElementById('btnShowPrice').addEventListener('click', (e) => {
    document.getElementById('btnShowPrice').classList.add('active');
    document.getElementById('btnShowVolume').classList.remove('active');
    state.chartView = 'price';
    updateChart();
  });
  
  document.getElementById('btnShowVolume').addEventListener('click', (e) => {
    document.getElementById('btnShowPrice').classList.remove('active');
    document.getElementById('btnShowVolume').classList.add('active');
    state.chartView = 'volume';
    updateChart();
  });
  
  // Run models button (regenerates prediction based on standard flow)
  document.getElementById('btnRunPrediction').addEventListener('click', () => {
    runForecastGeneration(null, null);
  });

  // Custom Form update forecast button click listener
  document.getElementById('btnGenerateCustomForecast').addEventListener('click', () => {
    // Automatically runs forecast on latest real-time stock prices (null, null)
    runForecastGeneration(null, null);
  });

  // Live clock updating every second
  function updateLiveClock() {
    const clockEl = document.getElementById('idxClock');
    if (!clockEl) return;
    const now = new Date();
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const jktTime = new Date(utc + (3600000 * 7)); // WIB (UTC+7)
    
    const timeStr = jktTime.toLocaleTimeString('id-ID', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    clockEl.textContent = `${timeStr} WIB`;
  }

  // Load everything on startup
  fetchAllData();
  updateLiveClock();

  // Redraw chart immediately whenever user changes the day horizon input
  const paramDaysEl = document.getElementById('paramDays');
  if (paramDaysEl) {
    paramDaysEl.addEventListener('input', () => {
      updateChart();
    });
    paramDaysEl.addEventListener('change', () => {
      updateChart();
    });
  }

  // Run live clock every second
  setInterval(updateLiveClock, 1000);

  // Set interval to update IDX clock/status every 30 seconds
  setInterval(updateIDXSessionStatus, 30000);
});
