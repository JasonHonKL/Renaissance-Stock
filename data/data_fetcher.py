# data/data_fetcher.py
import logging
import aiohttp
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
        """Check if a stock symbol is valid using Alpha Vantage."""
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data or "Global Quote" not in data or not data["Global Quote"]:
            return False
        
        return True
    
    @staticmethod
    async def get_company_name(symbol):
        """Get the company name for a symbol using Alpha Vantage."""
        from config import ALPHA_VANTAGE_API_KEY
        
        url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        data = await DataFetcher.fetch_json(url)
        
        if not data or "Name" not in data:
            return None
        
        return data["Name"]