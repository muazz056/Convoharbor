# chat_project/app/services/prompt_service.py

import yaml
from flask import current_app

class PromptService:
    """
    Manages loading and dynamically composing prompts from an external YAML file
    based on user attributes like permissions and expertise.
    """
    def __init__(self):
        self.base_templates = {}
        self.modifiers = {}
        self._load_prompts()
        current_app.logger.info("PromptService initialized with modular prompt system.")

    def _load_prompts(self):
        """Loads modular prompt components from the YAML config file."""
        config_path = current_app.config['PROMPT_CONFIG_PATH']
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.base_templates = data.get('base_templates', {})
                self.modifiers = data.get('modifiers', {})
        except FileNotFoundError:
            raise RuntimeError(f"Prompt configuration file not found at: {config_path}")
        except (yaml.YAMLError, KeyError) as e:
            raise RuntimeError(f"Error parsing prompt configuration file: {e}")

    def build_prompt(self, user_attributes: dict, prompt_data: dict) -> str:
        """
        Builds a dynamic prompt by composing a base template with modifiers.

        Args:
            user_attributes (dict): Attributes of the user, e.g.,
                {"permission": "admin", "expertise": "beginner", "intent": "support_request"}
            prompt_data (dict): The data to fill placeholders with, e.g.,
                {"english_context": "...", "english_query": "..."}

        Returns:
            The fully composed and formatted prompt string.
        """
        # Determine which base template to use (e.g., for summarization vs. QA)
        base_template_key = user_attributes.get('base_template', 'default')
        base_template = self.base_templates.get(base_template_key)
        if not base_template:
            raise ValueError(f"Base template '{base_template_key}' not found in prompts.yml.")

        # Gather modifier instructions based on user attributes
        modifier_instructions = []
        for category, levels in self.modifiers.items():
            user_level = user_attributes.get(category, 'default')
            instruction = levels.get(user_level, levels.get('default', ''))
            if instruction:
                modifier_instructions.append(instruction)
        
        # Combine instructions into a single block
        full_modifier_text = "\n".join(modifier_instructions)

        # Add the modifier text to the main prompt data
        # This will fill the {modifier_instructions} placeholder in the base template
        prompt_data['modifier_instructions'] = full_modifier_text

        formatting_data = prompt_data.copy()
        formatting_data['was_retrieval_successful'] = str(formatting_data.get('was_retrieval_successful', False))
        formatting_data['modifier_instructions'] = full_modifier_text

        try:
            # Format the base template with both the core data and the dynamic instructions
            return base_template.format(**formatting_data)
        except KeyError as e:
            current_app.logger.error(f"Missing a required placeholder to format the prompt: {e}")
            raise ValueError(f"Prompt template is missing a required variable: {e}")