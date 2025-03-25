# agents/manager.py
import json
import logging
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import OPENAI_API_KEY, MANAGER_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManagerAgent(Agent):
    """
    Manager agent responsible for coordinating other agents and creating task plans.
    """
    
    def __init__(self, task_manager):
        super().__init__("manager", "Coordinates tasks among specialized agents")
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY , base_url="https://api.deepseek.com")
        self.task_manager = task_manager
    
    async def create_analysis_plan(self, stock_symbol):
        """Create a plan for analyzing a stock."""
        prompt = f"""
        You are the manager of a stock analysis system. Create a detailed plan to analyze the stock {stock_symbol}.
        Your response should be a JSON object with a list of tasks in chronological order, where each task includes:
        1. The agent responsible (price_agent, financial_agent, news_agent, sentiment_agent, or report_agent)
        2. A description of what they should do
        3. The specific data they need to gather or analyze
        
        Example format:
        {{
            "plan": [
                {{
                    "agent": "price_agent",
                    "task": "Fetch current price data",
                    "details": "Retrieve real-time price, daily change, and trading volume for {stock_symbol}"
                }},
                ...
            ]
        }}
        
        Consider the following types of analysis:
        - Current price data and technical indicators
        - Financial metrics and recent earnings
        - Recent news and their impact
        - Market sentiment analysis
        - Report compilation and formatting
        
        Ensure the plan is comprehensive and will result in an actionable stock analysis report.
        """
        
        response = await self.client.chat.completions.create(
            model=MANAGER_MODEL,
            messages=[{"role": "system", "content": "You are a stock analysis planning system. Respond only with valid JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            plan = json.loads(response.choices[0].message.content)
            logger.info(f"Created analysis plan for {stock_symbol} with {len(plan['plan'])} tasks")
            return plan
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            raise
    
    async def process_task(self, task):
        """
        Process incoming tasks and distribute work to specialized agents.
        """
        task_data = self.parse_task(task)
        stock_symbol = task_data.get("stock_symbol")
        
        if not stock_symbol:
            return self.format_response("error", {}, "No stock symbol provided")
            
        # Create a detailed analysis plan
        try:
            plan = await self.create_analysis_plan(stock_symbol)
            task_ids = []
            
            # Add tasks to the task manager based on the plan
            for task_item in plan["plan"]:
                agent_name = task_item["agent"]
                task_details = {
                    "stock_symbol": stock_symbol,
                    "task": task_item["task"],
                    "details": task_item["details"]
                }
                task_id = self.task_manager.add_task(agent_name, task_details)
                task_ids.append(task_id)
            
            return self.format_response("success", {
                "stock_symbol": stock_symbol,
                "plan": plan["plan"],
                "task_ids": task_ids
            }, "Analysis plan created and tasks distributed")
            
        except Exception as e:
            logger.error(f"Error in manager agent: {str(e)}")
            return self.format_response("error", {}, f"Failed to process task: {str(e)}")   