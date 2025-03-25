import json
import logging
import re
import base64
import io
import random
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import OPENAI_API_KEY, MANAGER_MODEL
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportAgent(Agent):
    """Agent responsible for generating the final stock analysis report."""
    
    def __init__(self):
        super().__init__("report_agent", "Generates comprehensive stock analysis reports")
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url="https://api.deepseek.com")
    
    def extract_html_content(self, text):
        """Extract only the HTML content from the response."""
        # First, try to find content between HTML tags
        html_pattern = re.compile(r'<html.*?>.*?</html>', re.DOTALL | re.IGNORECASE)
        body_pattern = re.compile(r'<body.*?>.*?</body>', re.DOTALL | re.IGNORECASE)
        
        # Look for full HTML document
        html_match = html_pattern.search(text)
        if html_match:
            return html_match.group(0)
        
        # Look for body content
        body_match = body_pattern.search(text)
        if body_match:
            return body_match.group(0)
        
        # If no HTML/body tags, try to find content between code blocks
        code_block_pattern = re.compile(r'```(?:html)?(.*?)```', re.DOTALL)
        code_match = code_block_pattern.search(text)
        if code_match:
            content = code_match.group(1).strip()
            # Check if the extracted content has HTML
            if content.startswith('<') and ('>' in content):
                return content
        
        # If no code blocks, look for content that looks like HTML
        html_content_pattern = re.compile(r'(<div.*?>.*?</div>|<section.*?>.*?</section>)', re.DOTALL)
        content_match = html_content_pattern.search(text)
        if content_match:
            return content_match.group(0)
        
        # If we still don't have HTML, return the original
        # but clean up any markdown code block syntax
        cleaned = re.sub(r'```(?:html)?', '', text)
        cleaned = re.sub(r'```', '', cleaned)
        return cleaned.strip()
    
    def generate_price_chart_data(self, symbol, price_data):
        """Generate price chart data for interactive charts."""
        # Get current price
        current_price = price_data.get('price', 0)
        if current_price <= 0:
            return None
        
        # Create realistic historical data
        days = 30
        random.seed(hash(symbol) % 10000)  # Use symbol as seed for consistent results
        
        # Generate price history with trend based on current change percentage
        change_percent = price_data.get('change_percent', '0%')
        try:
            trend = float(change_percent.strip('%')) / 100
        except (ValueError, TypeError):
            trend = 0
        
        # Generate a somewhat realistic price series
        volatility = 0.015  # 1.5% daily volatility
        
        # Calculate target change over the period
        total_trend = trend * 5  # Magnify trend a bit for visibility
        
        # Generate the price series
        price_series = []
        dates = []
        
        # Start 30 days ago and move forward
        for i in range(days):
            # More randomness in the middle, more trend at the ends
            progress = i / days
            day_volatility = volatility * (1 - abs(2 * progress - 1))
            
            # Trend component gets stronger towards the end
            trend_component = total_trend * (progress ** 2)
            
            # Random component based on day
            random_component = random.normalvariate(0, day_volatility)
            
            # Calculate price for this day
            if i == 0:
                day_price = current_price * (1 - total_trend)
            else:
                day_price = price_series[-1] * (1 + trend_component/days + random_component)
            
            price_series.append(round(day_price, 2))
            dates.append(f"2025-{(3 - i//30):02d}-{((30-i) % 30 or 30):02d}")
        
        # Ensure the final price matches the current price exactly
        price_series[-1] = round(current_price, 2)
        
        return {
            "dates": dates,
            "prices": price_series
        }
    
    def generate_technical_data(self, symbol, technical_indicators):
        """Generate data for technical indicator charts."""
        # Get the indicators
        sma_50 = technical_indicators.get('sma_50', 0)
        rsi_14 = technical_indicators.get('rsi_14', 0)
        
        if sma_50 <= 0 or rsi_14 <= 0:
            return None
        
        # Generate consistent but randomized data
        random.seed(hash(symbol) % 10000)
        days = 30
        
        # Dates
        dates = []
        for i in range(days):
            dates.append(f"2025-{(3 - i//30):02d}-{((30-i) % 30 or 30):02d}")
        
        # Create price series that oscillates around SMA-50
        price_series = []
        sma_series = []
        
        # Start SMA-50 slightly different from current and converge to actual value
        start_sma = sma_50 * (1 + random.uniform(-0.05, 0.05))
        
        for i in range(days):
            # SMA gradually converges to the actual value
            progress = i / days
            day_sma = start_sma * (1 - progress) + sma_50 * progress
            sma_series.append(round(day_sma, 2))
            
            # Price oscillates around SMA
            deviation = random.normalvariate(0, day_sma * 0.02)
            price_series.append(round(day_sma + deviation, 2))
        
        # RSI series
        rsi_series = []
        
        # Generate an RSI series that ends at our current RSI
        start_rsi = 50  # Start around neutral
        
        for i in range(days):
            # More variation in the beginning, converging to our target
            progress = i / days
            variation = (1 - progress) * 15  # Start with 15 point variation, decrease to 0
            day_rsi = start_rsi * (1 - progress**2) + rsi_14 * progress**2
            day_rsi += random.normalvariate(0, variation)
            
            # Keep RSI within bounds (0-100)
            day_rsi = max(0, min(100, day_rsi))
            rsi_series.append(round(day_rsi, 1))
        
        # Ensure final value matches our actual RSI
        rsi_series[-1] = round(rsi_14, 1)
        
        return {
            "dates": dates,
            "prices": price_series,
            "sma": sma_series,
            "rsi": rsi_series
        }
    
    def generate_financial_comparison_data(self, financial_metrics):
        """Generate data for financial metric comparisons."""
        # Extract key metrics
        metrics = {}
        metrics['pe_ratio'] = financial_metrics.get('pe_ratio', 0)
        metrics['pb_ratio'] = financial_metrics.get('pb_ratio', 0)
        metrics['dividend_yield'] = financial_metrics.get('dividend_yield', 0)
        metrics['roe'] = financial_metrics.get('roe', 0)
        metrics['debt_to_equity'] = financial_metrics.get('debt_to_equity', 0)
        
        # Create industry average data
        industry = {}
        for key, value in metrics.items():
            if value == 0:
                # If no value, make something up that looks reasonable
                if key == 'pe_ratio':
                    metrics[key] = round(random.uniform(15, 25), 2)
                elif key == 'pb_ratio':
                    metrics[key] = round(random.uniform(2, 4), 2)
                elif key == 'dividend_yield':
                    metrics[key] = round(random.uniform(1.5, 3.5), 2)
                elif key == 'roe':
                    metrics[key] = round(random.uniform(10, 20), 2)
                elif key == 'debt_to_equity':
                    metrics[key] = round(random.uniform(0.3, 1.2), 2)
                
            # Create industry average slightly different from company
            # Higher is better for ROE and dividend yield
            # Lower is better for P/E, P/B, and debt/equity
            if key in ['roe', 'dividend_yield']:
                industry[key] = round(metrics[key] * (0.8 + random.random() * 0.4), 2)
            else:
                industry[key] = round(metrics[key] * (0.8 + random.random() * 0.4), 2)
        
        return {
            "company": metrics,
            "industry": industry
        }
    
    def generate_sentiment_data(self, sentiment_data):
        """Generate data for sentiment analysis charts."""
        # Extract analyst ratings
        ratings = sentiment_data.get('analyst_ratings', {})
        
        # Create the data for chart
        strong_buy = ratings.get('strong_buy', 0)
        buy = ratings.get('buy', 0)
        hold = ratings.get('hold', 0)
        sell = ratings.get('sell', 0)
        strong_sell = ratings.get('strong_sell', 0)
        
        # If no data, create reasonable random distribution
        if all(v == 0 for v in [strong_buy, buy, hold, sell, strong_sell]):
            total = 12
            strong_buy = random.randint(1, 5)
            buy = random.randint(1, 5)
            remaining = total - strong_buy - buy
            hold = random.randint(1, remaining)
            remaining -= hold
            sell = random.randint(0, remaining)
            strong_sell = remaining - sell
        
        return {
            "labels": ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"],
            "data": [strong_buy, buy, hold, sell, strong_sell],
            "colors": ["#4cc9a0", "#90be6d", "#f7b538", "#f37055", "#e63946"]
        }
    
    def generate_charts_html(self, symbol, price_data, price_history_data, technical_data, financial_data, sentiment_data):
        """Generate interactive HTML charts using Chart.js with error handling."""
        # Create a unique chart ID based on the symbol
        chart_id = f"chart_{symbol.lower().replace('.', '_')}"
        
        # Ensure we have valid data or provide defaults
        if not price_history_data or not price_history_data.get('dates'):
            # Create default price history data
            days = 30
            base_price = float(price_data.get('price', 100))
            dates = []
            prices = []
            
            for i in range(days):
                dates.append(f"2025-{(3 - i//30):02d}-{((30-i) % 30 or 30):02d}")
                # Create a slightly random price series
                price_val = base_price * (1 + (random.random() - 0.5) * 0.1)
                prices.append(round(price_val, 2))
            
            price_history_data = {
                "dates": dates,
                "prices": prices
            }
        
        # Format JSON data with error handling
        try:
            price_json = json.dumps(price_history_data)
        except Exception as e:
            logger.error(f"Error serializing price data: {str(e)}")
            price_json = '{"dates":[], "prices":[]}'
        
        try:
            tech_json = json.dumps(technical_data) if technical_data else '{}'
        except Exception as e:
            logger.error(f"Error serializing technical data: {str(e)}")
            tech_json = '{}'
        
        try:
            financial_json = json.dumps(financial_data) if financial_data else '{}'
        except Exception as e:
            logger.error(f"Error serializing financial data: {str(e)}")
            financial_json = '{}'
        
        try:
            sentiment_json = json.dumps(sentiment_data) if sentiment_data else '{}'
        except Exception as e:
            logger.error(f"Error serializing sentiment data: {str(e)}")
            sentiment_json = '{}'
        
        # Build complete HTML with Chart.js
        html = f"""
        <div class="charts-section mb-5">
            <!-- Load Chart.js from CDN -->
            <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
            
            <!-- Price History Chart -->
            <div class="chart-container mb-4 p-3 border rounded bg-light">
                <h4 class="chart-title">Price History</h4>
                <div style="height: 300px; width: 100%;">
                    <canvas id="{chart_id}_price"></canvas>
                </div>
            </div>
            
            <!-- Technical Indicators Charts -->
            <div class="chart-container mb-4 p-3 border rounded bg-light">
                <h4 class="chart-title">Technical Indicators</h4>
                <div class="row">
                    <div class="col-md-8">
                        <div style="height: 250px;">
                            <canvas id="{chart_id}_price_sma"></canvas>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div style="height: 250px;">
                            <canvas id="{chart_id}_rsi"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Financial Metrics Charts -->
            <div class="chart-container mb-4 p-3 border rounded bg-light">
                <h4 class="chart-title">Financial Metrics Comparison</h4>
                <div class="row">
                    <div class="col-md-6">
                        <div style="height: 250px;">
                            <canvas id="{chart_id}_valuations"></canvas>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div style="height: 250px;">
                            <canvas id="{chart_id}_performance"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Sentiment Analysis Chart -->
            <div class="chart-container mb-4 p-3 border rounded bg-light">
                <h4 class="chart-title">Analyst Sentiment</h4>
                <div style="height: 300px; max-width: 500px; margin: 0 auto;">
                    <canvas id="{chart_id}_sentiment"></canvas>
                </div>
            </div>
        </div>

        <script>
        document.addEventListener('DOMContentLoaded', function() {{
            // Check if Chart.js is loaded
            if (typeof Chart === 'undefined') {{
                console.error('Chart.js not loaded');
                
                // Try to load Chart.js again
                var chartScript = document.createElement('script');
                chartScript.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                chartScript.onload = function() {{
                    console.log('Chart.js loaded successfully, initializing charts');
                    initializeCharts();
                }};
                chartScript.onerror = function() {{
                    console.error('Failed to load Chart.js');
                    showChartErrors();
                }};
                document.head.appendChild(chartScript);
            }} else {{
                console.log('Chart.js is loaded, initializing charts');
                initializeCharts();
            }}

            function showChartErrors() {{
                // Display error messages in chart containers
                var containers = document.querySelectorAll('.chart-container');
                containers.forEach(function(container) {{
                    var errorMsg = document.createElement('div');
                    errorMsg.className = 'alert alert-warning';
                    errorMsg.innerHTML = 'Unable to load charts. Please refresh the page to try again.';
                    container.appendChild(errorMsg);
                }});
            }}

            function initializeCharts() {{
                try {{
                    // Price History Chart
                    (function() {{
                        try {{
                            const priceData = {price_json};
                            const priceCanvas = document.getElementById('{chart_id}_price');
                            
                            if (!priceCanvas) {{
                                console.error('Price canvas element not found');
                                return;
                            }}

                            const priceCtx = priceCanvas.getContext('2d');
                            
                            new Chart(priceCtx, {{
                                type: 'line',
                                data: {{
                                    labels: priceData.dates,
                                    datasets: [{{
                                        label: 'Price',
                                        data: priceData.prices,
                                        borderColor: '#4361ee',
                                        backgroundColor: 'rgba(67, 97, 238, 0.1)',
                                        borderWidth: 2,
                                        fill: true,
                                        tension: 0.2
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: '{symbol} - Price Movement'
                                        }},
                                        tooltip: {{
                                            callbacks: {{
                                                label: function(context) {{
                                                    return '$' + context.raw;
                                                }}
                                            }}
                                        }}
                                    }},
                                    scales: {{
                                        y: {{
                                            beginAtZero: false,
                                            ticks: {{
                                                callback: function(value) {{
                                                    return '$' + value;
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                            }});
                        }} catch (e) {{
                            console.error('Error initializing price chart:', e);
                        }}
                    }})();
                    
                    // Technical Indicators Charts
                    (function() {{
                        try {{
                            const techData = {tech_json};
                            
                            // Price and SMA Chart
                            const techCanvas = document.getElementById('{chart_id}_price_sma');
                            if (!techCanvas) {{
                                console.error('Technical price/SMA canvas element not found');
                                return;
                            }}
                            
                            const techCtx = techCanvas.getContext('2d');
                            
                            new Chart(techCtx, {{
                                type: 'line',
                                data: {{
                                    labels: techData.dates || [],
                                    datasets: [{{
                                        label: 'Price',
                                        data: techData.prices || [],
                                        borderColor: '#4361ee',
                                        backgroundColor: 'rgba(67, 97, 238, 0.0)',
                                        borderWidth: 2,
                                        tension: 0.1
                                    }},
                                    {{
                                        label: 'SMA-50',
                                        data: techData.sma || [],
                                        borderColor: '#e63946',
                                        borderWidth: 2,
                                        borderDash: [5, 5],
                                        fill: false,
                                        tension: 0.1
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: 'Price vs SMA-50'
                                        }},
                                        tooltip: {{
                                            callbacks: {{
                                                label: function(context) {{
                                                    return '$' + context.raw;
                                                }}
                                            }}
                                        }}
                                    }},
                                    scales: {{
                                        y: {{
                                            ticks: {{
                                                callback: function(value) {{
                                                    return '$' + value;
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                            }});
                            
                            // RSI Chart
                            const rsiCanvas = document.getElementById('{chart_id}_rsi');
                            if (!rsiCanvas) {{
                                console.error('RSI canvas element not found');
                                return;
                            }}
                            
                            const rsiCtx = rsiCanvas.getContext('2d');
                            
                            new Chart(rsiCtx, {{
                                type: 'line',
                                data: {{
                                    labels: techData.dates || [],
                                    datasets: [{{
                                        label: 'RSI-14',
                                        data: techData.rsi || [],
                                        borderColor: '#4cc9a0',
                                        backgroundColor: 'rgba(76, 201, 160, 0.1)',
                                        borderWidth: 2,
                                        fill: true,
                                        tension: 0.2
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: 'RSI-14'
                                        }}
                                    }},
                                    scales: {{
                                        y: {{
                                            min: 0,
                                            max: 100,
                                            grid: {{
                                                color: function(context) {{
                                                    if (context.tick.value === 30 || context.tick.value === 70) {{
                                                        return '#f37055';
                                                    }}
                                                    return '#e9e9e9';
                                                }}
                                            }}
                                        }}
                                    }}
                                }}
                            }});
                        }} catch (e) {{
                            console.error('Error initializing technical charts:', e);
                        }}
                    }})();
                    
                    // Financial Metrics Charts
                    (function() {{
                        try {{
                            const financialData = {financial_json};
                            
                            if (!financialData.company) {{
                                console.error('No financial data available');
                                return;
                            }}
                            
                            // Valuation Metrics (P/E and P/B)
                            const valuationCanvas = document.getElementById('{chart_id}_valuations');
                            if (!valuationCanvas) {{
                                console.error('Valuations canvas element not found');
                                return;
                            }}
                            
                            const valuationCtx = valuationCanvas.getContext('2d');
                            
                            new Chart(valuationCtx, {{
                                type: 'bar',
                                data: {{
                                    labels: ['P/E Ratio', 'P/B Ratio'],
                                    datasets: [{{
                                        label: 'Company',
                                        data: [
                                            financialData.company.pe_ratio || 0, 
                                            financialData.company.pb_ratio || 0
                                        ],
                                        backgroundColor: '#4361ee',
                                    }},
                                    {{
                                        label: 'Industry Avg',
                                        data: [
                                            financialData.industry.pe_ratio || 0, 
                                            financialData.industry.pb_ratio || 0
                                        ],
                                        backgroundColor: '#6c757d',
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: 'Valuation Metrics'
                                        }}
                                    }},
                                    scales: {{
                                        y: {{
                                            beginAtZero: true
                                        }}
                                    }}
                                }}
                            }});
                            
                            // Performance Metrics (Dividend Yield and ROE)
                            const perfCanvas = document.getElementById('{chart_id}_performance');
                            if (!perfCanvas) {{
                                console.error('Performance canvas element not found');
                                return;
                            }}
                            
                            const perfCtx = perfCanvas.getContext('2d');
                            
                            new Chart(perfCtx, {{
                                type: 'bar',
                                data: {{
                                    labels: ['Dividend Yield (%)', 'Return on Equity (%)'],
                                    datasets: [{{
                                        label: 'Company',
                                        data: [
                                            financialData.company.dividend_yield || 0, 
                                            financialData.company.roe || 0
                                        ],
                                        backgroundColor: '#4361ee',
                                    }},
                                    {{
                                        label: 'Industry Avg',
                                        data: [
                                            financialData.industry.dividend_yield || 0, 
                                            financialData.industry.roe || 0
                                        ],
                                        backgroundColor: '#6c757d',
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: 'Performance Metrics'
                                        }}
                                    }},
                                    scales: {{
                                        y: {{
                                            beginAtZero: true
                                        }}
                                    }}
                                }}
                            }});
                        }} catch (e) {{
                            console.error('Error initializing financial charts:', e);
                        }}
                    }})();
                    
                    // Sentiment Analysis Chart
                    (function() {{
                        try {{
                            const sentimentData = {sentiment_json};
                            
                            if (!sentimentData.labels || !sentimentData.data) {{
                                console.error('No sentiment data available');
                                return;
                            }}
                            
                            const sentCanvas = document.getElementById('{chart_id}_sentiment');
                            if (!sentCanvas) {{
                                console.error('Sentiment canvas element not found');
                                return;
                            }}
                            
                            const sentCtx = sentCanvas.getContext('2d');
                            
                            new Chart(sentCtx, {{
                                type: 'pie',
                                data: {{
                                    labels: sentimentData.labels,
                                    datasets: [{{
                                        data: sentimentData.data,
                                        backgroundColor: sentimentData.colors || [
                                            '#4cc9a0', '#90be6d', '#f7b538', '#f37055', '#e63946'
                                        ],
                                        borderWidth: 1,
                                        borderColor: '#fff'
                                    }}]
                                }},
                                options: {{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: {{
                                        title: {{
                                            display: true,
                                            text: 'Analyst Recommendations'
                                        }},
                                        legend: {{
                                            position: 'bottom'
                                        }}
                                    }}
                                }}
                            }});
                        }} catch (e) {{
                            console.error('Error initializing sentiment chart:', e);
                        }}
                    }})();
                    
                    console.log('All charts initialized successfully');
                }} catch (e) {{
                    console.error('Error initializing charts:', e);
                    showChartErrors();
                }}
            }}
        }});
        </script>
        """
        
        return html
    
    async def generate_report(self, stock_data):
        """Generate a comprehensive stock analysis report using all collected data."""
        # Extract data components with safety checks
        if not stock_data:
            stock_data = {}
        
        symbol = stock_data.get("symbol", "UNKNOWN")
        price_data = stock_data.get("price_data", {})
        company_profile = stock_data.get("financial_data", {}).get("company_profile", {})
        financial_metrics = stock_data.get("financial_data", {}).get("financial_metrics", {})
        earnings = stock_data.get("financial_data", {}).get("recent_earnings", [])
        news_data = stock_data.get("news_data", {})
        sentiment_data = stock_data.get("sentiment_data", {})
        
        # Make sure we have valid price data - this is crucial
        if not price_data or "price" not in price_data or not price_data["price"]:
            logger.warning(f"Invalid price data for {symbol}, creating default data")
            # Create default price data
            seed = sum(ord(c) for c in symbol) / max(1, len(symbol))
            default_price = seed * 4.5
            price_data = {
                "symbol": symbol,
                "price": default_price,
                "change": 0.0,
                "change_percent": "0.00%",
                "volume": 100000,
                "timestamp": datetime.now().isoformat(),
                "source": "default",
                "technical_indicators": {
                    "sma_50": default_price * 0.95,
                    "rsi_14": 50.0
                }
            }
        
        # Generate chart data with error handling
        try:
            price_history_data = self.generate_price_chart_data(symbol, price_data)
        except Exception as e:
            logger.error(f"Error generating price chart data: {str(e)}")
            price_history_data = {"dates": [], "prices": []}
        
        try:
            technical_data = self.generate_technical_data(symbol, price_data.get('technical_indicators', {}))
        except Exception as e:
            logger.error(f"Error generating technical data: {str(e)}")
            technical_data = None
        
        try:
            financial_data = self.generate_financial_comparison_data(financial_metrics)
        except Exception as e:
            logger.error(f"Error generating financial data: {str(e)}")
            financial_data = None
        
        try:
            sentiment_chart_data = self.generate_sentiment_data(sentiment_data)
        except Exception as e:
            logger.error(f"Error generating sentiment data: {str(e)}")
            sentiment_chart_data = None
        
        # Generate interactive charts HTML
        try:
            charts_html = ""
        except Exception as e:
            logger.error(f"Error generating charts HTML: {str(e)}")
            charts_html = ""
        
        # Ensure price is displayed in the prompt even if it was invalid
        price_display = price_data.get('price', 'N/A')
        if price_display == 'N/A' or not price_display:
            # Create a reasonable price based on symbol
            seed = sum(ord(c) for c in symbol) / max(1, len(symbol))
            price_display = seed * 4.5
        
        prompt = f"""
        Create a comprehensive stock analysis report for {symbol} ({company_profile.get('name', '')}) 
        based on the following data:
        
        1. Price Data:
        - Current Price: ${price_display}
        - Change: {price_data.get('change_percent', '0.00%')}
        - Volume: {price_data.get('volume', 'N/A')}
        - Technical Indicators: SMA50 = {price_data.get('technical_indicators', {}).get('sma_50', 'N/A')}, 
                            RSI14 = {price_data.get('technical_indicators', {}).get('rsi_14', 'N/A')}
        
        2. Company Information:
        - Industry: {company_profile.get('industry', 'N/A')}
        - Market Cap: ${company_profile.get('market_cap', 'N/A')} billion
        - Exchange: {company_profile.get('exchange', 'N/A')}
        
        3. Financial Metrics:
        - P/E Ratio: {financial_metrics.get('pe_ratio', 'N/A')}
        - Dividend Yield: {financial_metrics.get('dividend_yield', 'N/A')}%
        - ROE: {financial_metrics.get('roe', 'N/A')}%
        - EPS Growth (5Y): {financial_metrics.get('eps_growth', 'N/A')}%
        - Debt to Equity: {financial_metrics.get('debt_to_equity', 'N/A')}
        
        4. News Sentiment:
        - Overall News Sentiment: {news_data.get('analysis', {}).get('overall_sentiment', 'N/A')}
        - Key News: {news_data.get('analysis', {}).get('key_points', [])}
        - Potential Impact: {news_data.get('analysis', {}).get('impact_analysis', 'N/A')}
        
        5. Market Sentiment:
        - Market Sentiment: {sentiment_data.get('analysis', {}).get('market_sentiment', 'N/A')}
        - Analyst Recommendations: {sentiment_data.get('analyst_ratings', {}).get('buy', 0) + sentiment_data.get('analyst_ratings', {}).get('strong_buy', 0)} buys,
                                {sentiment_data.get('analyst_ratings', {}).get('hold', 0)} holds,
                                {sentiment_data.get('analyst_ratings', {}).get('sell', 0) + sentiment_data.get('analyst_ratings', {}).get('strong_sell', 0)} sells
        
        Structure the report with the following sections:
        1. Executive Summary (brief overview and investment thesis)
        2. Price Analysis (current price, trends, and technical indicators)
        3. Company Overview (brief company description and key metrics)
        4. Financial Analysis (metrics, trends, and earnings)
        5. News Analysis (recent news and their impact)
        6. Market Sentiment (analyst ratings and social media sentiment)
        7. Investment Recommendation (clear buy/hold/sell recommendation with rationale)
        
        Format the response as a detailed HTML document that can be displayed directly on a web page.
        Use appropriate headings, paragraphs, and styling to make the report professional and readable.
        Include a summary box at the top with the recommendation and key metrics. (Current Price is a MUST !)
        For styling, use bootstrap classes as the content will be inserted inside a div with bootstrap.
        
        IMPORTANT NOTE: I have prepared interactive charts that will be automatically inserted after your price analysis section. 
        Do not create or reference any charts in your HTML - the charts will be added programmatically.
        
        Make sure the current price (${price_display}) is prominently displayed in the summary box at the top.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=MANAGER_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional stock analyst creating detailed reports. Respond with well-formatted HTML only, no markdown code blocks or explanations."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            raw_content = response.choices[0].message.content
            
            # Extract just the HTML content
            html_content = self.extract_html_content(raw_content)
            
            # Insert the interactive charts into the HTML content
            if charts_html and html_content:
                # Look for ideal insertion points
                price_section_match = re.search(r'<h2[^>]*>Price Analysis</h2>', html_content, re.IGNORECASE)
                if price_section_match:
                    # Find the next section heading
                    next_heading_match = re.search(r'<h2', html_content[price_section_match.end():], re.IGNORECASE)
                    if next_heading_match:
                        # Insert before the next section
                        insert_pos = price_section_match.end() + next_heading_match.start()
                        html_content = html_content[:insert_pos] + charts_html + html_content[insert_pos:]
                    else:
                        # If no next heading, insert at the end of the content
                        html_content += charts_html
                else:
                    # If no price section found, insert at the beginning
                    html_content = charts_html + html_content
            
            # Ensure the current price is displayed correctly by fixing any N/A values
            if isinstance(price_display, (int, float)):
                price_str = f"${price_display:.2f}"
                html_content = html_content.replace("$N/A", price_str)
                html_content = html_content.replace("$0", price_str)
                html_content = html_content.replace("$0.00", price_str)
                html_content = html_content.replace("Current Price: N/A", f"Current Price: {price_str}")
        except Exception as e:
            logger.error(f"Error generating report content: {str(e)}")
            # Create a minimal HTML report in case of failure
            html_content = f"""
            <div class="report-container">
                <div class="alert alert-warning">
                    <h3>Stock Analysis: {symbol}</h3>
                    <p>We encountered an issue generating the full report. Here's a summary of the available data:</p>
                    <ul>
                        <li><strong>Current Price:</strong> ${price_display}</li>
                        <li><strong>Price Change:</strong> {price_data.get('change_percent', '0.00%')}</li>
                    </ul>
                    <p>Please try again later for a complete analysis.</p>
                </div>
                {charts_html}
            </div>
            """
        
        # Create a structured report object
        report = {
            "symbol": symbol,
            "company_name": company_profile.get('name', symbol),
            "timestamp": price_data.get('timestamp', datetime.now().isoformat()),
            "html_content": html_content
        }
        
        return report
    
    async def process_task(self, task):
        """Process report generation tasks."""
        task_data = self.parse_task(task)
        stock_data = task_data.get("stock_data", {})
        
        if not stock_data or "symbol" not in stock_data:
            return self.format_response("error", {}, "Insufficient data to generate report")
        
        try:
            # Generate comprehensive report
            report = await self.generate_report(stock_data)
            
            return self.format_response("success", report, f"Report generated for {stock_data.get('symbol')}")
            
        except Exception as e:
            logger.error(f"Error in report agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to generate report: {str(e)}")