from typing import Optional
from flask import current_app
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from groq import Groq


PROVIDER_API_TYPE_MAP = {
    'openai': 'openai',
    'claude': 'anthropic',
    'gemini': 'gemini',
    'groq': 'groq',
    'qwen': 'openai',
    'deepseek': 'openai',
    'mistral': 'openai',
    'xai': 'openai',
    'together': 'openai',
    'perplexity': 'openai',
    'openrouter': 'openai',
}


class LLMService:
    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        self.groq_client = None

        openai_key = current_app.config.get('OPENAI_API_KEY')
        gemini_key = current_app.config.get('GEMINI_API_KEY')
        groq_key = current_app.config.get('GROQ_API_KEY')

        if openai_key and not openai_key.startswith('your-'):
            try:
                self.openai_client = ChatOpenAI(
                    api_key=openai_key,
                    model=current_app.config.get('DEFAULT_OPENAI_MODEL'),
                    temperature=0.3,
                    max_tokens=500,
                    timeout=60
                )
                current_app.logger.info("OpenAI client initialized")
            except Exception as e:
                current_app.logger.error(f"OpenAI initialization failed: {e}")
                self.openai_client = None
        else:
            current_app.logger.warning("OpenAI API key not configured or is placeholder")

        if gemini_key and not gemini_key.startswith('your-'):
            try:
                self.gemini_client = ChatGoogleGenerativeAI(
                    google_api_key=gemini_key,
                    model=current_app.config.get('DEFAULT_GEMINI_MODEL', 'models/gemini-pro'),
                    temperature=0.3,
                    max_output_tokens=500,
                    timeout=60
                )
                current_app.logger.info("Gemini client initialized")
            except Exception as e:
                current_app.logger.error(f"Gemini initialization failed: {e}")
                self.gemini_client = None
        else:
            current_app.logger.warning("Gemini API key not configured or is placeholder")

        if groq_key and not groq_key.startswith('your-'):
            try:
                self.groq_client = Groq(api_key=groq_key)
                current_app.logger.info("Groq client initialized")
            except Exception as e:
                current_app.logger.error(f"Groq initialization failed: {e}")
                self.groq_client = None
        else:
            current_app.logger.warning("Groq API key not configured or is placeholder")

        if self.openai_client:
            current_app.logger.info("LLMService: OpenAI provider configured.")
        if self.gemini_client:
            current_app.logger.info("LLMService: Gemini provider configured.")
        if self.groq_client:
            current_app.logger.info("LLMService: Groq provider configured.")

        if not self.openai_client and not self.gemini_client and not self.groq_client:
            current_app.logger.error("No LLM clients are available. All AI services will fail.")
            current_app.logger.warning("LLMService: No LLM providers configured!")

    def generate_answer_with_model(self, messages: list, ai_model, user_id: str = None, tenant_id: str = None) -> Optional[dict]:
        api_type = PROVIDER_API_TYPE_MAP.get(ai_model.provider)
        api_key = ai_model.get_api_key()
        base_url = ai_model.base_url

        if not api_key:
            current_app.logger.error(f"No API key for model: {ai_model.display_name} (provider: {ai_model.provider})")
            return None

        cache_key = f"llm_response:{ai_model.id}:{hash(str(messages))}"
        redis_service = getattr(current_app, 'redis_service', None)
        if redis_service:
            cached = redis_service.get_cache(cache_key)
            if cached is not None:
                current_app.logger.info(f"Cache hit for LLM response: {ai_model.display_name}")
                return cached

        try:
            if api_type == 'openai':
                client = ChatOpenAI(
                    api_key=api_key,
                    model=ai_model.model_name,
                    base_url=base_url,
                    temperature=0.3,
                    max_tokens=ai_model.max_tokens or 500,
                    timeout=60
                )
                response = client.invoke({"input": messages})
                result = {
                    "content": response.content,
                    "usage": {
                        "prompt_tokens": response.usage_metadata.get('prompt_tokens', 0) if response.usage_metadata else 0,
                        "completion_tokens": response.usage_metadata.get('completion_tokens', 0) if response.usage_metadata else 0,
                        "total_tokens": response.usage_metadata.get('total_tokens', 0) if response.usage_metadata else 0,
                    }
                }

            elif api_type == 'gemini':
                client = ChatGoogleGenerativeAI(
                    google_api_key=api_key,
                    model=ai_model.model_name,
                    temperature=0.3,
                    max_output_tokens=ai_model.max_tokens or 500,
                    timeout=60
                )
                response = client.invoke({"input": messages})
                result = {
                    "content": response.content,
                    "usage": {
                        "prompt_tokens": response.usage_metadata.get('prompt_tokens', 0) if response.usage_metadata else 0,
                        "completion_tokens": response.usage_metadata.get('completion_tokens', 0) if response.usage_metadata else 0,
                        "total_tokens": response.usage_metadata.get('total_tokens', 0) if response.usage_metadata else 0,
                    }
                }

            elif api_type == 'groq':
                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model=ai_model.model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=ai_model.max_tokens or 500,
                    stream=False
                )
                result = {
                    "content": response.choices[0].message.content,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    }
                }

            elif api_type == 'anthropic':
                try:
                    from anthropic import Anthropic
                    client = Anthropic(api_key=api_key)
                    system_content = None
                    user_messages = []
                    for msg in messages:
                        if msg['role'] == 'system':
                            system_content = msg['content']
                        else:
                            user_messages.append({'role': msg['role'], 'content': msg['content']})
                    kwargs = {
                        'model': ai_model.model_name,
                        'max_tokens': ai_model.max_tokens or 500,
                        'messages': user_messages,
                    }
                    if system_content:
                        kwargs['system'] = system_content
                    response = client.messages.create(**kwargs)
                    result = {
                        "content": response.content[0].text if response.content else "",
                        "usage": {
                            "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                            "completion_tokens": response.usage.output_tokens if response.usage else 0,
                            "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                        }
                    }
                except ImportError:
                    current_app.logger.error("Anthropic package not installed. Install with: pip install anthropic")
                    return None

            else:
                current_app.logger.error(f"Unsupported API type: {api_type} for provider {ai_model.provider}")
                return None

            if redis_service:
                redis_service.set_cache(cache_key, result, ttl=300)
            return result

        except Exception as e:
            current_app.logger.error(f"Error during LLM call to {ai_model.display_name}: {e}")
            return None

    def generate_answer(self, messages: list, model_name: str, user_id: str = None, tenant_id: str = None) -> Optional[dict]:
        if model_name.startswith('models/gemini-2.') or model_name.startswith('gpt-'):
            pass
        else:
            original_model = model_name
            deprecated_models = {
                'models/gemini-pro', 'models/gemini-1.5-pro', 'models/gemini-1.5-flash',
                'gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash',
                'models/gemini-1.5-pro-latest', 'models/gemini-1.5-flash-latest'
            }
            if model_name in deprecated_models:
                model_name = 'models/gemini-2.5-flash'
            elif model_name.startswith('gemini-') and not model_name.startswith('models/'):
                model_name = f'models/{model_name}'

        cache_key = f"llm_response:{model_name}:{hash(str(messages))}"
        redis_service = getattr(current_app, 'redis_service', None)
        if redis_service:
            cached = redis_service.get_cache(cache_key)
            if cached is not None:
                current_app.logger.info(f"Cache hit for LLM response: {model_name}")
                return cached

        client = None
        if 'gpt' in model_name and self.openai_client:
            client = self.openai_client
        elif 'gemini' in model_name and self.gemini_client:
            client = self.gemini_client
            original_client_model = client.model
            client.model = model_name
        elif model_name.startswith('llama') or model_name.startswith('mixtral') or model_name.startswith('gemma'):
            if self.groq_client:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=500,
                        stream=False
                    )
                    result = {
                        "content": response.choices[0].message.content,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                            "total_tokens": response.usage.total_tokens if response.usage else 0,
                        }
                    }
                    if redis_service:
                        redis_service.set_cache(cache_key, result, ttl=300)
                    return result
                except Exception as e:
                    current_app.logger.error(f"Groq API call failed: {e}")
                    return None
            else:
                current_app.logger.error(f"Groq client not available for model: {model_name}")
                return None

        if not client:
            current_app.logger.error(f"No client available for model: {model_name}")
            return None

        try:
            invocation_args = {"input": messages}
            response = client.invoke(**invocation_args)

            if 'gemini' in model_name and 'original_client_model' in locals():
                client.model = original_client_model

            result = {
                "content": response.content,
                "usage": {
                    "prompt_tokens": response.usage_metadata.get('prompt_tokens', 0) if response.usage_metadata else 0,
                    "completion_tokens": response.usage_metadata.get('completion_tokens', 0) if response.usage_metadata else 0,
                    "total_tokens": response.usage_metadata.get('total_tokens', 0) if response.usage_metadata else 0,
                }
            }

            if redis_service:
                redis_service.set_cache(cache_key, result, ttl=300)

            return result

        except Exception as e:
            current_app.logger.error(f"Error during LLM call to {model_name}: {e}")
            if 'gemini' in model_name and 'original_client_model' in locals() and client:
                client.model = original_client_model
            return None

    def generate_for_chatbot(self, messages: list, chatbot_config: dict, user_id: str = None, tenant_id: str = None) -> Optional[dict]:
        ai_model_id = chatbot_config.get('ai_model_id')
        if ai_model_id:
            try:
                from ..models import AiModel
                ai_model = AiModel.query.get(ai_model_id)
                if ai_model and ai_model.is_active:
                    return self.generate_answer_with_model(messages, ai_model, user_id, tenant_id)
            except Exception as e:
                current_app.logger.warning(f"Failed to look up AiModel {ai_model_id}: {e}")

        model_name = chatbot_config.get('ai_model') or chatbot_config.get('model') or 'gpt-4o-mini'
        return self.generate_answer(messages, model_name, user_id, tenant_id)

    def is_available(self, provider: str = None) -> bool:
        if provider == 'openai':
            return self.openai_client is not None
        elif provider == 'gemini':
            return self.gemini_client is not None
        elif provider == 'groq':
            return self.groq_client is not None
        else:
            return self.openai_client is not None or self.gemini_client is not None or self.groq_client is not None
