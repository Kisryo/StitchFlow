"""
Z.AI GLM API Client.

Wrapper for Z.AI GLM-4.5/5.1 API with error handling and retry logic.
Supports both ZhipuAI SDK and Anthropic-compatible endpoints.
"""
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import requests

from config.settings import settings


class GLMClient:
    """
    Client for Z.AI GLM API.
    
    Handles API authentication, request formatting, and error handling.
    Supports Anthropic-compatible endpoints.
    """
    
    def __init__(self):
        """Initialize GLM client with API key and base URL from settings."""
        self.api_key = settings.zhipu_api_key
        self.model = settings.glm_model
        self.base_url = settings.glm_base_url
        
        # Determine if using Anthropic-compatible endpoint
        self.is_anthropic_compatible = "anthropic" in self.base_url.lower() if self.base_url else False
        
        print(f"[GLM Client] Initialized with:")
        print(f"  Model: {self.model}")
        print(f"  Base URL: {self.base_url}")
        print(f"  Anthropic-compatible: {self.is_anthropic_compatible}")
    
    @retry(
        stop=stop_after_attempt(2),  # Reduced from 3 to 2 attempts since each takes 120s
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send chat completion request to GLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            
        Returns:
            API response dict
            
        Raises:
            Exception: If API call fails after retries
        """
        print(f"[GLM Client] Attempting API call...")
        
        try:
            if self.is_anthropic_compatible:
                return self._anthropic_chat_completion(messages, temperature, max_tokens)
            else:
                return self._zhipuai_chat_completion(messages, temperature, max_tokens, response_format)
                
        except Exception as e:
            print(f"[GLM Client] API call failed: {str(e)}")
            raise Exception(f"GLM API call failed: {str(e)}")
    
    def _anthropic_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096
    ) -> Dict[str, Any]:
        """
        Make API call to Anthropic-compatible endpoint.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            API response dict
        """
        # Prepare request
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # Convert messages format if needed
        formatted_messages = []
        system_message = None
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096
        }
        
        if system_message:
            payload["system"] = system_message
        
        print(f"[GLM Client] Sending request to {url}")
        print(f"[GLM Client] Model: {self.model}")
        print(f"[GLM Client] Messages: {len(formatted_messages)}")
        
        # Make request with longer timeout (120 seconds for complex reasoning)
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            print(f"[GLM Client] Request timed out after 120 seconds")
            raise Exception("GLM API request timed out. The model is taking too long to respond. Please try again or use a shorter document.")
        except requests.exceptions.ConnectionError as e:
            print(f"[GLM Client] Connection error: {str(e)}")
            raise Exception(f"Failed to connect to GLM API: {str(e)}")
        except requests.exceptions.HTTPError as e:
            print(f"[GLM Client] HTTP error: {response.status_code} - {response.text}")
            raise Exception(f"GLM API returned error {response.status_code}: {response.text}")
        
        data = response.json()
        
        print(f"[GLM Client] Response received")
        print(f"[GLM Client] Content length: {len(data.get('content', [{}])[0].get('text', ''))}")
        
        # Extract response content
        result = {
            "content": data["content"][0]["text"],
            "model": data.get("model", self.model),
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
            },
            "finish_reason": data.get("stop_reason", "stop")
        }
        
        return result
    
    def _zhipuai_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make API call using ZhipuAI SDK.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            response_format: Optional response format specification
            
        Returns:
            API response dict
        """
        from zhipuai import ZhipuAI
        
        # Initialize client
        if self.base_url:
            client = ZhipuAI(api_key=self.api_key, base_url=self.base_url)
        else:
            client = ZhipuAI(api_key=self.api_key)
        
        # Prepare request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        if response_format:
            params["response_format"] = response_format
        
        # Make API call
        response = client.chat.completions.create(**params)
        
        # Extract response content
        result = {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "finish_reason": response.choices[0].finish_reason
        }
        
        return result
    
    def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Request structured JSON output from GLM.
        
        Args:
            messages: List of message dicts
            schema: JSON schema for response format
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON response
        """
        # Add schema instruction to system message
        schema_instruction = f"\n\nYou must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        
        # Add to last user message or create system message
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += schema_instruction
        else:
            messages.append({
                "role": "system",
                "content": f"Respond with valid JSON.{schema_instruction}"
            })
        
        # Request with JSON response format
        response = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=4096
        )
        
        # Parse JSON response
        try:
            content = response["content"]
            
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[GLM Client] Failed to parse JSON response: {str(e)}")
            print(f"[GLM Client] Response content: {response['content'][:500]}")
            raise Exception(f"Failed to parse GLM JSON response: {str(e)}\nResponse: {response['content'][:500]}")
    
    def simple_prompt(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Send a simple prompt and get text response.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            temperature: Sampling temperature
            
        Returns:
            Response text
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.chat_completion(messages=messages, temperature=temperature)
        return response["content"]


# Global GLM client instance
glm_client = GLMClient()
