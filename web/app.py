# web/app.py
from flask import Flask, render_template, request, jsonify
import asyncio
import aiohttp
import logging
import json
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web/templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web/static'))

# Add this to ensure proper cleanup between requests
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up resources after each request."""
    pass  # We'll add specific cleanup code if needed

# Stock analysis system components
from core.task_manager import TaskManager
from agents.manager import ManagerAgent
from agents.price_agent import PriceAgent
from agents.financial_agent import FinancialAgent
from agents.news_agent import NewsAgent
from agents.sentiment_agent import SentimentAgent
from agents.report_agent import ReportAgent
from data.data_fetcher import DataFetcher
from data.cache import cache
from functools import wraps

# Initialize task manager and agents
task_manager = TaskManager()
manager_agent = ManagerAgent(task_manager)

# Register all agents with the task manager
task_manager.register_agent("manager", manager_agent)
task_manager.register_agent("price_agent", PriceAgent())
task_manager.register_agent("financial_agent", FinancialAgent())
task_manager.register_agent("news_agent", NewsAgent())
task_manager.register_agent("sentiment_agent", SentimentAgent())
task_manager.register_agent("report_agent", ReportAgent())

def async_route(f):
    """Decorator to make async routes work with Flask."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapped

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
@async_route
async def analyze_stock():
    """API endpoint to analyze a stock."""
    data = request.json
    symbol = data.get('symbol', '').upper()
    
    if not symbol:
        return jsonify({
            'status': 'error',
            'message': 'Stock symbol is required'
        }), 400
    
    try:
        # Check if we have a cached report
        cached_report = cache.get(f"report_{symbol}")
        if cached_report:
            logger.info(f"Returning cached report for {symbol}")
            return jsonify({
                'status': 'success',
                'data': cached_report
            })
        
        # Check if the symbol is valid with improved error handling
        try:
            is_valid = await DataFetcher.check_symbol_validity(symbol)
            if not is_valid:
                return jsonify({
                    'status': 'error',
                    'message': f"Could not validate stock symbol: {symbol}. Please check if this is a correct symbol."
                }), 400
        except Exception as e:
            logger.warning(f"Symbol validation error for {symbol}: {str(e)}")
            # Continue anyway since our validation might be failing, not the symbol
            logger.info(f"Proceeding with analysis for {symbol} despite validation failure")
        
        # Get company name with better error handling
        try:
            company_name = await DataFetcher.get_company_name(symbol)
        except Exception as e:
            logger.warning(f"Error getting company name for {symbol}: {str(e)}")
            company_name = symbol
        
        # Create manager task
        manager_task = {
            "stock_symbol": symbol,
            "company_name": company_name
        }
        
        # Process manager task
        manager_response = await manager_agent.process_task(manager_task)
        manager_result = json.loads(manager_response)
        
        if manager_result["status"] != "success":
            return jsonify({
                'status': 'error',
                'message': manager_result["message"]
            }), 500
        
        # Execute all tasks created by the manager
        task_results = await task_manager.execute_all_tasks()
        
        # Collect data from all agents
        stock_data = {
            "symbol": symbol,
            "company_name": company_name
        }
        
        for result in task_results:
            if result["status"] == "completed":
                agent_result = json.loads(result["result"])
                
                if agent_result["agent"] == "price_agent":
                    stock_data["price_data"] = agent_result["data"]
                elif agent_result["agent"] == "financial_agent":
                    stock_data["financial_data"] = agent_result["data"]
                elif agent_result["agent"] == "news_agent":
                    stock_data["news_data"] = agent_result["data"]
                elif agent_result["agent"] == "sentiment_agent":
                    stock_data["sentiment_data"] = agent_result["data"]
        
        # Create report task
        report_task = {
            "stock_data": stock_data
        }
        
        # Get report from report agent
        report_agent = task_manager.agents["report_agent"]
        report_response = await report_agent.process_task(report_task)
        report_result = json.loads(report_response)
        
        if report_result["status"] != "success":
            return jsonify({
                'status': 'error',
                'message': report_result["message"]
            }), 500
        
        # Construct final response
        response_data = {
            "symbol": symbol,
            "company_name": company_name,
            "timestamp": datetime.now().isoformat(),
            "report": report_result["data"]
        }
        
        # Cache the report for 5 minutes
        cache.set(f"report_{symbol}", response_data)
        
        return jsonify({
            'status': 'success',
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"Error analyzing stock: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error analyzing stock: {str(e)}"
        }), 500

@app.route('/api/search', methods=['GET'])
@async_route
async def search_symbol():
    """API endpoint to search for a stock symbol."""
    query = request.args.get('q', '').upper()
    
    if not query or len(query) < 2:
        return jsonify({
            'status': 'error',
            'message': 'Search query must be at least 2 characters'
        }), 400
    
    try:
        # Use our improved DataFetcher to search for symbols
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={query}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to search for symbols: {response.status}")
                    # Fallback to a simple search
                    return await fallback_search(query)
                
                data = await response.json()
                
                if "bestMatches" not in data or not data["bestMatches"]:
                    logger.warning(f"No matches found for {query} in Alpha Vantage")
                    # Fallback to a simple search
                    return await fallback_search(query)
                
                matches = []
                for match in data["bestMatches"][:5]:  # Limit to 5 results
                    matches.append({
                        "symbol": match.get("1. symbol", ""),
                        "name": match.get("2. name", ""),
                        "type": match.get("3. type", ""),
                        "region": match.get("4. region", "")
                    })
                
                return jsonify({
                    'status': 'success',
                    'data': matches
                })
                
    except Exception as e:
        logger.error(f"Error searching for symbol: {str(e)}")
        # Fallback to a simple search
        return await fallback_search(query)

async def fallback_search(query):
    """Fallback search when the API fails."""
    logger.info(f"Using fallback search for {query}")
    
    # Common stocks that might match the query
    common_stocks = [
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "type": "Common Stock", "region": "United States"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "GOOGL", "name": "Alphabet Inc. (Class A)", "type": "Common Stock", "region": "United States"},
        {"symbol": "GOOG", "name": "Alphabet Inc. (Class C)", "type": "Common Stock", "region": "United States"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "Common Stock", "region": "United States"},
        {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "type": "Common Stock", "region": "United States"},
        {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "Common Stock", "region": "United States"},
        {"symbol": "V", "name": "Visa Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "PG", "name": "Procter & Gamble Co.", "type": "Common Stock", "region": "United States"},
        {"symbol": "UNH", "name": "UnitedHealth Group Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "MA", "name": "Mastercard Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "HD", "name": "Home Depot Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "DIS", "name": "Walt Disney Co.", "type": "Common Stock", "region": "United States"},
        {"symbol": "BAC", "name": "Bank of America Corp.", "type": "Common Stock", "region": "United States"},
        {"symbol": "ADBE", "name": "Adobe Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "CRM", "name": "Salesforce.com Inc.", "type": "Common Stock", "region": "United States"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "type": "Common Stock", "region": "United States"}
    ]
    
    # Filter the stocks based on the query
    matches = []
    for stock in common_stocks:
        if (query.lower() in stock["symbol"].lower() or 
            query.lower() in stock["name"].lower()):
            matches.append(stock)
    
    return jsonify({
        'status': 'success',
        'data': matches[:5]  # Limit to 5 results
    })

def run_app():
    """Run the Flask app."""
    from config import PORT, DEBUG
    
    if DEBUG:
        # Use Flask's development server for debugging
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
    else:
        # Use Waitress for production
        from waitress import serve
        serve(app, host='0.0.0.0', port=PORT)


    