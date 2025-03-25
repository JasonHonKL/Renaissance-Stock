# agents/report_agent.py
import json
import logging
import re
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import OPENAI_API_KEY, MANAGER_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportAgent(Agent):
    """Agent responsible for generating the final stock analysis report."""
    
    def __init__(self):
        super().__init__("report_agent", "Generates comprehensive stock analysis reports")
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY , base_url="https://api.deepseek.com")
    
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
    
    async def generate_report(self, stock_data):
        """Generate a comprehensive stock analysis report using all collected data."""
        # Extract data components
        symbol = stock_data.get("symbol", "")
        price_data = stock_data.get("price_data", {})
        company_profile = stock_data.get("financial_data", {}).get("company_profile", {})
        financial_metrics = stock_data.get("financial_data", {}).get("financial_metrics", {})
        earnings = stock_data.get("financial_data", {}).get("recent_earnings", [])
        news_data = stock_data.get("news_data", {})
        sentiment_data = stock_data.get("sentiment_data", {})
        
        prompt = f"""
        Create a comprehensive stock analysis report for {symbol} ({company_profile.get('name', '')}) 
        based on the following data:
        
        1. Price Data:
        - Current Price: ${price_data.get('price', 'N/A')}
        - Change: {price_data.get('change_percent', 'N/A')}
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
        Include a summary box at the top with the recommendation and key metrics.
        For styling you should be careful as the content will be instert inside a div. Don't shirk or enlarge which will cause problem of display.
        Do not include any markdown code blocks or explanations outside of the HTML - just provide clean HTML.
        """
        
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
        
        # Create a structured report object
        report = {
            "symbol": symbol,
            "company_name": company_profile.get('name', symbol),
            "timestamp": price_data.get('timestamp', ''),
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