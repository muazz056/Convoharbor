# ULTRA-OPTIMIZED version of chat_project/app/services/query_processor_service.py

from flask import current_app
import json
import time
import hashlib

# Lazy import to avoid circular dependency at module load


def _prompt_svc():
    from .prompt_service import PromptService
    return PromptService()

# In-memory cache for language detection to avoid repeated calls
_language_cache = {}
_intent_cache = {}

# In-memory cache for query analysis (cleared on restart)
_analysis_cache = {}
_cache_max_size = 1000
_cache_ttl = 3600  # 1 hour


def _get_cache_key(query: str, provider: str, model: str) -> str:
    """Generate a cache key for query analysis"""
    combined = f"{query.lower().strip()}:{provider}:{model}"
    return hashlib.md5(combined.encode()).hexdigest()


def clear_analysis_cache():
    """Clear the analysis cache to ensure fresh results"""
    global _analysis_cache  # noqa: F824
    _analysis_cache.clear()
    current_app.logger.info("🧹 Analysis cache cleared")


def _cleanup_cache():
    """Remove expired cache entries"""
    current_time = time.time()
    expired_keys = [k for k, v in _analysis_cache.items() if current_time - v['timestamp'] > _cache_ttl]
    for key in expired_keys:
        del _analysis_cache[key]

    # Also limit cache size
    if len(_analysis_cache) > _cache_max_size:
        # Remove oldest entries
        sorted_items = sorted(_analysis_cache.items(), key=lambda x: x[1]['timestamp'])
        for key, _ in sorted_items[:100]:  # Remove oldest 100
            del _analysis_cache[key]


def rewrite_query_with_history(chat_history: str, latest_query: str, provider: str = 'openai', model_name: str = None) -> str:
    """
    Rewrite user's query to be standalone using conversation history.
    Model is resolved from the Super Admin's AiModel table when not supplied.
    """
    if not model_name:
        try:
            from .model_resolver import get_default_llm_model
            model_name, resolved_provider = get_default_llm_model(provider=provider)
            provider = resolved_provider or provider
        except Exception:  # noqa: BLE001
            pass
    if not model_name:
        current_app.logger.warning("⚠️ No active AI model configured for query rewrite; returning original query")
        return latest_query

    current_app.logger.info(f"🔄 REWRITE DEBUG - Input query: '{latest_query}'")
    current_app.logger.info(f"🔄 REWRITE DEBUG - Chat history length: {len(chat_history) if chat_history else 0}")
    current_app.logger.info(f"🔄 REWRITE DEBUG - Chat history preview: {chat_history[:200] if chat_history else 'EMPTY'}...")

    # Quick check: if query seems standalone or is conversation ending, skip rewriting
    conversation_endings = ['bye', 'goodbye', 'thank you', 'thanks', 'that\'s all', 'exit', 'quit']
    if any(phrase in latest_query.lower() for phrase in conversation_endings):
        current_app.logger.info("🔄 REWRITE DEBUG - Skipping rewrite: conversation ending detected")
        return latest_query

    # Cache key includes provider and model for consistency
    cache_key = f"rewrite_{hash(chat_history + latest_query) % 10000}_{provider}_{model_name}"
    if cache_key in _intent_cache:
        cached_result = _intent_cache[cache_key]
        if time.time() - cached_result['timestamp'] < 600:  # 10 minutes TTL
            current_app.logger.info("🔄 REWRITE DEBUG - Using cached rewrite result")
            return cached_result['result']

    # If no meaningful history, return original query
    if not chat_history or len(chat_history.strip()) < 10:
        current_app.logger.info("🔄 REWRITE DEBUG - No meaningful history, returning original query")
        return latest_query

    current_app.logger.info(f"🔄 REWRITE DEBUG - Proceeding with rewrite using {provider}:{model_name}")

    rewrite_prompt = _prompt_svc().render(
        'query_rewrite',
        query=latest_query,
        context_block=(
            f"CONVERSATION HISTORY (use to resolve pronouns and context):\n{chat_history}"
            if chat_history else "CONVERSATION HISTORY: (none provided)"
        ),
    )

    try:
        current_app.logger.info("🔄 REWRITE DEBUG - Calling LLM for query rewriting...")
        response = current_app.llm_service.generate_answer(
            prompt=rewrite_prompt,
            provider=provider,  # Use user's specified provider
            model_name=model_name,  # Use user's specified model
            temperature=0.1
        )

        rewritten_query = response.strip().replace('"', '').replace('REWRITTEN QUERY:', '').strip()

        # Cache the result
        _intent_cache[cache_key] = {
            'result': rewritten_query,  # Changed from 'query' to 'result'
            'timestamp': time.time()
        }

        current_app.logger.info(f"🔄 REWRITE DEBUG - SUCCESS: '{latest_query}' → '{rewritten_query}'")
        return rewritten_query

    except Exception as e:
        current_app.logger.error(f"🔄 REWRITE DEBUG - ERROR: {e}")
        return latest_query  # Fallback to original


def ultra_efficient_query_analysis(query: str, provider: str, model_name: str, session_id: str = None, user_id: str = None) -> dict:
    """
    🚀 ULTRA-EFFICIENT: Single LLM call for complete query analysis
    Performs language detection, translation, sentiment analysis, intent classification,
    complexity assessment, safety moderation, and HyDE generation in ONE call.
    Single LLM call for complete query analysis.
    """
    import time

    # Check cache first
    cache_key = f"analysis_{hash(query) % 10000}_{provider}_{model_name}"
    if cache_key in _analysis_cache:
        cached_result = _analysis_cache[cache_key]
        if time.time() - cached_result['timestamp'] < 600:  # 10 minutes TTL
            current_app.logger.info("🎯 Using cached analysis result")
            return cached_result['result']

    # All prompt text comes from prompts.yml (query_analysis)
    analysis_prompt = _prompt_svc().render(
        'query_analysis',
        query=query,
        context_block="",
    )

    try:
        response = current_app.llm_service.generate_answer(
            prompt=analysis_prompt,
            provider=provider,
            model_name=model_name,
            temperature=0.1,
            session_id=session_id,
            user_id=user_id
        )

        # Parse JSON response
        result = json.loads(response.strip())

        # Cache the result
        _analysis_cache[cache_key] = {
            'result': result,
            'timestamp': time.time()
        }

        current_app.logger.info(f"✅ Analysis completed: complexity={result.get('complexity')}, intent={result.get('intent')}")
        return result

    except Exception as e:
        current_app.logger.error(f"❌ Analysis failed: {e}")
        return _fallback_analysis(query)


def _fallback_analysis(query: str) -> dict:
    """
    Fallback analysis when the ultra-efficient method fails.
    Uses pattern matching and heuristics for speed.
    Enhanced to detect conversational queries properly.
    """
    current_app.logger.info("🔄 Using fallback analysis...")

    # Simple safety check
    bad_words = ["hell", "fuck", "shit", "damn", "bitch"]
    is_safe = not any(word in query.lower() for word in bad_words)

    # Simple language detection (English assumed if uncertain)
    original_lang = "en"
    if any(char > '\u007F' for char in query):  # Non-ASCII characters
        original_lang = "und"  # Undefined

    # Enhanced complexity detection for conversational queries
    query_lower = query.lower()

    # Pronouns and context-dependent words that indicate conversational complexity
    conversational_indicators = [
        # Pronouns
        'he ', 'his ', 'him ', 'she ', 'her ', 'it ', 'its ',
        'they ', 'them ', 'their ', 'theirs ',
        # Context-dependent words
        'this ', 'that ', 'these ', 'those ',
        'more ', 'other ', 'another ', 'also ', 'further ',
        'additional ', 'same ', 'similar '
    ]

    # Check for conversational indicators
    is_conversational = any(indicator in query_lower for indicator in conversational_indicators)

    # Determine complexity
    if is_conversational:
        complexity = "complex"  # Conversational queries need context
        current_app.logger.info(f"🔗 Detected conversational query: {query}")
    elif len(query.split()) > 10:
        complexity = "moderate"
    else:
        complexity = "simple"

    # Simple intent detection
    intent = "question"
    if any(phrase in query.lower() for phrase in ["thank", "thanks", "bye", "done"]):
        intent = "end_conversation"
    elif any(phrase in query.lower() for phrase in ["clarify", "explain", "mean"]):
        intent = "clarification"

    return {
        "is_safe": is_safe,
        "safety_reason": "Contains inappropriate language" if not is_safe else "",
        "original_lang": original_lang,
        "english_query": query,  # Assume English for fallback
        "sentiment": "neutral",
        "intent": intent,
        "complexity": complexity,
        "hypothetical_answer": f"This query asks about {query[:50]}...",
        "query_for_embedding": query
    }


def ultra_efficient_final_generation(
    context: str,
    query: str,
    target_lang: str,
    mode: str,
    provider: str,
    model_name: str,
    user_attributes: dict,
    temperature: float = 0.1,
    session_id: str = None,
    user_id: str = None
) -> str:
    """
    🚀 ULTRA-OPTIMIZED: Single call that generates the final answer AND translates it if needed.
    This replaces 3 separate operations:
    1. Final answer generation
    2. Translation to target language
    3. Adding concluding phrase

    Reduces 3 LLM calls to 1 call.
    """
    start_time = time.time()

    # Determine if we need translation
    needs_translation = target_lang != "en"

    # Get user role for personalization (legacy fields - kept for parity)
    _expertise = user_attributes.get('expertise', 'default')  # noqa: F841
    _permission = user_attributes.get('permission', 'user')  # noqa: F841
    _intent = user_attributes.get('intent', 'question')  # noqa: F841

    # All final-answer generation now uses a single RAG-aware template.
    # The "ultra-fast" English-only branch is removed: prompts.yml renders
    # cleanly for both English and non-English targets, and the consistency
    # outweighs the small per-call cost of the richer template.
    needs_translation_block = (
        f"CRITICAL: Respond entirely in {target_lang} native script - "
        f"do not use English letters for non-English languages."
        if needs_translation else ""
    )
    refusal_message = (
        "I'm sorry, but I can't find an answer to your question in my "
        "knowledge base right now."
        if mode == 'strict' else
        "I searched my knowledge base but don't have specific information on that."
    )
    ultra_prompt = _prompt_svc().render(
        'answer_ultra',
        chatbot_name=user_attributes.get('chatbot_name', 'this chatbot'),
        chatbot_role=user_attributes.get('role', 'AI Assistant'),
        target_lang=target_lang,
        needs_translation_block=needs_translation_block,
        context=context,
        history=user_attributes.get('history', '(no prior messages)'),
        query=query,
        mode=mode,
        refusal_message=refusal_message,
    )

    try:
        current_app.logger.info(f"🚀 ULTRA-EFFICIENT: Single call for final answer{' + translation' if needs_translation else ''}...")

        final_answer = current_app.llm_service.generate_answer(
            prompt=ultra_prompt,
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            user_id=user_id,
            session_id=session_id
        )

        processing_time = time.time() - start_time
        current_app.logger.info(f"⚡ ULTRA-EFFICIENT final generation completed in {processing_time:.2f}s")

        return final_answer.strip()

    except Exception as e:
        current_app.logger.error(f"❌ Error during ultra-efficient final generation: {e}")
        # Fallback to basic answer
        return f"I apologize, but I'm having trouble processing your request. Could you please rephrase your question?"

# Legacy functions for backward compatibility


def process_query_in_one_shot(query: str, provider: str, original_lang: str, model_name: str) -> dict | None:
    """
    DEPRECATED: Use ultra_efficient_query_analysis instead.
    Maintained for backward compatibility.
    """
    current_app.logger.warning("⚠️ Using deprecated process_query_in_one_shot. Consider upgrading to ultra_efficient_query_analysis.")
    return ultra_efficient_query_analysis(query, provider, model_name)
