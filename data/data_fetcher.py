# data/data_fetcher.py
import logging
import aiohttp
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataFetcher:
    """Utility class for fetching data from various financial APIs."""
    
    @staticmethod
    async def fetch_json(url, headers=None):
        """Fetch JSON data from a URL."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error fetching data: {response.status}")
                        return None
                    
                    return await response.json()
            except Exception as e:
                logger.error(f"Error in fetch_json: {str(e)}")
                return None
    
    @staticmethod
    async def check_symbol_validity(symbol):
        """Check if a stock symbol is valid using multiple APIs."""
        # Try using Alpha Vantage first
        is_valid = await DataFetcher._check_alpha_vantage(symbol)
        if is_valid:
            return True
            
        # If Alpha Vantage fails, try Finnhub
        is_valid = await DataFetcher._check_finnhub(symbol)
        if is_valid:
            return True
            
        # Last resort: try symbol search
        is_valid = await DataFetcher._check_symbol_search(symbol)
        if is_valid:
            return True
            
        # If all methods fail, use a common stock list fallback
        common_stocks = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'GOOG', 'FB', 'TSLA', 'NVDA', 'JPM', 'JNJ', 
                        'V', 'PG', 'UNH', 'HD', 'MA', 'BAC', 'DIS', 'ADBE', 'CRM', 'NFLX', 'CMCSA',
                        'PFE', 'CSCO', 'VZ', 'ABT', 'KO', 'PEP', 'TMO', 'ACN', 'AVGO', 'NKE']
        
        if symbol.upper() in common_stocks:
            logger.info(f"Symbol {symbol} validated against common stocks list")
            return True
        
        return False
    
    @staticmethod
    async def _check_alpha_vantage(symbol):
        """Check symbol validity using Alpha Vantage."""
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data:
            return False
            
        # Check if we got valid data or an error
        if "Global Quote" in data and data["Global Quote"] and "05. price" in data["Global Quote"]:
            logger.info(f"Symbol {symbol} validated with Alpha Vantage")
            return True
            
        return False
    
    @staticmethod
    async def _check_finnhub(symbol):
        """Check symbol validity using Finnhub."""
        from config import FINNHUB_API_KEY
        
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data:
            return False
            
        # Check if we got valid data with a price
        if "c" in data and data["c"] > 0:
            logger.info(f"Symbol {symbol} validated with Finnhub")
            return True
            
        return False
    
    @staticmethod
    async def _check_symbol_search(symbol):
        """Check symbol validity using Alpha Vantage symbol search."""
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data or "bestMatches" not in data:
            return False
            
        # Check if we have any exact matches
        for match in data["bestMatches"]:
            if match.get("1. symbol", "").upper() == symbol.upper():
                logger.info(f"Symbol {symbol} validated with Alpha Vantage symbol search")
                return True
                
        return False
    
    @staticmethod
    async def get_company_name(symbol):
        """Get the company name for a symbol."""
        # Try Alpha Vantage first
        company_name = await DataFetcher._get_company_name_alpha_vantage(symbol)
        if company_name:
            return company_name
            
        # Try Finnhub if Alpha Vantage fails
        company_name = await DataFetcher._get_company_name_finnhub(symbol)
        if company_name:
            return company_name
            
        # Fallback to symbol if all else fails
        return symbol
    
    @staticmethod
    async def _get_company_name_alpha_vantage(symbol):
        """Get company name using Alpha Vantage."""
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data or "Name" not in data:
            return None
            
        return data["Name"]
    
    @staticmethod
    async def _get_company_name_finnhub(symbol):
        """Get company name using Finnhub."""
        from config import FINNHUB_API_KEY
        
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data or "name" not in data:
            return None
            
        return data["name"]