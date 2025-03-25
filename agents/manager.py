# agents/manager.py
import json
import logging
import traceback
import time
from openai import AsyncOpenAI
from core.agent_interface import Agent
from config import OPENAI_API_KEY, MANAGER_MODEL, BASE_URL

# Configure more detailed logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler("manager_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create a performance logger
perf_logger = logging.getLogger("manager_performance")
perf_logger.setLevel(logging.INFO)

class ManagerAgent(Agent):
    """
    Manager agent responsible for coordinating other agents and creating task plans.
    """
    
    def __init__(self, task_manager):
        super().__init__("manager", "Coordinates tasks among specialized agents")
        # Let's use a property to create the client on demand
        self._client = None
        self.task_manager = task_manager
    
    @property
    def client(self):
        """Get or create an OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=BASE_URL,
                api_key=OPENAI_API_KEY,
                timeout=30.0,
                max_retries=2
            )
        return self._client
    
    async def create_analysis_plan(self, stock_symbol, request_id=None):
        """Create a plan for analyzing a stock."""
        if not request_id:
            request_id = f"plan-{int(time.time())}"
            
        logger.info(f"[{request_id}] Creating analysis plan for stock: {stock_symbol}")
        
        start_time = time.time()
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
        
        logger.debug(f"[{request_id}] Sending plan generation prompt to LLM for {stock_symbol}")
        
        try:
            api_start = time.time()
            response = await self.client.chat.completions.create(
                model=MANAGER_MODEL,
                messages=[
                    {"role": "system", "content": "You are a stock analysis planning system. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            api_end = time.time()
            api_duration = api_end - api_start
            perf_logger.info(f"[{request_id}] LLM API call completed in {api_duration:.2f} seconds")
            
            response_content = response.choices[0].message.content
            logger.debug(f"[{request_id}] Raw response from LLM: {response_content[:500]}...")
            
            try:
                plan = json.loads(response_content)
                plan_tasks = len(plan.get('plan', []))
                logger.info(f"[{request_id}] Created analysis plan for {stock_symbol} with {plan_tasks} tasks")
                
                # Log each task in the plan
                for i, task in enumerate(plan.get('plan', [])):
                    logger.debug(f"[{request_id}] Plan task {i+1}: {task.get('agent')} - {task.get('task')}")
                
                end_time = time.time()
                total_duration = end_time - start_time
                perf_logger.info(f"[{request_id}] Analysis plan creation completed in {total_duration:.2f} seconds")
                
                return plan
            except json.JSONDecodeError as e:
                logger.error(f"[{request_id}] Failed to parse plan JSON: {e}")
                logger.error(f"[{request_id}] Invalid JSON response: {response_content}")
                raise
                
        except Exception as e:
            logger.error(f"[{request_id}] Error creating analysis plan for {stock_symbol}: {str(e)}")
            logger.error(traceback.format_exc())
            end_time = time.time()
            total_duration = end_time - start_time
            perf_logger.info(f"[{request_id}] Analysis plan creation failed after {total_duration:.2f} seconds")
            raise
    
    async def process_task(self, task):
        """
        Process incoming tasks and distribute work to specialized agents.
        """
        request_id = f"manager-{int(time.time())}"
        logger.info(f"[{request_id}] Processing manager task")
        logger.debug(f"[{request_id}] Task data: {task}")
        
        start_time = time.time()
        
        try:
            task_data = self.parse_task(task)
            stock_symbol = task_data.get("stock_symbol")
            company_name = task_data.get("company_name", "Unknown Company")
            
            logger.info(f"[{request_id}] Processing task for {stock_symbol} ({company_name})")
            
            if not stock_symbol:
                logger.warning(f"[{request_id}] No stock symbol provided in task data")
                return self.format_response("error", {}, "No stock symbol provided")
                
            # Create a detailed analysis plan
            try:
                logger.info(f"[{request_id}] Creating analysis plan for {stock_symbol}")
                plan = await self.create_analysis_plan(stock_symbol, request_id)
                
                if not plan or "plan" not in plan:
                    logger.error(f"[{request_id}] Invalid plan structure received")
                    return self.format_response("error", {}, "Invalid analysis plan structure")
                
                task_ids = []
                
                # Add tasks to the task manager based on the plan
                logger.info(f"[{request_id}] Adding {len(plan['plan'])} tasks to task manager")
                for i, task_item in enumerate(plan["plan"]):
                    agent_name = task_item["agent"]
                    logger.debug(f"[{request_id}] Creating task {i+1} for agent: {agent_name}")
                    
                    task_details = {
                        "stock_symbol": stock_symbol,
                        "company_name": company_name,
                        "task": task_item["task"],
                        "details": task_item["details"],
                        "request_id": request_id
                    }
                    
                    try:
                        task_id = self.task_manager.add_task(agent_name, task_details)
                        task_ids.append(task_id)
                        logger.debug(f"[{request_id}] Task created with ID: {task_id}")
                    except Exception as e:
                        logger.error(f"[{request_id}] Failed to create task for {agent_name}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                end_time = time.time()
                total_duration = end_time - start_time
                perf_logger.info(f"[{request_id}] Manager task processing completed in {total_duration:.2f} seconds")
                
                result = {
                    "stock_symbol": stock_symbol,
                    "company_name": company_name,
                    "plan": plan["plan"],
                    "task_ids": task_ids,
                    "task_count": len(task_ids)
                }
                
                logger.info(f"[{request_id}] Successfully created {len(task_ids)} tasks for {stock_symbol}")
                return self.format_response("success", result, "Analysis plan created and tasks distributed")
                
            except Exception as e:
                logger.error(f"[{request_id}] Error creating analysis plan: {str(e)}")
                logger.error(traceback.format_exc())
                return self.format_response("error", {"stock_symbol": stock_symbol}, f"Failed to create analysis plan: {str(e)}")
                
        except Exception as e:
            logger.error(f"[{request_id}] Error in manager agent: {str(e)}")
            logger.error(traceback.format_exc())
            
            end_time = time.time()
            total_duration = end_time - start_time
            perf_logger.info(f"[{request_id}] Manager task processing failed after {total_duration:.2f} seconds")
            
            return self.format_response("error", {}, f"Failed to process task: {str(e)}")
    
    def parse_task(self, task):
        """Parse the incoming task data with better error handling."""
        request_id = task.get("request_id", f"parse-{int(time.time())}")
        
        try:
            if isinstance(task, str):
                logger.debug(f"[{request_id}] Parsing task from string: {task[:100]}...")
                return json.loads(task)
            return task
        except json.JSONDecodeError as e:
            logger.error(f"[{request_id}] Failed to parse task JSON: {e}")
            logger.error(f"[{request_id}] Invalid task data: {task[:200]}...")
            return {}
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error parsing task: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
    
    def format_response(self, status, data, message=""):
        """Format the response with consistent structure and logging."""
        response = {
            "agent": self.name,
            "status": status,
            "data": data,
            "message": message
        }
        
        if status == "success":
            logger.info(f"Manager response: {message}")
        else:
            logger.error(f"Manager error response: {message}")
            
        return json.dumps(response)