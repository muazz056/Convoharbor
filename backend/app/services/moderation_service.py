# app/services/moderation_service.py

from better_profanity import profanity
from flask import current_app
import openai
import json

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
    # For this critical reasoning task, we use a more powerful model.
    provider = "openai"
    model_name = "gpt-4o-mini"
    
    policy_prompt = f"""
    You are an AI personal assistant that helps users with related queries.
    You must ensure that all responses adhere to a strict safety policy.
    POLICY: Do not answer if the vaulgar language is used in the query.
    Analyze the user's query below. Your response MUST be a single, valid JSON object with two keys: "violates_policy" (boolean) and "reason" (string).

    USER QUERY: "{query}"
    """
    
    try:
        response_str = current_app.llm_service.generate_answer(
            prompt=policy_prompt,
            provider=provider,
            model_name=model_name,
            temperature=0.0
        )
        cleaned_response = response_str.strip().replace("```json", "").replace("```", "")
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