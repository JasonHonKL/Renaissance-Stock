# core/task_manager.py
import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskManager:
    """Manages task distribution and execution among agents."""
    
    def __init__(self):
        self.agents = {}
        self.tasks_queue = []
        self.results = {}
    
    def register_agent(self, agent_name, agent_instance):
        """Register an agent with the task manager."""
        self.agents[agent_name] = agent_instance
        logger.info(f"Registered agent: {agent_name}")
        
    def add_task(self, agent_name, task_data, task_id=None):
        """Add a task to the queue."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        task = {
            "agent": agent_name,
            "data": task_data,
            "id": task_id or f"{agent_name}_{len(self.tasks_queue)}"
        }
        
        self.tasks_queue.append(task)
        logger.info(f"Added task {task['id']} for agent {agent_name}")
        return task["id"]
    
    async def execute_all_tasks(self):
        """Execute all tasks in the queue."""
        tasks = []
        for task in self.tasks_queue:
            agent_name = task["agent"]
            agent = self.agents[agent_name]
            tasks.append(self._execute_task(agent, task))
        
        results = await asyncio.gather(*tasks)
        self.tasks_queue = []
        return results
    
    async def _execute_task(self, agent, task):
        """Execute a single task."""
        logger.info(f"Executing task {task['id']} with agent {agent.name}")
        try:
            result = await agent.process_task(task["data"])
            self.results[task["id"]] = result
            logger.info(f"Task {task['id']} completed")
            return {"task_id": task["id"], "status": "completed", "result": result}
        except Exception as e:
            logger.error(f"Task {task['id']} failed: {str(e)}")
            return {"task_id": task["id"], "status": "failed", "error": str(e)}