"""
Document Cleaner — Normalizes text before it gets chunked and embedded.

=== WHY THIS FILE EXISTS ===
Raw text extracted from PDFs and DOCX files is often messy. It contains:
- Multiple consecutive blank lines
- Hidden control characters (zero-width spaces, null bytes)
- Inconsistent unicode representations (e.g., different types of quotes)
- Stray whitespace

If we embed messy text:
1. The embedding model wastes tokens on garbage characters
2. The semantic representation is degraded (model gets confused by noise)
3. The LLM generation includes these artifacts in its response

This module provides a suite of cleaning functions to standardize text.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/ingestion/parser.py (calls clean_text())
  Input:   Raw string from DocumentLoader
  Output:  Clean string
  Uses:    re (regular expressions), unicodedata

=== WHAT HAPPENS WITHOUT IT ===
- Chunking fails unexpectedly because chunks are filled with invisible characters.
- Token counts are inaccurate.
- LLM outputs look unprofessional ("The revenue in Â Q3 was...").

=== INDUSTRY ALTERNATIVES ===
- unstructured.cleaners: A great open-source suite of regex-based cleaners.
- scrubadub: For PII (Personally Identifiable Information) removal.
- ftfy (fixes text for you): Automatically fixes broken unicode/mojibake.

=== DESIGN PATTERNS ===
- Function Composition: The main clean_text() function composes several
  smaller, specific cleaning functions.
- Pure Functions: Cleaners take a string and return a string without side effects.
  This makes them perfectly testable.
"""

import re
import unicodedata
from app.core.logging import get_logger

logger = get_logger(__name__)


def normalize_unicode(text: str) -> str:
    """
    Standardize unicode representations.

    Why NFKC?
    NFKC (Normalization Form Compatibility Composition) replaces compatibility
    characters with their standard equivalents.
    Example: 'ﬁ' (single ligature character) -> 'fi' (two characters).
    This ensures that vector search matches "finance" even if the PDF
    represented it as "ﬁnance".
    """
    return unicodedata.normalize("NFKC", text)


def remove_control_characters(text: str) -> str:
    """
    Remove unprintable control characters.

    PDFs often contain hidden null bytes (\x00), zero-width spaces (\u200b),
    or vertical tabs (\v). These waste tokens and confuse embeddings.
    We keep standard whitespace: \n, \r, \t.
    """
    # Explanation:
    # \x00-\x08: Null to Backspace
    # \x0b-\x0c: Vertical tab, Form feed
    # \x0e-\x1f: Shift Out to Unit Separator
    # \x7f-\x9f: Delete and C1 control characters
    # \u200b: Zero-width space
    control_chars = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b]')
    return control_chars.sub("", text)


def normalize_whitespace(text: str) -> str:
    """
    Standardize spacing while preserving paragraph structure.

    Rules:
    1. Replace carriage returns (\r\n) with newlines (\n)
    2. Reduce 3+ consecutive newlines to exactly 2 newlines (paragraph boundary)
    3. Reduce 2+ consecutive spaces (or tabs) to a single space
    4. Strip leading/trailing whitespace

    Why keep 2 newlines?
    Double newlines indicate paragraph breaks, which are critical for
    the Recursive Chunker to split text logically.
    """
    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Collapse 3+ newlines into 2 (preserve paragraph breaks, remove excessive gaps)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 3. Collapse multiple spaces/tabs into a single space, but don't touch newlines
    # [^\S\n] matches any whitespace character EXCEPT newline
    text = re.sub(r'[^\S\n]{2,}', ' ', text)

    # 4. Strip edges
    return text.strip()


def remove_citation_brackets(text: str) -> str:
    """
    Optional: Remove academic/wiki citation markers like [1], [23], etc.

    Why? If the RAG system generates its own citations (e.g. [Source 1]),
    existing document citations can confuse the user and the LLM.
    """
    return re.sub(r'\[\d+\]', '', text)


def clean_text(text: str, remove_citations: bool = False) -> str:
    """
    Apply the full cleaning pipeline.

    This is the main entry point for the cleaner module.
    It applies transformations in a specific, logical order.

    Args:
        text: The raw text to clean.
        remove_citations: Whether to strip bracketed numbers like [1].

    Returns:
        The cleaned, normalized string.
    """
    if not text:
        return ""

    original_len = len(text)

    text = normalize_unicode(text)
    text = remove_control_characters(text)
    if remove_citations:
        text = remove_citation_brackets(text)
    text = normalize_whitespace(text)

    cleaned_len = len(text)
    if original_len > 0 and (original_len - cleaned_len) > 500:
        logger.debug(
            "Significant cleaning reduction",
            original=original_len,
            cleaned=cleaned_len,
            removed=original_len - cleaned_len,
        )

    return text
