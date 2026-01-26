
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("Agent")

class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents in the Inwezt system.
    """
    
    def __init__(self, name: str, model: str = "gemini-1.5-flash"):
        self.name = name
        self.model = model
        self.logger = logging.getLogger(f"Agent.{name}")
    
    @abstractmethod
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the user query and return a result dictionary.
        Must return: {"response": str, "data": dict, "source": str}
        """
        pass
    
    def _log_activity(self, activity: str):
        self.logger.info(f"[{self.name}] {activity}")
