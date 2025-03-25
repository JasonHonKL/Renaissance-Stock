# agents/news_agent.py
import json
import logging
import aiohttp
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import NEWS_API_KEY, OPENAI_API_KEY, AGENT_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsAgent(Agent):
    """Agent responsible for gathering and analyzing news about a stock."""
    
    def __init__(self):
        super().__init__("news_agent", "Gathers and analyzes recent news about stocks")
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY , base_url="https://api.deepseek.com")
    
    async def fetch_news(self, symbol, company_name=None):
        """Fetch recent news articles about the stock."""
        # Calculate date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Format dates for the API
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        
        # Search query (using both symbol and company name if available)
        query = symbol
        if company_name:
            query = f"{symbol} OR {company_name}"
        
        url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&to={to_date}&language=en&sortBy=relevancy&pageSize=10&apiKey={NEWS_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch news: {response.status}")
                
                data = await response.json()
                if data.get("status") != "ok":
                    raise Exception(f"News API error: {data.get('message', 'Unknown error')}")
                
                articles = data.get("articles", [])
                if not articles:
                    return []
                
                # Format articles
                formatted_articles = []
                for article in articles:
                    formatted_articles.append({
                        "title": article.get("title", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "published_at": article.get("publishedAt", ""),
                        "url": article.get("url", ""),
                        "description": article.get("description", "")
                    })
                
                return formatted_articles
    
    async def analyze_news_sentiment(self, articles, symbol):
        """Analyze the sentiment and key points from news articles."""
        if not articles:
            return {"overall_sentiment": "neutral", "key_points": [], "impact_analysis": "No recent news to analyze."}
        
        # Prepare articles for analysis
        articles_text = ""
        for i, article in enumerate(articles[:5]):  # Analyze top 5 articles
            articles_text += f"Article {i+1}: {article['title']}\n"
            articles_text += f"Source: {article['source']}\n"
            articles_text += f"Description: {article['description']}\n\n"
        
        prompt = f"""
        Analyze the following recent news articles about {symbol}:
        
        {articles_text}
        
        Provide the following in JSON format:
        1. overall_sentiment: The overall sentiment toward the stock (positive, negative, or neutral)
        2. key_points: A list of 3-5 key points from the news articles
        3. impact_analysis: A brief analysis of how these news items might impact the stock
        
        Response format:
        {{
            "overall_sentiment": "positive/negative/neutral",
            "key_points": ["point 1", "point 2", "point 3"],
            "impact_analysis": "brief analysis..."
        }}
        """
        
        response = await self.client.chat.completions.create(
            model=AGENT_MODEL,
            messages=[{"role": "system", "content": "You are a financial news analyst. Respond only with valid JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
            return analysis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sentiment analysis JSON: {e}")
            return {"overall_sentiment": "neutral", "key_points": [], "impact_analysis": "Error analyzing news sentiment."}
    
    async def process_task(self, task):
        """Process news analysis tasks."""
        task_data = self.parse_task(task)
        symbol = task_data.get("stock_symbol")
        company_name = task_data.get("company_name", None)
        
        if not symbol:
            return self.format_response("error", {}, "No stock symbol provided")
        
        try:
            # Fetch recent news
            news_articles = await self.fetch_news(symbol, company_name)
            
            # Analyze news sentiment
            news_analysis = await self.analyze_news_sentiment(news_articles, symbol)
            
            # Combine results
            result = {
                "symbol": symbol,
                "articles": news_articles,
                "analysis": news_analysis
            }
            
            return self.format_response("success", result, f"News analyzed for {symbol}")
            
        except Exception as e:
            logger.error(f"Error in news agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to analyze news: {str(e)}")