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

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
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
async def search_symbol():
    """API endpoint to search for a stock symbol."""
    query = request.args.get('q', '').upper()
    
    if not query or len(query) < 2:
        return jsonify({
            'status': 'error',
            'message': 'Search query must be at least 2 characters'
        }), 400
    
    try:
        # In a real app, you'd use an API to search for symbols
        # This is a simplified example
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={query}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to search for symbols'
                    }), 500
                
                data = await response.json()
                
                if "bestMatches" not in data:
                    return jsonify({
                        'status': 'error',
                        'message': 'No matches found'
                    }), 404
                
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
        return jsonify({
            'status': 'error',
            'message': f"Error searching for symbol: {str(e)}"
        }), 500

def run_app():
    """Run the Flask app."""
    from config import PORT, DEBUG
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)