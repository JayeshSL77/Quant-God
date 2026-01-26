
from typing import Dict, Any
from .base import BaseAgent
import json
import google.generativeai as genai
import os
from openai import OpenAI
from mistralai import Mistral

class RouterAgent(BaseAgent):
    """
    Agent responsible for classifying user intent and routing to specialized sub-agents.
    """
    
    def __init__(self):
        super().__init__(name="RouterAgent")
        
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self.openai_client = None
        self.gemini_client = None
        self.mistral_client = None
        
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
            else:
                self._log_activity("Warning: OPENAI_API_KEY not found.")
        elif self.provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            if api_key:
                self.mistral_client = Mistral(api_key=api_key)
            else:
                 self._log_activity("Warning: MISTRAL_API_KEY not found.")

        # Fallback or default to Gemini
        if not (self.openai_client or self.mistral_client):
            self.provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.gemini_client = genai.GenerativeModel('gemini-2.0-flash-exp')
            else:
                self._log_activity("Warning: GEMINI_API_KEY not found.")
        
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies query into: 'market_data', 'filings', or 'general'.
        """
        self._log_activity(f"Routing query: {query}")
        
        prompt = f"""
        You are a Router Agent for a Stock Analysis System.
        Classify the following user query into exactly one of these categories:
        
        1. "market_data": Questions about stock price, PE ratio, trends, volume, market cap, or simple quantitative stats.
        2. "filings": Questions about corporate announcements, board meetings, dividends, quarterly results, annual reports, or specific document content.
        3. "general": General greetings, investing advice, or questions not specific to fetching data.
        
        Examples:
        - "What is the price of Reliance?" -> market_data
        - "How has TCS performed this year?" -> market_data
        - "Did Infosys declare a dividend?" -> filings
        - "Summarize the recent board meeting." -> filings
        - "Hello, how are you?" -> general
        
        Query: "{query}"
        
        Return JSON only: {{ "category": "..." }}
        """
        
        try:
            category = "general"
            
            if self.provider == "openai" and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": prompt}],
                    temperature=0
                )
                text = response.choices[0].message.content
            elif self.provider == "mistral" and self.mistral_client:
                response = self.mistral_client.chat.complete(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.choices[0].message.content
            elif self.gemini_client:
                response = self.gemini_client.generate_content(prompt)
                text = response.text
            else:
                return {"response": "Error: No LLM configured", "data": {"category": "general"}}

            # Basic parsing
            text = text.strip().replace("```json", "").replace("```", "")
            if "{" in text:
                import json # ensure json imported if not at top
                try:
                    result = json.loads(text)
                    category = result.get("category", "general")
                except:
                    pass
            
            self._log_activity(f"Selected category: {category}")
            
            return {
                "response": "Routing...",
                "data": {"category": category},
                "source": "RouterAgent"
            }
        except Exception as e:
            self._log_activity(f"Error in routing: {e}")
            return {
                "response": "Error routing",
                "data": {"category": "general"}, # Default fallback
                "source": "RouterAgent"
            }
