# agents/price_agent.py
import json
import logging
import aiohttp
from datetime import datetime
from core.agent_interface import Agent
from config import ALPHA_VANTAGE_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceAgent(Agent):
    """Agent responsible for fetching real-time price data and technical indicators."""
    
    def __init__(self):
        super().__init__("price_agent", "Fetches real-time stock price data and technical indicators")
    
    async def fetch_price_data(self, symbol):
        """Fetch current price data from Alpha Vantage."""
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch price data: {response.status}")
                
                data = await response.json()
                if "Global Quote" not in data or not data["Global Quote"]:
                    raise Exception(f"No price data found for {symbol}")
                
                quote = data["Global Quote"]
                return {
                    "symbol": symbol,
                    "price": float(quote.get("05. price", 0)),
                    "change": float(quote.get("09. change", 0)),
                    "change_percent": quote.get("10. change percent", "0%"),
                    "volume": int(quote.get("06. volume", 0)),
                    "timestamp": datetime.now().isoformat(),
                }
    
    async def fetch_technical_indicators(self, symbol):
        """Fetch technical indicators from Alpha Vantage."""
        # SMA (Simple Moving Average)
        sma_url = f"https://www.alphavantage.co/query?function=SMA&symbol={symbol}&interval=daily&time_period=50&series_type=close&apikey={ALPHA_VANTAGE_API_KEY}"
        
        # RSI (Relative Strength Index)
        rsi_url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=daily&time_period=14&series_type=close&apikey={ALPHA_VANTAGE_API_KEY}"
        
        indicators = {}
        
        async with aiohttp.ClientSession() as session:
            # Fetch SMA
            async with session.get(sma_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "Technical Analysis: SMA" in data:
                        latest_date = list(data["Technical Analysis: SMA"].keys())[0]
                        indicators["sma_50"] = float(data["Technical Analysis: SMA"][latest_date]["SMA"])
            
            # Fetch RSI
            async with session.get(rsi_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "Technical Analysis: RSI" in data:
                        latest_date = list(data["Technical Analysis: RSI"].keys())[0]
                        indicators["rsi_14"] = float(data["Technical Analysis: RSI"][latest_date]["RSI"])
        
        return indicators
    
    async def process_task(self, task):
        """Process price data tasks."""
        task_data = self.parse_task(task)
        symbol = task_data.get("stock_symbol")
        
        if not symbol:
            return self.format_response("error", {}, "No stock symbol provided")
        
        try:
            # Fetch price data
            price_data = await self.fetch_price_data(symbol)
            
            # Fetch technical indicators
            technical_data = await self.fetch_technical_indicators(symbol)
            
            # Combine results
            result = {
                **price_data,
                "technical_indicators": technical_data
            }
            
            return self.format_response("success", result, f"Price data fetched for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in price agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to fetch price data: {str(e)}")