# chat_project/app/services/prompt_service.py

import yaml
from string import Template
from flask import current_app


class PromptService:
    """
    Manages loading and rendering prompts from the master ``prompts.yml`` file.

    The service is the SINGLE source of truth for prompt strings used across
    the backend. No .py file should hardcode a prompt.

    Two access patterns are supported:

    1. **Direct render**: ``prompt_service.render("rag_system.strict", ...)``
       Loads a specific top-level key (with optional dotted sub-key) and
       fills the ``$var_name`` placeholders.

    2. **Composite build** (legacy): ``prompt_service.build_prompt(user_attributes, prompt_data)``
       Composes a base template with attribute-based modifiers. Retained for
       backward compatibility with the original attribute-based system.

    Placeholder syntax:
        - ``$name`` - replaced from kwargs.
        - ``${name}`` - same, useful when followed by alphanumeric chars.
        - Missing placeholders are left as-is (no exception).

    The renderer is safe-substitute: it will NOT raise if a placeholder is
    missing, but it WILL log a warning so authors can fix the prompt.
    """

    def __init__(self):
        self.prompts: dict = {}
        self.base_templates: dict = {}
        self.modifiers: dict = {}
        self._load_prompts()
        current_app.logger.info(
            f"PromptService initialized - {len(self.prompts)} prompt keys loaded."
        )

    # ----------------------------------------------------------------
    # Loading
    # ----------------------------------------------------------------
    # Reserved top-level YAML keys that are NOT prompts.
    _RESERVED_KEYS = frozenset({
        'version', 'description',
        'base_templates', 'modifiers',
    })

    def _load_prompts(self):
        """Loads prompts from the YAML config file.

        The new format puts every prompt key (rag_system, moderation, ...) at
        the top level of the YAML. Reserved keys (``version``, ``description``,
        ``base_templates``, ``modifiers``) are stripped out and stored on
        dedicated attributes for backward compatibility.

        This is the single source of truth for prompt text used across the
        backend. No .py file should hardcode a prompt string.
        """
        config_path = current_app.config['PROMPT_CONFIG_PATH']
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raise RuntimeError(f"Prompt configuration file not found at: {config_path}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing prompt configuration file: {e}")

        # Legacy support: keep base_templates + modifiers as separate attrs.
        self.base_templates = data.get('base_templates', {}) or {}
        self.modifiers = data.get('modifiers', {}) or {}

        # New format: every non-reserved top-level key is a prompt.
        self.prompts = {
            k: v for k, v in data.items() if k not in self._RESERVED_KEYS
        }

    def reload(self):
        """Hot-reload prompts from disk. Useful in dev or when admins edit the file."""
        self._load_prompts()

    # ----------------------------------------------------------------
    # New RENDER API
    # ----------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str:
        """
        Return the raw template string for a top-level (or dotted) prompt key.

        Examples:
            prompt_service.get("rag_system.strict")
            prompt_service.get("query_rewrite")
            prompt_service.get("moderation", default="You are a moderator.")
        """
        if not key:
            return default or ""

        # Support dotted keys: "rag_system.strict"
        node = self.prompts
        for part in key.split('.'):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                if default is not None:
                    return default
                current_app.logger.warning(
                    f"PromptService: key '{key}' not found in prompts.yml"
                )
                return ""

        if not isinstance(node, str):
            current_app.logger.warning(
                f"PromptService: key '{key}' resolved to non-string type {type(node).__name__}"
            )
            return default or ""

        return node

    def render(self, key: str, **kwargs) -> str:
        """
        Load the template for ``key`` and substitute ``$var_name`` placeholders.

        Missing placeholders are left as literal text (safe-substitute) so a
        render never crashes the request path. A warning is logged for each
        missing key so authors can fix the prompt.

        Example:
            prompt_service.render(
                "rag_system.strict",
                chatbot_name="Acme Support",
                chatbot_role="customer service",
                target_lang="English",
                context="<kb chunks here>",
            )
        """
        template_str = self.get(key)
        if not template_str:
            current_app.logger.error(
                f"PromptService.render: empty/missing template for key '{key}'"
            )
            return ""

        # string.Template handles $name and ${name} with safe_substitute
        # which leaves missing keys literal instead of raising.
        try:
            tmpl = Template(template_str)
        except (ValueError, KeyError) as e:
            current_app.logger.error(
                f"PromptService.render: invalid template for key '{key}': {e}"
            )
            return template_str

        try:
            rendered = tmpl.safe_substitute(kwargs)
        except Exception as e:
            current_app.logger.error(
                f"PromptService.render: substitution error for key '{key}': {e}"
            )
            return template_str

        # Detect any unfilled placeholders and log them.
        if '$' in rendered:
            import re
            leftover = re.findall(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?', rendered)
            if leftover:
                current_app.logger.warning(
                    f"PromptService.render: key '{key}' had unfilled placeholders: "
                    f"{sorted(set(leftover))}"
                )

        return rendered

    # ----------------------------------------------------------------
    # Legacy COMPOSE API (kept for backward compatibility)
    # ----------------------------------------------------------------
    def build_prompt(self, user_attributes: dict, prompt_data: dict) -> str:
        """
        Builds a dynamic prompt by composing a base template with modifiers.

        Kept for backward compatibility with the original attribute-based
        system. New code should use ``render()`` instead.

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
        prompt_data['modifier_instructions'] = full_modifier_text

        formatting_data = prompt_data.copy()
        formatting_data['was_retrieval_successful'] = str(
            formatting_data.get('was_retrieval_successful', False)
        )
        formatting_data['modifier_instructions'] = full_modifier_text

        try:
            return base_template.format(**formatting_data)
        except KeyError as e:
            current_app.logger.error(f"Missing a required placeholder to format the prompt: {e}")
            raise ValueError(f"Prompt template is missing a required variable: {e}")


# ----------------------------------------------------------------
# Module-level singleton helper.
# ----------------------------------------------------------------
_prompt_service_instance: PromptService | None = None


def get_prompt_service() -> PromptService:
    """
    Returns a process-local PromptService singleton.

    PromptService is stateless after construction (it only reads the YAML
    file once), so a single instance is safe to share across requests.
    """
    global _prompt_service_instance
    if _prompt_service_instance is None:
        _prompt_service_instance = PromptService()
    return _prompt_service_instance
