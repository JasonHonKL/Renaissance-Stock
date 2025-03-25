# agents/financial_agent.py
import json
import logging
import aiohttp
from core.agent_interface import Agent
from config import FINNHUB_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialAgent(Agent):
    """Agent responsible for analyzing financial metrics and company fundamentals."""
    
    def __init__(self):
        super().__init__("financial_agent", "Analyzes financial metrics and company fundamentals")
    
    async def fetch_company_profile(self, symbol):
        """Fetch company profile from Finnhub."""
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch company profile: {response.status}")
                
                data = await response.json()
                if not data:
                    raise Exception(f"No company profile found for {symbol}")
                
                return {
                    "name": data.get("name", ""),
                    "market_cap": data.get("marketCapitalization", 0),
                    "industry": data.get("finnhubIndustry", ""),
                    "exchange": data.get("exchange", ""),
                    "ipo": data.get("ipo", ""),
                    "logo": data.get("logo", ""),
                    "website": data.get("weburl", "")
                }
    
    async def fetch_financial_metrics(self, symbol):
        """Fetch financial metrics from Finnhub."""
        url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={FINNHUB_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch financial metrics: {response.status}")
                
                data = await response.json()
                if not data or "metric" not in data:
                    raise Exception(f"No financial metrics found for {symbol}")
                
                metrics = data["metric"]
                return {
                    "pe_ratio": metrics.get("peNormalizedAnnual", None),
                    "pb_ratio": metrics.get("pbAnnual", None),
                    "dividend_yield": metrics.get("dividendYieldIndicatedAnnual", None),
                    "roe": metrics.get("roeRfy", None),
                    "eps_growth": metrics.get("epsGrowth5Y", None),
                    "debt_to_equity": metrics.get("totalDebtToEquityQuarterly", None),
                    "current_ratio": metrics.get("currentRatioQuarterly", None)
                }
    
    async def fetch_earnings(self, symbol):
        """Fetch recent earnings from Finnhub."""
        url = f"https://finnhub.io/api/v1/stock/earnings?symbol={symbol}&token={FINNHUB_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch earnings: {response.status}")
                
                data = await response.json()
                if not data:
                    return []
                
                # Return the most recent 4 quarters
                recent_earnings = data[:4]
                formatted_earnings = []
                
                for quarter in recent_earnings:
                    formatted_earnings.append({
                        "period": quarter.get("period", ""),
                        "actual_eps": quarter.get("actual", None),
                        "estimated_eps": quarter.get("estimate", None),
                        "surprise": quarter.get("surprise", None),
                        "surprise_percent": quarter.get("surprisePercent", None)
                    })
                
                return formatted_earnings
    
    async def process_task(self, task):
        """Process financial analysis tasks."""
        task_data = self.parse_task(task)
        symbol = task_data.get("stock_symbol")
        
        if not symbol:
            return self.format_response("error", {}, "No stock symbol provided")
        
        try:
            # Fetch company profile
            profile = await self.fetch_company_profile(symbol)
            
            # Fetch financial metrics
            metrics = await self.fetch_financial_metrics(symbol)
            
            # Fetch recent earnings
            earnings = await self.fetch_earnings(symbol)
            
            # Combine results
            result = {
                "symbol": symbol,
                "company_profile": profile,
                "financial_metrics": metrics,
                "recent_earnings": earnings
            }
            
            return self.format_response("success", result, f"Financial data analyzed for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in financial agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to analyze financial data: {str(e)}")