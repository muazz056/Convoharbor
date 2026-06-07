"""
Intent Analysis Service for detecting conversation ending patterns.
The model is resolved at call time from the Super Admin's AiModel table
(no hardcoded response-model names).
"""
from flask import current_app
from typing import List, Dict
import json


def _prompt_svc():
    from .prompt_service import PromptService
    return PromptService()


class IntentAnalysisService:
    """Service to analyze user intent for conversation management."""

    def __init__(self):
        """Initialize the intent analysis service."""
        self.model = None  # Resolved lazily from AiModel table

    def _resolve_model(self) -> str | None:
        """Return the first active model from the AiModel table."""
        try:
            from .model_resolver import get_default_llm_model
            model_name, _ = get_default_llm_model()
            return model_name
        except Exception:  # noqa: BLE001
            return None

    def analyze_conversation_intent(self, messages: List[Dict], user_message: str) -> Dict:
        """
        Analyze the last few messages to determine if user wants to end the conversation.

        Args:
            messages: List of recent conversation messages
            user_message: The latest user message

        Returns:
            Dict with intent analysis results
        """
        try:
            if not current_app.llm_service or not current_app.llm_service.openai_client:
                current_app.logger.warning("⚠️ Intent analysis skipped - OpenAI client not available")
                return {'should_show_rating': False, 'confidence': 0.0, 'reason': 'OpenAI not available'}

            # Resolve the model from the Super Admin's AiModel table
            model_name = self._resolve_model()
            if not model_name:
                current_app.logger.warning("⚠️ Intent analysis skipped - no active AI model configured")
                return {'should_show_rating': False, 'confidence': 0.0, 'reason': 'No active AI model'}

            # Get the last 3-4 messages for context
            recent_messages = messages[-4:] if len(messages) >= 4 else messages

            # Build conversation context
            conversation_context = []
            for msg in recent_messages:
                role = 'user' if msg.get('message_type') == 'user' else 'assistant'
                content = msg.get('content', '')
                if content.strip():
                    conversation_context.append(f"{role.title()}: {content}")

            # Add the current user message
            conversation_context.append(f"User: {user_message}")

            # Create the analysis prompt
            analysis_prompt = self._create_intent_analysis_prompt(conversation_context)

            # Analyze intent using GPT-4o
            intent_messages = [
                {"role": "system", "content": analysis_prompt},
                {"role": "user", "content": "Analyze the conversation above for ending intent."}
            ]

            current_app.logger.info(f"🧠 Analyzing conversation intent with {len(conversation_context)} messages")

            response_data = current_app.llm_service.generate_answer(
                messages=intent_messages,
                model_name=model_name,
                user_id='system',
                tenant_id='intent_analysis'
            )

            if not response_data:
                return {'should_show_rating': False, 'confidence': 0.0, 'reason': 'No response from GPT-4o'}

            # Parse the response
            analysis_result = self._parse_intent_response(response_data.get('content', ''))
            current_app.logger.info(f"🧠 Intent analysis result: {analysis_result}")

            return analysis_result

        except Exception as e:
            current_app.logger.error(f"❌ Error in intent analysis: {e}")
            return {'should_show_rating': False, 'confidence': 0.0, 'reason': f'Analysis error: {str(e)}'}

    def _create_intent_analysis_prompt(self, conversation_context: List[str]) -> str:
        """Create the prompt for intent analysis (sourced from prompts.yml)."""
        context_text = "\n".join(conversation_context)
        return _prompt_svc().render(
            'intent_analysis',
            context_text=context_text,
        )

    def _parse_intent_response(self, response_content: str) -> Dict:
        """Parse the GPT-4o response for intent analysis."""
        try:
            # Try to extract JSON from the response
            response_content = response_content.strip()

            # Look for JSON block
            if '```json' in response_content:
                start = response_content.find('```json') + 7
                end = response_content.find('```', start)
                json_content = response_content[start:end].strip()
            elif response_content.startswith('{') and response_content.endswith('}'):
                json_content = response_content
            else:
                # Try to find JSON-like content
                start = response_content.find('{')
                end = response_content.rfind('}') + 1
                if start != -1 and end > start:
                    json_content = response_content[start:end]
                else:
                    raise ValueError("No JSON found in response")

            result = json.loads(json_content)

            # Validate required fields
            should_show_rating = result.get('should_show_rating', False)
            confidence = float(result.get('confidence', 0.0))
            reason = result.get('reason', 'No reason provided')
            detected_patterns = result.get('detected_patterns', [])

            # Apply confidence threshold
            if confidence < 0.7:
                should_show_rating = False
                reason += f" (Confidence {confidence} below threshold 0.7)"

            return {
                'should_show_rating': should_show_rating,
                'confidence': confidence,
                'reason': reason,
                'detected_patterns': detected_patterns
            }

        except Exception as e:
            current_app.logger.error(f"❌ Error parsing intent response: {e}")
            current_app.logger.error(f"❌ Response content: {response_content}")
            return {
                'should_show_rating': False,
                'confidence': 0.0,
                'reason': f'Parse error: {str(e)}',
                'detected_patterns': []
            }
