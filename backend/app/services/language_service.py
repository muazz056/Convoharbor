# app/services/language_service.py

import google.generativeai as genai
from flask import current_app

_language_cache = {}

def _configure_llm(model_name="gemini-1.5-flash-latest"):
    """Configures and returns the Generative AI model."""
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the .env file.")
    
    # Check if already configured to avoid redundant calls
    if not hasattr(genai, '_is_configured'):
        genai.configure(api_key=api_key)
        genai._is_configured = True

    # Try multiple model names for compatibility (Google deprecated old model names)
    model_names_to_try = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-002",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro-latest",
        "gemini-pro"
    ]
    
    for name in model_names_to_try:
        try:
            model = genai.GenerativeModel(name, generation_config={"temperature": 0.0})
            return model
        except Exception as e:
            current_app.logger.debug(f"Failed to load Gemini model {name}: {e}")
            continue
    
    # Final fallback
    model = genai.GenerativeModel("gemini-pro", generation_config={"temperature": 0.0})
    return model

def detect_language_with_llm(text_sample: str) -> str:
    """
    Detects the language of a text sample using the Gemini LLM for high accuracy.
    """
    sanitized_sample = text_sample.strip()
    if len(sanitized_sample) > 1000:
        sanitized_sample = sanitized_sample[:1000]

    if not sanitized_sample:
        return 'und'
        
    if sanitized_sample in _language_cache:
        return _language_cache[sanitized_sample]

    try:
        model = _configure_llm()
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
    
def translate_text(text: str, target_language: str, source_language: str = "auto") -> str | None:
    """
    Translates text to a target language using the Gemini LLM with an improved, context-aware prompt.

    Args:
        text: The text to translate.
        target_language: The ISO 639-1 code of the language to translate to (e.g., "en", "es").
        source_language: The ISO 639-1 code of the source language. Defaults to "auto".

    Returns:
        The translated text, or None if translation fails.
    """
    if not text.strip():
        return None

    try:
        model = _configure_llm(model_name='gemini-1.5-flash-latest')
        
        # --- NEW, MORE ROBUST PROMPT ---
        # We give the model context about the task to get a more accurate conceptual translation.
        prompt = (
            "You are an expert multilingual translator. Your task is to translate the user's query for a semantic search system. "
            "It is crucial that the core *concept* of the query is preserved. "
            f"Translate the following text from '{source_language}' to '{target_language}'. "
            "Respond ONLY with the translated text and nothing else. "
            f"\n\nText to translate: \"{text}\""
        )
        # --- END OF NEW PROMPT ---

        response = model.generate_content(prompt)
        if not response or not response.text:
            current_app.logger.warning("Translation: Gemini returned empty response")
            return None
        translated_text = response.text.strip()
        
        # A simple post-translation check to remove potential quotation marks from the LLM's output
        if translated_text.startswith('"') and translated_text.endswith('"'):
            translated_text = translated_text[1:-1]
            
        current_app.logger.info(f"Translation from '{source_language}' to '{target_language}' result: '{translated_text}'")
        return translated_text
    except Exception as e:
        current_app.logger.error(f"Gemini API call for translation failed: {e}")
        return None