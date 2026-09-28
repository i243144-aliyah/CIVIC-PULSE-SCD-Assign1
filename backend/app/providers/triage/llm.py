import os
from google import genai
from google.genai import types
from app.schemas.triage import TriageResult  # Your Pydantic model

class GeminiTriageProvider:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Initialize Google GenAI client
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def triage(self, text: str, location: str) -> TriageResult:
        prompt = f"""
        Analyze the following civic complaint and categorize it:
        Location: {location}
        Complaint: {text}
        
        Rules:
        1. Category must be one of: water, electricity, sanitation, roads, streetlights, other.
        2. Priority must be one of: high, normal, low.
        3. Summary must be <= 140 characters.
        4. Confidence must be between 0.0 and 1.0.
        """

        # Enforce structured Pydantic output using Gemini's response_schema
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TriageResult,
                temperature=0.1,
            ),
        )

        # Parse and return as Pydantic instance
        return TriageResult.model_validate_json(response.text)