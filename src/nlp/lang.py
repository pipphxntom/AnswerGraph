"""
Language detection and normalization module.

This module provides functionality for:
1. Detecting the language of input text
2. Normalizing text, especially Hinglish
3. Machine translation for non-English queries
"""
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
import cld3

# Configure logging
logger = logging.getLogger(__name__)

# Common mappings for Hinglish normalization
HINGLISH_REPLACEMENTS = {
    # Common misspellings
    "schlrshp": "scholarship",
    "skolarship": "scholarship",
    "skolrshp": "scholarship",
    "exm": "exam",
    "hostel": "hostel",
    "hostl": "hostel",
    "tymtbl": "timetable",
    "timetabl": "timetable",
    "fess": "fees",
    "fee": "fee",
    "dedline": "deadline",
    "dedlin": "deadline",
    "submisn": "submission",
    "submison": "submission",
    "lst": "last",
    "dat": "date",
    
    # Hinglish phrases
    "kab tak": "deadline",
    "kab hai": "when is",
    "kab bharna hai": "when to fill",
    "kab tak bharna hai": "deadline for filling",
    "kitna hai": "how much is",
    "kahan hai": "where is",
    "kaise": "how to",
    "kaise kare": "how to do",
    "kab tak jama": "deadline for submission",
    "kitne din": "how many days",
    "kab se kab tak": "from when to when"
}

# Devanagari to Latin transliteration mapping (simplified)
DEVANAGARI_TO_LATIN = {
    # Hindi vowels
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee',
    'उ': 'u', 'ऊ': 'oo', 'ए': 'e', 'ऐ': 'ai',
    'ओ': 'o', 'औ': 'au',
    
    # Hindi consonants
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    
    # Hindi matras (vowel signs)
    'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u',
    'ू': 'oo', 'े': 'e', 'ै': 'ai', 'ो': 'o',
    'ौ': 'au', '्': '',
    
    # Hindi numerals
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
    
    # Special characters
    'ँ': 'n', 'ं': 'n', 'ः': 'h', '़': ''
}

# Latin to Devanagari transliteration mapping (simplified)
LATIN_TO_DEVANAGARI = {
    # Common Latin representations of Hindi sounds (simplified)
    'a': 'अ', 'aa': 'आ', 'i': 'इ', 'ee': 'ई',
    'u': 'उ', 'oo': 'ऊ', 'e': 'ए', 'ai': 'ऐ',
    'o': 'ओ', 'au': 'औ',
    
    'k': 'क', 'kh': 'ख', 'g': 'ग', 'gh': 'घ', 'ng': 'ङ',
    'ch': 'च', 'chh': 'छ', 'j': 'ज', 'jh': 'झ', 'ny': 'ञ',
    't': 'त', 'th': 'थ', 'd': 'द', 'dh': 'ध', 'n': 'न',
    'p': 'प', 'ph': 'फ', 'b': 'ब', 'bh': 'भ', 'm': 'म',
    'y': 'य', 'r': 'र', 'l': 'ल', 'v': 'व', 'w': 'व',
    'sh': 'श', 's': 'स', 'h': 'ह'
}

# Domain-specific keywords
DOMAIN_KEYWORDS = {
    "scholarship": ["scholarship", "schlrshp", "स्कॉलरशिप", "छात्रवृत्ति"],
    "fee": ["fee", "fees", "tuition", "शुल्क", "फीस"],
    "deadline": ["deadline", "due date", "last date", "अंतिम तिथि", "डेडलाइन"],
    "exam": ["exam", "examination", "test", "परीक्षा", "एग्जाम"],
    "timetable": ["timetable", "schedule", "टाइमटेबल", "समय सारणी"],
    "hostel": ["hostel", "dormitory", "छात्रावास", "हॉस्टल"]
}


def detect_lang(text: str) -> str:
    """
    Detect the language of input text.
    
    Args:
        text: Input text to detect language for
        
    Returns:
        ISO language code (e.g., 'en', 'hi', 'hi-en')
    """
    try:
        # Use CLD3 for language detection
        detection = cld3.get_language(text)
        
        if not detection or detection.is_reliable is False:
            logger.warning(f"Language detection not reliable for: '{text[:50]}...'")
            return "en"  # Default to English
        
        lang_code = detection.language
        
        # Special handling for Hinglish (mix of Hindi and English)
        if lang_code == "hi":
            # Check if there's a significant amount of Latin script
            latin_chars = sum(1 for c in text if ord('a') <= ord(c.lower()) <= ord('z'))
            if latin_chars / len(text) > 0.25:  # If more than 25% Latin characters
                return "hi-en"  # Mark as Hinglish
            
        return lang_code
    
    except Exception as e:
        logger.error(f"Error detecting language: {str(e)}")
        return "en"  # Default to English on error


def normalize_hinglish(text: str) -> str:
    """
    Normalize Hinglish text by converting to standardized English.
    
    Args:
        text: Input Hinglish text
        
    Returns:
        Normalized English text
    """
    # 1. Convert any Devanagari to Latin
    latin_text = transliterate_devanagari_to_latin(text)
    
    # 2. Apply common Hinglish replacements
    normalized = apply_hinglish_replacements(latin_text)
    
    # 3. Normalize numbers
    normalized = normalize_numbers(normalized)
    
    # 4. Fix common domain-specific terms
    normalized = fix_domain_terms(normalized)
    
    return normalized


def transliterate_devanagari_to_latin(text: str) -> str:
    """
    Transliterate Devanagari script to Latin alphabet.
    
    Args:
        text: Input text potentially containing Devanagari script
        
    Returns:
        Text with Devanagari converted to Latin
    """
    # Check if there's any Devanagari in the text
    has_devanagari = any(0x900 <= ord(c) <= 0x97F for c in text)
    
    if not has_devanagari:
        return text
    
    # Simple character-by-character replacement (not linguistically perfect)
    result = ""
    i = 0
    while i < len(text):
        if 0x900 <= ord(text[i]) <= 0x97F:  # Devanagari Unicode range
            # Try to match longer sequences first
            found = False
            for j in range(min(3, len(text) - i), 0, -1):
                chunk = text[i:i+j]
                if chunk in DEVANAGARI_TO_LATIN:
                    result += DEVANAGARI_TO_LATIN[chunk]
                    i += j
                    found = True
                    break
                    
            if not found:
                # If no mapping, just add the character as is
                result += text[i]
                i += 1
        else:
            result += text[i]
            i += 1
    
    return result


def apply_hinglish_replacements(text: str) -> str:
    """
    Apply common Hinglish word and phrase replacements.
    
    Args:
        text: Input text
        
    Returns:
        Text with Hinglish terms replaced
    """
    # Normalize to lowercase for matching
    lower_text = text.lower()
    
    # Apply word-level replacements
    for hinglish, english in HINGLISH_REPLACEMENTS.items():
        # Word boundary matching
        pattern = r'\b' + re.escape(hinglish) + r'\b'
        lower_text = re.sub(pattern, english, lower_text)
    
    # Preserve original capitalization where possible
    result = ""
    i = 0
    for j in range(len(lower_text)):
        if lower_text[j] != text[j].lower():
            # This shouldn't happen since we lowercased, but just in case
            result += lower_text[j]
        else:
            result += text[j]
    
    return result


def normalize_numbers(text: str) -> str:
    """
    Normalize numeric expressions in text.
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized numbers
    """
    # Replace Hindi numeric words with digits
    hindi_numbers = {
        "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5",
        "छह": "6", "सात": "7", "आठ": "8", "नौ": "9", "दस": "10",
        "ek": "1", "do": "2", "teen": "3", "char": "4", "panch": "5",
        "cheh": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10"
    }
    
    for hindi, digit in hindi_numbers.items():
        pattern = r'\b' + re.escape(hindi) + r'\b'
        text = re.sub(pattern, digit, text)
    
    # Normalize date formats (e.g., "5 tareek" to "5th")
    text = re.sub(r'(\d+)\s*(?:tareekh|tareek|tarikh|तारीख)', r'\1th', text)
    
    return text


def fix_domain_terms(text: str) -> str:
    """
    Fix domain-specific terminology in the text.
    
    Args:
        text: Input text
        
    Returns:
        Text with corrected domain terminology
    """
    # For each domain category, check for variations
    for category, variations in DOMAIN_KEYWORDS.items():
        for variation in variations:
            if variation in text.lower() and variation != category:
                # Replace with the canonical form
                pattern = r'\b' + re.escape(variation) + r'\b'
                text = re.sub(pattern, category, text, flags=re.IGNORECASE)
    
    return text


def pivot_mt(text: str, src_lang: str, tgt_lang: str = 'en') -> str:
    """
    Translate text from source language to target language.
    
    Args:
        text: Input text to translate
        src_lang: Source language code
        tgt_lang: Target language code (default: 'en')
        
    Returns:
        Translated text (or original if translation not needed/available)
    """
    # Skip translation if already in target language
    if src_lang == tgt_lang:
        return text
    
    # Skip translation if source is Hinglish - we'll normalize instead
    if src_lang == "hi-en":
        return normalize_hinglish(text)
    
    # Skip English or Hindi - we handle these natively
    if src_lang in ["en", "hi"]:
        return text
    
    # Placeholder for actual translation logic
    logger.info(f"Translation required from {src_lang} to {tgt_lang}")
    
    # For now, just return the original text with a note
    # This would be replaced with actual translation API calls
    return f"[TRANSLATION PLACEHOLDER] {text}"


def process_query(text: str) -> Dict[str, Any]:
    """
    Process a query through the full language pipeline.
    
    Args:
        text: Raw query text
        
    Returns:
        Dictionary with language info and normalized text
    """
    # Detect language
    lang = detect_lang(text)
    
    # Normalize based on language
    if lang == "hi-en":
        normalized = normalize_hinglish(text)
    elif lang == "hi":
        # For pure Hindi, transliterate to Latin and then normalize
        latin = transliterate_devanagari_to_latin(text)
        normalized = normalize_hinglish(latin)
    elif lang == "en":
        # For English, apply light normalization for domain terms
        normalized = fix_domain_terms(text.lower())
    else:
        # For other languages, attempt translation
        normalized = pivot_mt(text, lang)
    
    return {
        "original": text,
        "normalized": normalized,
        "detected_language": lang,
        "processing_steps": [
            "language_detection",
            "normalization" if lang in ["en", "hi", "hi-en"] else "translation"
        ]
    }
