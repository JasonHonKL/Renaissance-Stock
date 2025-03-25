# agents/sentiment_agent.py
import json
import logging
import aiohttp
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import FINNHUB_API_KEY, OPENAI_API_KEY, AGENT_MODEL,BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentimentAgent(Agent):
    """Agent responsible for analyzing market sentiment and social media trends."""
    
    def __init__(self):
        super().__init__("sentiment_agent", "Analyzes market sentiment and social media trends")
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY , base_url=BASE_URL)
    
    async def fetch_social_sentiment(self, symbol):
        """Fetch social sentiment data from Finnhub."""
        url = f"https://finnhub.io/api/v1/stock/social-sentiment?symbol={symbol}&from=2022-01-01&token={FINNHUB_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch social sentiment: {response.status}")
                
                data = await response.json()
                if not data:
                    return {"reddit": [], "twitter": []}
                
                # Process and aggregate sentiment data
                reddit_data = data.get("reddit", [])
                twitter_data = data.get("twitter", [])
                
                # Calculate average sentiment scores
                reddit_sentiment = 0
                if reddit_data:
                    reddit_sentiment = sum(item.get("score", 0) for item in reddit_data) / len(reddit_data)
                
                twitter_sentiment = 0
                if twitter_data:
                    twitter_sentiment = sum(item.get("score", 0) for item in twitter_data) / len(twitter_data)
                
                # Get mention counts
                reddit_mentions = sum(item.get("mention", 0) for item in reddit_data)
                twitter_mentions = sum(item.get("mention", 0) for item in twitter_data)
                
                return {
                    "reddit_sentiment": round(reddit_sentiment, 2),
                    "twitter_sentiment": round(twitter_sentiment, 2),
                    "reddit_mentions": reddit_mentions,
                    "twitter_mentions": twitter_mentions
                }
    
    async def fetch_analyst_ratings(self, symbol):
        """Fetch analyst ratings from Finnhub."""
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={FINNHUB_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch analyst ratings: {response.status}")
                
                data = await response.json()
                if not data:
                    return {}
                
                # Get the most recent ratings period
                latest_rating = data[0] if data else {}
                
                return {
                    "period": latest_rating.get("period", ""),
                    "buy": latest_rating.get("buy", 0),
                    "hold": latest_rating.get("hold", 0),
                    "sell": latest_rating.get("sell", 0),
                    "strong_buy": latest_rating.get("strongBuy", 0),
                    "strong_sell": latest_rating.get("strongSell", 0)
                }
    
    async def analyze_sentiment_data(self, symbol, social_sentiment, analyst_ratings):
        """Analyze sentiment data using LLM."""
        prompt = f"""
        Analyze the following sentiment data for {symbol}:
        
        Social Media Sentiment:
        - Reddit: {social_sentiment.get('reddit_sentiment', 'N/A')} (mentions: {social_sentiment.get('reddit_mentions', 'N/A')})
        - Twitter: {social_sentiment.get('twitter_sentiment', 'N/A')} (mentions: {social_sentiment.get('twitter_mentions', 'N/A')})
        
        Analyst Ratings (Period: {analyst_ratings.get('period', 'N/A')}):
        - Strong Buy: {analyst_ratings.get('strong_buy', 'N/A')}
        - Buy: {analyst_ratings.get('buy', 'N/A')}
        - Hold: {analyst_ratings.get('hold', 'N/A')}
        - Sell: {analyst_ratings.get('sell', 'N/A')}
        - Strong Sell: {analyst_ratings.get('strong_sell', 'N/A')}
        
        Provide the following in JSON format:
        1. market_sentiment: The overall market sentiment (bullish, bearish, or neutral)
        2. highlights: 2-3 key highlights from the sentiment data
        3. recommendation: A brief recommendation based on sentiment analysis
        
        Response format:
        {{
            "market_sentiment": "bullish/bearish/neutral",
            "highlights": ["highlight 1", "highlight 2", "highlight 3"],
            "recommendation": "brief recommendation..."
        }}
        """
        
        response = await self.client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[{"role": "system", "content": "You are a market sentiment analyst. Respond only with valid JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sentiment analysis JSON: {e}")
            return {"market_sentiment": "neutral", "highlights": [], "recommendation": "Error analyzing sentiment data."}
    
    async def process_task(self, task):
        """Process sentiment analysis tasks."""
        task_data = self.parse_task(task)
        symbol = task_data.get("stock_symbol")
        
        if not symbol:
            return self.format_response("error", {}, "No stock symbol provided")
        
        try:
            # Fetch social sentiment
            social_sentiment = await self.fetch_social_sentiment(symbol)
            
            # Fetch analyst ratings
            analyst_ratings = await self.fetch_analyst_ratings(symbol)
            
            # Analyze sentiment data
            sentiment_analysis = await self.analyze_sentiment_data(symbol, social_sentiment, analyst_ratings)
            
            # Combine results
            result = {
                "symbol": symbol,
                "social_sentiment": social_sentiment,
                "analyst_ratings": analyst_ratings,
                "analysis": sentiment_analysis
            }
            
            return self.format_response("success", result, f"Sentiment analyzed for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in sentiment agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to analyze sentiment: {str(e)}")