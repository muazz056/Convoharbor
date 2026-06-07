# chat_project/app/services/text_cleaner_service.py
import re
from flask import current_app


def clean_extracted_text(text: str) -> str:
    """
    A robust function to clean text extracted from various document types (PDF, DOCX, TXT).
    Handles common issues in document extraction:
    - Removes control characters and null bytes
    - Fixes common PDF extraction issues (fragmented text, bad line breaks)
    - Cleans up Word document artifacts
    - Normalizes whitespace and line endings
    - Preserves intentional paragraph breaks
    """
    if not text:
        return ""

    # Log original text length for debugging
    original_length = len(text)
    if hasattr(current_app, 'logger'):
        current_app.logger.info(f"🧹 Text cleaner: Original text length: {original_length} chars")

    # 1. Remove null bytes, control characters, and zero-width characters
    # Keep most Unicode, only remove truly problematic characters
    cleaned_text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F\u200B-\u200D\uFEFF]', '', text)

    # 2. Replace Unicode quotation marks and apostrophes with ASCII ones
    cleaned_text = re.sub(r'[''‚‛`]', "'", cleaned_text)
    cleaned_text = re.sub(r'[""„‟]', '"', cleaned_text)

    # 3. Fix common PDF extraction issues
    # Join single letters that are likely fragmented (e.g., "t h i s" -> "this")
    cleaned_text = re.sub(r'(?<=\s)([a-zA-Z])\s(?=[a-zA-Z]\s|[a-zA-Z]$)', r'\1', cleaned_text)
    # Fix words broken by line breaks with hyphen
    cleaned_text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', cleaned_text)

    # 4. Clean up Word document artifacts
    # Remove section breaks, page breaks, and other Word-specific markers
    cleaned_text = re.sub(r'\f|\v|\r', '\n', cleaned_text)
    cleaned_text = re.sub(r'_{3,}|\*{3,}|={3,}|-{3,}', '', cleaned_text)

    # 5. Normalize whitespace while preserving paragraph structure
    # Replace multiple spaces/tabs with single space
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)
    # Normalize line endings and preserve intentional paragraph breaks
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)  # Max 2 newlines
    cleaned_text = re.sub(r'[ \t]+\n', '\n', cleaned_text)  # Remove trailing spaces
    cleaned_text = re.sub(r'\n[ \t]+', '\n', cleaned_text)  # Remove leading spaces

    # 6. Final cleanup
    # Remove only truly problematic characters, keep Unicode/international text
    # Only remove control characters and invalid Unicode, keep printable Unicode
    cleaned_text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', cleaned_text)

    final_text = cleaned_text.strip()
    final_length = len(final_text)

    # Log cleaning results for debugging
    if hasattr(current_app, 'logger'):
        current_app.logger.info(f"🧹 Text cleaner: Final text length: {final_length} chars (reduced by {original_length - final_length})")
        if final_length == 0:
            current_app.logger.warning(f"🧹 Text cleaner: ALL TEXT WAS REMOVED! Original preview: {repr(text[:200])}")
        elif final_length < 50:
            current_app.logger.warning(f"🧹 Text cleaner: Very short result: {repr(final_text)}")

    return final_text


def test_clean_sample_text():
    """Test function to see how the cleaner handles different types of text"""
    test_cases = [
        "Simple ASCII text with numbers 123",
        "Text with accents: café, résumé, piñata",
        "Special symbols: @#$%^&*()_+-=[]{}|;':\",./<>?",
        "Unicode: 🔥 emoji, ñ, é, ü, ç",
        "Mixed: Hello world! This is a test with café and résumé.",
        "\x00\x01\x02Control\x03chars\x04here\x05",
        "Line\nbreaks\r\nand\ttabs",
    ]

    results = []
    for i, test in enumerate(test_cases):
        cleaned = clean_extracted_text(test)
        results.append(f"Test {i+1}: '{test}' -> '{cleaned}' (len: {len(test)} -> {len(cleaned)})")

    return results
