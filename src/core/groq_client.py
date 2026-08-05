import os
from dotenv import load_dotenv
from groq import Groq, BadRequestError, RateLimitError

# Load environment variables from .env file if available
load_dotenv()

class GroqClient:
    """Wrapper class for interacting with the Groq API with automatic model fallback."""

    def __init__(self, api_key: str = None, default_model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Please set it in your environment or in a .env file."
            )
        self.client = Groq(api_key=self.api_key)
        self.default_model = default_model
        self.fallback_models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama3-8b-8192"]

    def evaluate(self, system_prompt: str, user_prompt: str, model: str = None, json_mode: bool = False) -> str:
        """
        Send a chat completion request to the Groq API.
        Automatically retries with lightweight fallback models if rate limits are hit.
        """
        models_to_try = [model or self.default_model] + [m for m in self.fallback_models if m != (model or self.default_model)]
        
        last_error = None
        for current_model in models_to_try:
            try:
                kwargs = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "model": current_model,
                    "temperature": 0.2,
                }
                
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except (RateLimitError, BadRequestError) as e:
                err_msg = str(e)
                if "rate_limit" in err_msg.lower() or "429" in err_msg or "tpd" in err_msg.lower():
                    print(f"⚠️ Model '{current_model}' hit Groq rate limit. Falling back to alternative model...")
                    last_error = e
                    continue
                else:
                    raise e
            except Exception as e:
                raise e

        raise RuntimeError(f"All Groq models failed due to rate limits: {last_error}")
