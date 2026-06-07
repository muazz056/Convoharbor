"""
Model Resolver - Centralized lookup for LLM models configured by Super Admin.

Architectural rule (2026-06-06):
- Embedding models come from .env (OPENAI_EMBEDDING_MODEL, GEMINI_EMBEDDING_MODEL).
- Response-generation models come ONLY from the AiModel table, configured by Super Admin
  via the admin UI. There are no .env or hardcoded response-model defaults.

If a chatbot config or internal service does not have an explicit model, this resolver
returns the first active model from the AiModel table, optionally filtered by provider.
"""
from typing import Optional, Tuple, List
from flask import current_app

from ..models import AiModel


def get_default_llm_model(provider: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (model_name, provider) for the first active AiModel.

    Args:
        provider: optional provider id to filter on ('openai', 'gemini', etc.)

    Returns:
        (model_name, provider) tuple, or (None, None) if no active model is configured.
    """
    try:
        query = AiModel.query.filter_by(is_active=True)
        if provider:
            query = query.filter_by(provider=provider)
        model = query.order_by(AiModel.id.asc()).first()
        if model:
            return model.model_name, model.provider
    except Exception as exc:  # noqa: BLE001
        try:
            current_app.logger.warning(f"⚠️ model_resolver.get_default_llm_model failed: {exc}")
        except RuntimeError:
            pass
    return None, None


def get_active_models(provider: Optional[str] = None) -> List[AiModel]:
    """
    Return the list of active AiModel rows, optionally filtered by provider.
    """
    try:
        query = AiModel.query.filter_by(is_active=True)
        if provider:
            query = query.filter_by(provider=provider)
        return query.order_by(AiModel.id.asc()).all()
    except Exception as exc:  # noqa: BLE001
        try:
            current_app.logger.warning(f"⚠️ model_resolver.get_active_models failed: {exc}")
        except RuntimeError:
            pass
        return []


def get_active_model_names(provider: Optional[str] = None) -> List[str]:
    """
    Return the list of active AiModel.model_name values, optionally filtered by provider.
    Useful for validation and Swagger enums.
    """
    return [m.model_name for m in get_active_models(provider=provider)]


def resolve_model(config: Optional[dict], provider: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolve a chatbot config dict to (model_name, provider).

    Resolution order:
        1. config.get('ai_model_id')   -> look up that AiModel row
        2. config.get('ai_model')      -> validate it exists in the active AiModel list
        3. Fall back to first active AiModel (optionally filtered by config provider)

    Raises ValueError if no model can be resolved.
    """
    config = config or {}

    explicit_id = config.get('ai_model_id')
    if explicit_id:
        try:
            model = AiModel.query.filter_by(id=explicit_id, is_active=True).first()
            if model:
                return model.model_name, model.provider
        except Exception as exc:  # noqa: BLE001
            try:
                current_app.logger.warning(f"⚠️ model_resolver.resolve_model lookup failed: {exc}")
            except RuntimeError:
                pass

    explicit_name = config.get('ai_model') or config.get('model')
    if explicit_name:
        try:
            model = AiModel.query.filter_by(model_name=explicit_name, is_active=True).first()
            if model:
                return model.model_name, model.provider
        except Exception as exc:  # noqa: BLE001
            try:
                current_app.logger.warning(f"⚠️ model_resolver.resolve_model lookup failed: {exc}")
            except RuntimeError:
                pass

    configured_provider = provider or config.get('ai_provider')
    default_name, default_provider = get_default_llm_model(provider=configured_provider)
    if default_name:
        return default_name, default_provider

    raise ValueError(
        "No active AI model is configured. Super Admin must add at least one model in the AI Models page."
    )
