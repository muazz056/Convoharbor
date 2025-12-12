# chat_project/app/services/llm_service.py

import os
import json
from typing import Optional
from flask import current_app
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import json


class LLMService:
    def __init__(self):
        """Initialize LLM service with Helicone observability support."""
        self.openai_client = None
        self.gemini_client = None
        
        # Get API keys
        openai_key = current_app.config.get('OPENAI_API_KEY')
        gemini_key = current_app.config.get('GEMINI_API_KEY')
        
        # Helicone Configuration
        self.helicone_enabled = current_app.config.get('HELICONE_ENABLED', False)
        self.helicone_key = current_app.config.get('HELICONE_API_KEY')
        
        # Initialize OpenAI with Helicone proxy if enabled, with fallback to direct
        if openai_key and not openai_key.startswith('your-'):
            self.openai_client = None
            self.openai_direct_client = None
            
            # Try Helicone first if enabled
            if self.helicone_enabled:
                try:
                    client_args = {
                        "api_key": openai_key,
                        "model": current_app.config.get('DEFAULT_OPENAI_MODEL'),
                        "temperature": 0.3,  # Optimized for faster responses
                        "max_tokens": 500,   # Limit response length for speed
                        "timeout": 60,
                        "base_url": "https://oai.helicone.ai/v1",
                        "default_headers": {
                            "Helicone-Auth": f"Bearer {self.helicone_key}",
                            "Content-Type": "application/json"
                        }
                    }

                    self.openai_client = ChatOpenAI(**client_args)
                    current_app.logger.info("✅ Helicone observability ENABLED for OpenAI")
                    current_app.logger.info(f"🔗 Using Helicone base URL: https://oai.helicone.ai/v1")
                    
                    # Test Helicone connection
                    test_response = self.openai_client.invoke("Hello")
                    current_app.logger.info("✅ Helicone connection test successful")
                    
                except Exception as e:
                    current_app.logger.warning(f"⚠️ Helicone initialization failed: {e}")
                    if "unsupported_country_region_territory" in str(e):
                        current_app.logger.warning("🌍 Helicone blocked in your region, falling back to direct OpenAI")
                    self.openai_client = None
            
            # Create direct OpenAI client (always available as fallback)
            try:
                direct_args = {
                    "api_key": openai_key,
                    "model": current_app.config.get('DEFAULT_OPENAI_MODEL'),
                    "temperature": 0.3,  # Optimized for faster responses
                    "max_tokens": 500,   # Limit response length for speed
                    "timeout": 60
                }

                self.openai_direct_client = ChatOpenAI(**direct_args)
                current_app.logger.info("✅ Direct OpenAI client created successfully")
                
                # If Helicone failed, use direct as primary
                if not self.openai_client:
                    self.openai_client = self.openai_direct_client
                    current_app.logger.info("🔄 Using direct OpenAI connection (Helicone unavailable)")

            except Exception as e:
                current_app.logger.error(f"❌ Direct OpenAI initialization failed: {e}")
                self.openai_direct_client = None

        else:
            current_app.logger.warning("⚠️ OpenAI API key not configured or is placeholder")
            
        # Initialize Gemini
        if gemini_key and not gemini_key.startswith('your-'):
            try:
                current_app.logger.info(f"🔑 Initializing Gemini with key: {gemini_key[:10]}...{gemini_key[-4:] if len(gemini_key) > 14 else ''}")
                self.gemini_client = ChatGoogleGenerativeAI(
                    google_api_key=gemini_key,
                    model=current_app.config.get('DEFAULT_GEMINI_MODEL', 'models/gemini-pro'),
                    temperature=0.3,      # Optimized for faster responses
                    max_output_tokens=500,  # Limit response length for speed (Gemini uses max_output_tokens)
                    timeout=60
                )
                current_app.logger.info("✅ Gemini client created successfully")
                
                # Test the connection immediately
                try:
                    test_response = self.gemini_client.invoke("Hello")
                    current_app.logger.info(f"✅ Gemini connection test successful: {test_response.content[:50]}...")
                except Exception as test_error:
                    current_app.logger.error(f"⚠️ Gemini connection test failed: {test_error}")
                    # Don't set to None, let it try during actual use
                    
            except Exception as e:
                current_app.logger.error(f"❌ Gemini initialization failed: {e}")
                current_app.logger.error(f"❌ Error type: {type(e).__name__}")
                current_app.logger.error(f"❌ Key length: {len(gemini_key) if gemini_key else 0}")
                self.gemini_client = None
        else:
            if not gemini_key:
                current_app.logger.warning("⚠️ Gemini API key not found in config")
            elif gemini_key.startswith('your-'):
                current_app.logger.warning(f"⚠️ Gemini API key appears to be placeholder: {gemini_key}")
            else:
                current_app.logger.warning("⚠️ Gemini API key validation failed")

        # Log service status
        if self.openai_client and self.gemini_client:
            provider_info = "OpenAI + Gemini"
            if self.helicone_enabled:
                provider_info += " (with Helicone observability)"
            current_app.logger.info(f"LLMService: {provider_info} providers configured.")
        elif self.openai_client:
            provider_info = "OpenAI only"
            if self.helicone_enabled:
                provider_info += " (with Helicone observability)"
            current_app.logger.info(f"LLMService: {provider_info} provider configured.")
        elif self.gemini_client:
            current_app.logger.info("LLMService: Gemini only provider configured.")
        else:
            current_app.logger.warning("LLMService: No LLM providers configured!")

        if not self.openai_client and not self.gemini_client:
            current_app.logger.error("❌ CRITICAL: No LLM clients are available. All AI services will fail.")

    def generate_answer(self, messages: list, model_name: str, user_id: str = None, tenant_id: str = None) -> Optional[dict]:
        """
        Generate an answer using the specified LLM, with Helicone logging.
        """
        # Fast model normalization with early return for common cases
        if model_name.startswith('models/gemini-2.') or model_name.startswith('gpt-'):
            # Already in correct format, skip expensive checks
            pass
        else:
            # Handle model format corrections and fallbacks only when needed
            original_model = model_name
            
            # Use set for O(1) lookup instead of list
            deprecated_models = {
                'models/gemini-pro', 'models/gemini-1.5-pro', 'models/gemini-1.5-flash',
                'gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash',
                'models/gemini-1.5-pro-latest', 'models/gemini-1.5-flash-latest'
            }
            
            if model_name in deprecated_models:
                model_name = 'models/gemini-2.5-flash'  # Use latest working model with models/ prefix
                # current_app.logger.warning(f"⚠️ Model fallback: {original_model} -> {model_name} (using latest working model)")
            elif model_name.startswith('gemini-') and not model_name.startswith('models/'):
                # Add models/ prefix for ALL Gemini models (langchain requirement)
                model_name = f'models/{model_name}'
                # current_app.logger.warning(f"⚠️ Model format correction: {original_model} -> {model_name} (added models/ prefix - langchain requirement)")
        
        # Determine which client to use
        client = None
        if 'gpt' in model_name and self.openai_client:
            client = self.openai_client
        elif 'gemini' in model_name and self.gemini_client:
            client = self.gemini_client
            # For Gemini, dynamically set the model for this request
            original_client_model = client.model
            client.model = model_name

        if not client:
            current_app.logger.error(f"No client available for model: {model_name}")
            return None

        try:
            # Prepare invocation arguments
            invocation_args = {
                "input": messages
            }

            # Add Helicone properties to the request if enabled and using Helicone client
            using_helicone = (self.helicone_enabled and isinstance(client, ChatOpenAI) and 
                            hasattr(client, 'default_headers') and 
                            client.default_headers and 
                            'Helicone-Auth' in str(client.default_headers))
            
            if using_helicone:
                helicone_headers = {
                    "Helicone-Property-TenantId": tenant_id,
                    "Helicone-User-Id": user_id
                }
                # Filter out None values
                helicone_headers = {k: v for k, v in helicone_headers.items() if v is not None}
                
                # Add headers to the client for this specific call
                original_headers = client.default_headers
                client.default_headers = {**original_headers, **helicone_headers}
                
                current_app.logger.info(f"Adding Helicone headers: {helicone_headers}")

            response = client.invoke(**invocation_args)

            # Reset headers if modified
            if 'original_headers' in locals():
                client.default_headers = original_headers

            # Reset Gemini model if we changed it
            if 'gemini' in model_name and 'original_client_model' in locals():
                client.model = original_client_model

            return {
                "content": response.content,
                "usage": {
                    "prompt_tokens": response.usage_metadata.get('prompt_tokens', 0) if response.usage_metadata else 0,
                    "completion_tokens": response.usage_metadata.get('completion_tokens', 0) if response.usage_metadata else 0,
                    "total_tokens": response.usage_metadata.get('total_tokens', 0) if response.usage_metadata else 0,
                }
            }
        except Exception as e:
            current_app.logger.error(f"Error during LLM call to {model_name}: {e}")
            
            # Reset headers in case of an error
            if 'original_headers' in locals() and client:
                client.default_headers = original_headers
            
            # Reset Gemini model in case of an error
            if 'gemini' in model_name and 'original_client_model' in locals() and client:
                client.model = original_client_model
            
            # If using Helicone and got region error, try direct fallback
            if ('gpt' in model_name and "unsupported_country_region_territory" in str(e) and 
                hasattr(self, 'openai_direct_client') and self.openai_direct_client and
                client != self.openai_direct_client):
                
                current_app.logger.warning("🔄 Helicone blocked, trying direct OpenAI fallback...")
                try:
                    # Use direct client without Helicone headers
                    response = self.openai_direct_client.invoke(**invocation_args)
                    current_app.logger.info("✅ Direct OpenAI fallback successful")
                    
                    return {
                        "content": response.content,
                        "usage": {
                            "prompt_tokens": response.usage_metadata.get('prompt_tokens', 0) if response.usage_metadata else 0,
                            "completion_tokens": response.usage_metadata.get('completion_tokens', 0) if response.usage_metadata else 0,
                            "total_tokens": response.usage_metadata.get('total_tokens', 0) if response.usage_metadata else 0,
                        }
                    }
                except Exception as fallback_error:
                    current_app.logger.error(f"❌ Direct OpenAI fallback also failed: {fallback_error}")
            
            return None

    def _generate_demo_response(self, reason: str) -> str:
        """Generate a demo response when LLM services are unavailable."""
        current_app.logger.info(f"🎮 DEMO MODE: {reason}")
        return f"I'm currently in demo mode. {reason}. Please check your API configuration."

    def is_available(self, provider: str = None) -> bool:
        """Check if LLM service is available."""
        if provider == 'openai':
            return self.openai_client is not None
        elif provider == 'gemini':
            return self.gemini_client is not None
        else:
            return self.openai_client is not None or self.gemini_client is not None

    def get_helicone_status(self) -> dict:
        """Get Helicone integration status."""
        return {
            "enabled": self.helicone_enabled,
            "auth_configured": bool(self.helicone_key),
            "openai_proxied": self.helicone_enabled and self.openai_client is not None,
            "proxy_url": "https://oai.helicone.ai/v1" if self.helicone_enabled else None,
            "fallback_available": hasattr(self, 'openai_direct_client') and self.openai_direct_client is not None
        }