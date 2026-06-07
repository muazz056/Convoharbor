import google.generativeai as genai
from flask import current_app

_language_cache = {}


def _prompt_svc():
    from .prompt_service import PromptService
    return PromptService()


def _is_placeholder_key(api_key):
    return not api_key or api_key.startswith('your-')


def _resolve_model_name(provider: str = "gemini") -> str | None:
    """Return the first active model name configured by Super Admin for the provider."""
    try:
        from .model_resolver import get_default_llm_model
        model_name, _ = get_default_llm_model(provider=provider)
        return model_name
    except Exception:  # noqa: BLE001
        return None


def _configure_llm(api_key=None, model_name=None, provider: str = "gemini"):
    api_key = api_key or current_app.config.get('GEMINI_API_KEY')
    if not api_key or _is_placeholder_key(api_key):
        return None
    genai.configure(api_key=api_key)

    # Prefer the model that the Super Admin has configured for the provider.
    primary = model_name or _resolve_model_name(provider=provider)
    if primary:
        try:
            return genai.GenerativeModel(primary, generation_config={"temperature": 0.0})
        except Exception:  # noqa: BLE001
            current_app.logger.warning(f"⚠️ Could not initialize configured Gemini model: {primary}")

    # As a last resort, try any other active model from the Super Admin's table.
    try:
        from .model_resolver import get_active_models
        for ai_model in get_active_models(provider=provider):
            try:
                return genai.GenerativeModel(ai_model.model_name, generation_config={"temperature": 0.0})
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass

    return None


def detect_language_with_llm(text_sample: str, api_key: str = None) -> str:
    sanitized_sample = text_sample.strip()
    if len(sanitized_sample) > 1000:
        sanitized_sample = sanitized_sample[:1000]

    if not sanitized_sample:
        return 'und'

    if sanitized_sample in _language_cache:
        return _language_cache[sanitized_sample]

    model = _configure_llm(api_key=api_key)
    if not model:
        return 'und'

    try:
        prompt = _prompt_svc().render(
            'language_detection',
            text=sanitized_sample,
        )
        response = model.generate_content(prompt)
        if not response or not response.text:
            current_app.logger.warning("Language detection: Gemini returned empty response")
            return 'und'
        lang_code = response.text.strip().lower()

        if 2 <= len(lang_code) <= 3 and lang_code.isalpha():
            _language_cache[sanitized_sample] = lang_code
            return lang_code
        else:
            return 'und'

    except Exception as e:
        current_app.logger.error(f"Gemini API call for language detection failed: {e}")
        return 'und'


def translate_text(text: str, target_language: str, source_language: str = "auto", api_key: str = None) -> str | None:
    if not text.strip():
        return None

    model = _configure_llm(api_key=api_key, model_name=None)
    if not model:
        return None

    try:
        prompt = _prompt_svc().render(
            'translation',
            text=text,
            source_lang=source_language,
            target_lang=target_language,
        )

        response = model.generate_content(prompt)
        if not response or not response.text:
            current_app.logger.warning("Translation: Gemini returned empty response")
            return None
        translated_text = response.text.strip()

        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]

        current_app.logger.info(f"Translation from '{source_language}' to '{target_language}' result: '{translated_text}'")
        return translated_text
    except Exception as e:
        current_app.logger.error(f"Gemini API call for translation failed: {e}")
        return None
