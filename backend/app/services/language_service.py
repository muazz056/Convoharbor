import google.generativeai as genai
from flask import current_app

_language_cache = {}

def _is_placeholder_key(api_key):
    return not api_key or api_key.startswith('your-')

def _configure_llm(api_key=None, model_name="gemini-1.5-flash"):
    api_key = api_key or current_app.config.get('GEMINI_API_KEY')
    if not api_key or _is_placeholder_key(api_key):
        return None
    genai.configure(api_key=api_key)

    model_names_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-002",
        "gemini-1.5-pro-002",
        "gemini-pro"
    ]

    for name in model_names_to_try:
        try:
            model = genai.GenerativeModel(name, generation_config={"temperature": 0.0})
            return model
        except Exception:
            continue

    model = genai.GenerativeModel("gemini-pro", generation_config={"temperature": 0.0})
    return model

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
        prompt = (
            "Analyze the following text and identify its primary language. "
            "Respond with ONLY the two-letter ISO 639-1 language code. "
            "For example: 'en' for English, 'es' for Spanish, 'fa' for Farsi (Persian) and in same manner for other languages. "
            f"Text: \"{sanitized_sample}\""
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

    model = _configure_llm(api_key=api_key, model_name='gemini-1.5-flash')
    if not model:
        return None

    try:
        prompt = (
            "You are an expert multilingual translator. Your task is to translate the user's query for a semantic search system. "
            "It is crucial that the core *concept* of the query is preserved. "
            f"Translate the following text from '{source_language}' to '{target_language}'. "
            "Respond ONLY with the translated text and nothing else. "
            f"\n\nText to translate: \"{text}\""
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
