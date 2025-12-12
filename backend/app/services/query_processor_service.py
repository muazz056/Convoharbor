# ULTRA-OPTIMIZED version of chat_project/app/services/query_processor_service.py

from flask import current_app
import json
import time
import hashlib

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
    global _analysis_cache
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

def rewrite_query_with_history(chat_history: str, latest_query: str, provider: str = 'openai', model_name: str = 'gpt-4o-mini') -> str:
    """
    Rewrite user's query to be standalone using conversation history.
    Now respects user's specified LLM provider and model choice.
    """
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

    rewrite_prompt = f"""
You are helping rewrite a user's query to be standalone and clear.

CONVERSATION HISTORY:
{chat_history}

USER'S LATEST QUERY: "{latest_query}"

TASK: Rewrite the latest query to be standalone and searchable, incorporating necessary context from the conversation history.

EXAMPLES:
- If history mentions "atoms" and user asks "what are more related things to this?" → "What are things related to atoms?"
- If history mentions "Python programming" and user asks "show me examples" → "Show me examples of Python programming"
- If history mentions "machine learning" and user asks "how does it work?" → "How does machine learning work?"
- If history mentions "Hasnain Ali" and user asks "What are his projects?" → "What are Hasnain Ali's projects?"

IMPORTANT:
- Include specific topics/entities mentioned in recent conversation
- Make the query clear and searchable
- Keep it concise but complete
- If the latest query is already standalone, keep it as is

REWRITTEN QUERY:"""

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
            'result': rewritten_query, # Changed from 'query' to 'result'
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
    Enhanced with Helicone tracking for observability.
    """
    import time
    
    # Check cache first
    cache_key = f"analysis_{hash(query) % 10000}_{provider}_{model_name}"
    if cache_key in _analysis_cache:
        cached_result = _analysis_cache[cache_key]
        if time.time() - cached_result['timestamp'] < 600:  # 10 minutes TTL
            current_app.logger.info("🎯 Using cached analysis result")
            return cached_result['result']

    # Enhanced prompt with better conversational query detection
    analysis_prompt = f"""
Analyze this query comprehensively in a SINGLE response:

QUERY: "{query}"

Provide response in this EXACT JSON format:
{{
    "is_safe": true/false,
    "safety_reason": "reason if unsafe, empty if safe",
    "original_lang": "ISO_code",
    "english_query": "query in English",
    "sentiment": "positive/neutral/negative", 
    "intent": "question/clarification/end_conversation/gratitude/complaint",
    "complexity": "simple/moderate/complex",
    "hypothetical_answer": "sample answer in 1-2 sentences",
    "query_for_embedding": "optimized version for vector search"
}}

CRITICAL RULES:
1. CONVERSATIONAL QUERIES: If query contains pronouns (he, his, she, her, it, this, that, they, them) or context-dependent words (these, those, more, other, another, also), set complexity="complex"
2. LANGUAGE DETECTION: Use ISO codes (en, es, fr, de, hi, ar, etc.). For Hindi/Urdu, provide native script examples
3. SAFETY: Flag inappropriate content, hate speech, or harmful requests
4. INTENT: Classify the main purpose of the query
5. EMBEDDING QUERY: Make it searchable and specific

Examples of COMPLEX queries requiring context:
- "What are his projects?" (pronoun reference)
- "Tell me more about this" (context-dependent)
- "How does it work?" (pronoun reference)
- "Show me other examples" (context-dependent)

Examples of SIMPLE queries:
- "What is machine learning?"
- "Explain artificial intelligence"
- "How to cook pasta?"
"""

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
        import json
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
    
    # Get user role for personalization
    user_role = user_attributes.get('expertise', 'default')
    permission = user_attributes.get('permission', 'user')
    intent = user_attributes.get('intent', 'question')
    
    # Use ultra-fast prompt for simple queries
    if intent == 'question' and len(context) < 1000 and target_lang == 'en':
        # ULTRA-FAST prompt for simple ENGLISH queries only
        ultra_prompt = f"""
You are a professional AI assistant helping users find information. 

Context: {context}
User Question: {query}

Instructions:
- Provide a helpful, conversational response in natural English
- Speak directly to the user as their personal assistant
- If information is available, present it clearly and professionally
- If information is limited, acknowledge this naturally
- End with a relevant, helpful follow-up question
- Sound human and professional, not robotic

Response:"""
    else:
        # Use comprehensive prompt for non-English or complex queries
        ultra_prompt = f"""
You are a world-class AI assistant providing professional support to users globally.

CONTEXT INFORMATION:
{context}

USER QUESTION: {query}

RESPONSE GUIDELINES:
1. **Professional Tone**: Speak naturally as a knowledgeable assistant
2. **Language**: Respond in {target_lang} using native script
3. **Information Handling**:
   - If sufficient information: Provide clear, helpful answers
   - If limited information: "I checked my knowledge and found some relevant information..." 
   - If no information: "I've searched my knowledge base but don't have specific information about this topic"
4. **Mode**: {mode} mode - {'Use only provided context' if mode == 'strict' else 'Use context and general knowledge'}
5. **Follow-up**: End with a natural, helpful question to continue the conversation

CRITICAL LANGUAGE REQUIREMENTS:
- Target language: {target_lang}
- If {target_lang} is "hi": Use Devanagari script (हिंदी में)
- If {target_lang} is "ar": Use Arabic script (بالعربية)
- If {target_lang} is "zh": Use Chinese characters (中文)
- If {target_lang} is "en": Use professional English
- Use native script, not Roman transliteration

CONVERSATION STYLE:
- Professional but warm and approachable
- Direct and helpful without being robotic
- Acknowledge limitations naturally
- Focus on being genuinely helpful to the user

FOLLOW-UP QUESTION EXAMPLES:
- "Would you like me to explain any specific aspect in more detail?"
- "Is there anything else about this topic you'd like to know?"
- "Would you like to know more about [related topic]?"
- "Do you have any questions about [specific detail mentioned]?"
- NOT: "Can you provide more details about the technologies used in..."
- NOT: "Follow-up question: What other aspects would you like to explore?"

{f'CRITICAL: Respond entirely in {target_lang} native script - do not use English letters for non-English languages!' if needs_translation else ''}

RESPONSE:"""

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