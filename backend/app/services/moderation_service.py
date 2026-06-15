# app/services/moderation_service.py

from better_profanity import profanity
from flask import current_app
import openai
import json


def _prompt_svc():
    from .prompt_service import PromptService
    return PromptService()

# --- TIER 1: Custom profanity list (unchanged) ---
custom_bad_words = ["hell", "fucked", "fucking", "fuck", "bitch", "shit", "asshole"]
profanity.add_censor_words(custom_bad_words)

# --- Define Fallback Responses ---
POLICY_VIOLATION_FALLBACK = "This question violates our safety policy regarding personal inquiries. I cannot process this request."
PROFANITY_FALLBACK = "Your request could not be processed because it contains inappropriate language."
MODERATION_FALLBACK = "Your request has been flagged as potentially harmful. Please rephrase your query."


def _is_policy_violating(query: str) -> tuple[bool, str]:
    """
    TIER 0: Inappropriate Inquiry Policy Check
    This is the most important layer for catching nuanced, inappropriate intent.
    """
    # Resolve the chat model from Super Admin's AiModel table (no hardcoded names).
    try:
        from .model_resolver import get_default_llm_model
        resolved_model, resolved_provider = get_default_llm_model(provider="openai")
    except Exception:  # noqa: BLE001
        resolved_model, resolved_provider = None, None

    if not resolved_model:
        # No model configured - fail safe by blocking the request
        current_app.logger.error("❌ Policy check skipped: no active AI model configured by Super Admin")
        return True, "Safety policy check is unavailable right now. Please try again later."

    provider = resolved_provider or "openai"
    model_name = resolved_model

    policy_prompt = _prompt_svc().render('moderation', query=query)

    try:
        response_data = current_app.llm_service.generate_answer(
            messages=[{"role": "user", "content": policy_prompt}],
            model_name=model_name,
            temperature=0.0
        )
        if response_data is None:
            return {"violates_policy": False, "reason": "LLM unavailable"}
        cleaned_response = response_data.get('content', '').strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned_response)

        if result.get("violates_policy") is True:
            reason = result.get("reason", "No reason provided.")
            current_app.logger.warning(f"POLICY VIOLATION DETECTED. Reason: {reason}. Query: '{query}'")
            return True, POLICY_VIOLATION_FALLBACK

        return False, ""
    except Exception as e:
        current_app.logger.error(f"Error during policy check: {e}. Defaulting to safe (blocking request).")
        # Fail-safe: If the policy check itself fails, we block the query.
        return True, "Could not verify request against safety policy."


def moderate_input_with_ai(text: str) -> str | None:
    """
    The main moderation entry point, now with a three-tiered approach.
    """
    # TIER 0: Policy Violation Check (Most Important)
    is_violating, reason = _is_policy_violating(text)
    if is_violating:
        return reason

    # TIER 1: Fast, local profanity check.
    if profanity.contains_profanity(text):
        current_app.logger.warning(f"Profanity detected by local filter. Query blocked: '{text}'")
        return PROFANITY_FALLBACK

    # TIER 2: General AI-based moderation for explicit content.
    try:
        client = openai.OpenAI(api_key=current_app.config['OPENAI_API_KEY'])
        response = client.moderations.create(input=text, model="text-moderation-stable")

        result = response.results[0]
        if result.flagged:
            flagged_categories = [category for category, flagged in result.categories.__dict__.items() if flagged]
            current_app.logger.warning(f"AI moderation flagged input. Categories: {flagged_categories}. Query: '{text}'")
            return MODERATION_FALLBACK
    except Exception as e:
        current_app.logger.error(f"Error during moderation API call: {e}. Allowing request to proceed.")

    # If all checks pass, the input is clean.
    return None
