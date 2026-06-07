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
        current_app.logger.info("LLMService initialized (clients created on demand per request)")

    def generate_answer_with_model(self, messages: list, ai_model, user_id: str = None, tenant_id: str = None, temperature: float = None, max_tokens: int = None) -> Optional[dict]:
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

        temp = temperature if temperature is not None else 0.3
        tokens = max_tokens or ai_model.max_tokens or 500

        try:
            if api_type == 'openai':
                client = ChatOpenAI(
                    api_key=api_key,
                    model=ai_model.model_name,
                    base_url=base_url,
                    temperature=temp,
                    max_tokens=tokens,
                    timeout=60
                )
                response = client.invoke(messages)
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
                    temperature=temp,
                    max_output_tokens=tokens,
                    timeout=60
                )
                response = client.invoke(messages)
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
                    temperature=temp,
                    max_tokens=tokens,
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
                        'max_tokens': tokens,
                        'temperature': temp,
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

    def generate_answer(self, messages: list, model_name: str, user_id: str = None, tenant_id: str = None, temperature: float = None, max_tokens: int = None) -> Optional[dict]:
        from ..models import AiModel as AiModelDB
        ai_model = AiModelDB.query.filter_by(model_name=model_name, is_active=True).first()
        if ai_model:
            return self.generate_answer_with_model(messages, ai_model, user_id, tenant_id, temperature=temperature, max_tokens=max_tokens)

        current_app.logger.error(f"No active AiModel found for '{model_name}'. Only models set by super admin are available.")
        return None

    def generate_for_chatbot(self, messages: list, chatbot_config: dict, user_id: str = None, tenant_id: str = None) -> Optional[dict]:
        # Use the centralized defaults so the .env file is the single
        # source of truth and the temperature/max_tokens are consistent
        # across the whole application.
        from . import chatbot_defaults
        temperature = chatbot_defaults.resolve_field(chatbot_config, 'temperature')
        max_tokens = chatbot_config.get('max_tokens')
        if max_tokens is None:
            max_tokens = chatbot_defaults.resolve_field(chatbot_config, 'max_tokens')
        ai_model_id = chatbot_config.get('ai_model_id')
        if ai_model_id:
            try:
                from ..models import AiModel
                ai_model = AiModel.query.get(ai_model_id)
                if ai_model and ai_model.is_active:
                    return self.generate_answer_with_model(messages, ai_model, user_id, tenant_id, temperature=temperature, max_tokens=max_tokens)
            except Exception as e:
                current_app.logger.warning(f"Failed to look up AiModel {ai_model_id}: {e}")

        model_name = chatbot_config.get('ai_model') or chatbot_config.get('model')
        if model_name:
            return self.generate_answer(messages, model_name, user_id, tenant_id, temperature=temperature, max_tokens=max_tokens)

        current_app.logger.error("No ai_model configured for chatbot. Set a model via super admin.")
        return None

    def is_available(self, provider: str = None) -> bool:
        from ..models import AiModel as AiModelDB
        query = AiModelDB.query.filter_by(is_active=True)
        if provider:
            query = query.filter_by(provider=provider)
        return query.first() is not None
