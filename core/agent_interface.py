# core/agent_interface.py
from abc import ABC, abstractmethod
import json

class Agent(ABC):
    """Base abstract class for all agents in the system."""
    
    def __init__(self, name, description):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def process_task(self, task):
        """Process a task and return the result."""
        pass
    
    def format_response(self, status, data, message=""):
        """Format the agent's response as a standardized JSON structure."""
        return json.dumps({
            "agent": self.name,
            "status": status,
            "message": message,
            "data": data
        })
    
    def parse_task(self, task_json):
        """Parse a JSON task input."""
        if isinstance(task_json, str):
            return json.loads(task_json)
        return task_json