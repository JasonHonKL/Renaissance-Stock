# web/app.py
from flask import Flask, render_template, request, jsonify
import asyncio
import aiohttp
import logging
import json
import os
import traceback
from datetime import datetime
import time

# Configure more detailed logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to get more detailed logs
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("app.log"),  # Log to file
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# Create a performance logger for timing operations
perf_logger = logging.getLogger("performance")
perf_logger.setLevel(logging.INFO)

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web/templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web/static'))

# Log Flask app initialization
logger.info(f"Flask app initialized with template folder: {app.template_folder}")
logger.info(f"Flask app initialized with static folder: {app.static_folder}")

# Add this to ensure proper cleanup between requests
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up resources after each request."""
    if exception:
        logger.error(f"Error during request: {str(exception)}")
    logger.debug("Request context ended, cleaning up resources")
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
logger.info("Initializing task manager and agents")
task_manager = TaskManager()
manager_agent = ManagerAgent(task_manager)

# Register all agents with the task manager
logger.debug("Registering agents with task manager")
task_manager.register_agent("manager", manager_agent)
task_manager.register_agent("price_agent", PriceAgent())
task_manager.register_agent("financial_agent", FinancialAgent())
task_manager.register_agent("news_agent", NewsAgent())
task_manager.register_agent("sentiment_agent", SentimentAgent())
task_manager.register_agent("report_agent", ReportAgent())
logger.info("All agents registered successfully")

# web/app.py
from core.event_loop import loop_manager

def async_route(f):
    """Decorator to make async routes work with Flask."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        return loop_manager.run_async(f(*args, **kwargs))
    return wrapped

def performance_log(method):
    """Decorator to log performance of methods."""
    @wraps(method)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        method_name = method.__name__
        logger.debug(f"Starting {method_name}")
        try:
            result = await method(*args, **kwargs)
            end_time = time.time()
            perf_logger.info(f"{method_name} completed in {end_time - start_time:.2f} seconds")
            return result
        except Exception as e:
            end_time = time.time()
            logger.error(f"Exception in {method_name}: {str(e)}")
            logger.error(traceback.format_exc())
            perf_logger.info(f"{method_name} failed after {end_time - start_time:.2f} seconds")
            raise
    return wrapper

@app.route('/')
def index():
    """Render the main page."""
    logger.debug("Rendering index page")
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
@async_route
async def analyze_stock():
    """API endpoint to analyze a stock."""
    request_id = f"req-{int(time.time())}"
    logger.info(f"[{request_id}] Received analyze request")
    
    data = request.json
    logger.debug(f"[{request_id}] Request data: {data}")
    
    symbol = data.get('symbol', '').upper()
    logger.info(f"[{request_id}] Analyzing stock: {symbol}")
    
    if not symbol:
        logger.warning(f"[{request_id}] Missing stock symbol in request")
        return jsonify({
            'status': 'error',
            'message': 'Stock symbol is required'
        }), 400
    
    try:
        # Check if we have a cached report
        cached_report = cache.get(f"report_{symbol}")
        if cached_report:
            logger.info(f"[{request_id}] Returning cached report for {symbol}")
            return jsonify({
                'status': 'success',
                'data': cached_report
            })
        
        logger.info(f"[{request_id}] No cached report found for {symbol}, performing analysis")
        
        # Check if the symbol is valid with improved error handling
        try:
            logger.debug(f"[{request_id}] Validating symbol: {symbol}")
            is_valid = await DataFetcher.check_symbol_validity(symbol)
            if not is_valid:
                logger.warning(f"[{request_id}] Invalid stock symbol: {symbol}")
                return jsonify({
                    'status': 'error',
                    'message': f"Could not validate stock symbol: {symbol}. Please check if this is a correct symbol."
                }), 400
            logger.debug(f"[{request_id}] Symbol {symbol} is valid")
        except Exception as e:
            logger.warning(f"[{request_id}] Symbol validation error for {symbol}: {str(e)}")
            logger.debug(traceback.format_exc())
            # Continue anyway since our validation might be failing, not the symbol
            logger.info(f"[{request_id}] Proceeding with analysis for {symbol} despite validation failure")
        
        # Get company name with better error handling
        try:
            logger.debug(f"[{request_id}] Getting company name for {symbol}")
            company_name = await DataFetcher.get_company_name(symbol)
            logger.debug(f"[{request_id}] Company name for {symbol}: {company_name}")
        except Exception as e:
            logger.warning(f"[{request_id}] Error getting company name for {symbol}: {str(e)}")
            logger.debug(traceback.format_exc())
            company_name = symbol
            logger.info(f"[{request_id}] Using symbol as company name: {company_name}")
        
        # Create manager task
        manager_task = {
            "stock_symbol": symbol,
            "company_name": company_name
        }
        
        logger.info(f"[{request_id}] Processing manager task for {symbol}")
        logger.debug(f"[{request_id}] Manager task: {manager_task}")
        
        # Process manager task
        manager_start = time.time()
        manager_response = await manager_agent.process_task(manager_task)
        manager_end = time.time()
        perf_logger.info(f"[{request_id}] Manager agent completed in {manager_end - manager_start:.2f} seconds")
        
        logger.debug(f"[{request_id}] Manager response: {manager_response}")
        manager_result = json.loads(manager_response)
        
        if manager_result["status"] != "success":
            logger.error(f"[{request_id}] Manager agent failed: {manager_result['message']}")
            return jsonify({
                'status': 'error',
                'message': manager_result["message"]
            }), 500
        
        # Execute all tasks created by the manager
        logger.info(f"[{request_id}] Executing all tasks for {symbol}")
        tasks_start = time.time()
        task_results = await task_manager.execute_all_tasks()
        tasks_end = time.time()
        perf_logger.info(f"[{request_id}] All agent tasks completed in {tasks_end - tasks_start:.2f} seconds")
        
        logger.debug(f"[{request_id}] Task results: {task_results}")
        
        # Collect data from all agents
        stock_data = {
            "symbol": symbol,
            "company_name": company_name
        }
        
        for result in task_results:
            if result["status"] == "completed":
                agent_name = result.get("agent", "unknown")
                logger.debug(f"[{request_id}] Processing result from {agent_name}")
                
                try:
                    agent_result = json.loads(result["result"])
                    
                    if agent_result["agent"] == "price_agent":
                        stock_data["price_data"] = agent_result["data"]
                        logger.debug(f"[{request_id}] Added price data")
                    elif agent_result["agent"] == "financial_agent":
                        stock_data["financial_data"] = agent_result["data"]
                        logger.debug(f"[{request_id}] Added financial data")
                    elif agent_result["agent"] == "news_agent":
                        stock_data["news_data"] = agent_result["data"]
                        logger.debug(f"[{request_id}] Added news data")
                    elif agent_result["agent"] == "sentiment_agent":
                        stock_data["sentiment_data"] = agent_result["data"]
                        logger.debug(f"[{request_id}] Added sentiment data")
                except Exception as e:
                    logger.error(f"[{request_id}] Error processing result from {agent_name}: {str(e)}")
                    logger.error(traceback.format_exc())
                    logger.debug(f"[{request_id}] Problematic result: {result}")
            else:
                logger.warning(f"[{request_id}] Task not completed: {result}")
        
        # Log collected data summary
        data_keys = list(stock_data.keys())
        logger.info(f"[{request_id}] Collected data for {symbol}: {data_keys}")
        
        # Create report task
        report_task = {
            "stock_data": stock_data
        }
        
        # Get report from report agent
        logger.info(f"[{request_id}] Generating report for {symbol}")
        report_agent = task_manager.agents["report_agent"]
        report_start = time.time()
        report_response = await report_agent.process_task(report_task)
        report_end = time.time()
        perf_logger.info(f"[{request_id}] Report generation completed in {report_end - report_start:.2f} seconds")
        
        logger.debug(f"[{request_id}] Report response: {report_response}")
        report_result = json.loads(report_response)
        
        if report_result["status"] != "success":
            logger.error(f"[{request_id}] Report generation failed: {report_result['message']}")
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
        logger.debug(f"[{request_id}] Caching report for {symbol}")
        cache.set(f"report_{symbol}", response_data)
        
        logger.info(f"[{request_id}] Analysis completed successfully for {symbol}")
        
        return jsonify({
            'status': 'success',
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"[{request_id}] Error analyzing stock {symbol}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f"Error analyzing stock: {str(e)}"
        }), 500

@app.route('/api/search', methods=['GET'])
@async_route
async def search_symbol():
    """API endpoint to search for a stock symbol."""
    request_id = f"search-{int(time.time())}"
    query = request.args.get('q', '').upper()
    
    logger.info(f"[{request_id}] Received search request for: {query}")
    
    if not query or len(query) < 2:
        logger.warning(f"[{request_id}] Search query too short: {query}")
        return jsonify({
            'status': 'error',
            'message': 'Search query must be at least 2 characters'
        }), 400
    
    try:
        # Use our improved DataFetcher to search for symbols
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={query}&apikey={ALPHA_VANTAGE_API_KEY}"
        logger.debug(f"[{request_id}] Searching with URL: {url}")
        
        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"[{request_id}] Failed to search for symbols: {response.status}")
                    # Fallback to a simple search
                    logger.info(f"[{request_id}] Using fallback search for {query}")
                    return await fallback_search(query, request_id)
                
                data = await response.json()
                end_time = time.time()
                perf_logger.info(f"[{request_id}] Symbol search API completed in {end_time - start_time:.2f} seconds")
                
                logger.debug(f"[{request_id}] Search API response: {data}")
                
                if "bestMatches" not in data or not data["bestMatches"]:
                    logger.warning(f"[{request_id}] No matches found for {query} in Alpha Vantage")
                    # Fallback to a simple search
                    return await fallback_search(query, request_id)
                
                matches = []
                for match in data["bestMatches"][:5]:  # Limit to 5 results
                    matches.append({
                        "symbol": match.get("1. symbol", ""),
                        "name": match.get("2. name", ""),
                        "type": match.get("3. type", ""),
                        "region": match.get("4. region", "")
                    })
                
                logger.info(f"[{request_id}] Found {len(matches)} matches for {query}")
                logger.debug(f"[{request_id}] Matches: {matches}")
                
                return jsonify({
                    'status': 'success',
                    'data': matches
                })
                
    except Exception as e:
        logger.error(f"[{request_id}] Error searching for symbol {query}: {str(e)}")
        logger.error(traceback.format_exc())
        # Fallback to a simple search
        return await fallback_search(query, request_id)

async def fallback_search(query, request_id=None):
    """Fallback search when the API fails."""
    if not request_id:
        request_id = f"fallback-{int(time.time())}"
        
    logger.info(f"[{request_id}] Using fallback search for {query}")
    
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
    
    logger.info(f"[{request_id}] Fallback search found {len(matches)} matches for {query}")
    logger.debug(f"[{request_id}] Fallback matches: {matches[:5]}")
    
    return jsonify({
        'status': 'success',
        'data': matches[:5]  # Limit to 5 results
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """API endpoint to check system health."""
    logger.debug("Health check requested")
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    logger.warning(f"404 error: {request.path}")
    return jsonify({
        'status': 'error',
        'message': f"Endpoint not found: {request.path}"
    }), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"500 error: {str(e)}")
    return jsonify({
        'status': 'error',
        'message': f"Server error: {str(e)}"
    }), 500

def run_app():
    """Run the Flask app."""
    from config import PORT, DEBUG
    
    logger.info(f"Starting app with PORT={PORT}, DEBUG={DEBUG}")
    
    if DEBUG:
        # Use Flask's development server for debugging
        logger.info("Using Flask development server (DEBUG mode)")
        app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
    else:
        # Use Waitress for production
        logger.info("Using Waitress for production")
        from waitress import serve
        serve(app, host='0.0.0.0', port=PORT)
    