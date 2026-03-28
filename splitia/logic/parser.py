# ============================================================================
# PARSER.PY
# ============================================================================
# Placeholder functions for future AI integration.
#
# This module is a stub for AI-assisted expense parsing.
# Currently, all functions return mock data.
#
# Future integrations:
# 1. Audio transcription (OpenAI Whisper API or similar)
# 2. Text/ticket OCR parsing (Google Vision API or similar)
# 3. Named Entity Recognition (NER) to extract amounts and names
#
# For now: Just structure the code so you can add real APIs later.
# ============================================================================


def parse_audio_expense(audio_text):
    """
    Parse an audio transcription to extract expense information.
    
    INPUT EXAMPLE:
        "I paid twenty-five dollars for pizza with three people"
    
    OUTPUT SHOULD BE:
        {
            'description': str,        # What was bought? (e.g., "Pizza")
            'total_amount': float,     # Total cost
            'participants': list,      # Who participated? (names or generic)
            'confidence': float,       # How confident is the parsing? (0-1)
            'raw_text': str
        }
    
    FUTURE: Integrate with:
    - OpenAI Whisper (for audio to text)
    - spaCy or BERT (for NER - extract entities like amounts and names)
    - Custom rules for currency detection
    
    Args:
        audio_text (str): Transcribed audio text
    
    Returns:
        dict: Structured expense data
    """
    
    # TODO: Implement real parsing with NLP
    # For now, return mock data
    
    mock_result = {
        'description': 'AI Parsed Expense',
        'total_amount': 0.0,
        'participants': [],
        'confidence': 0.0,
        'raw_text': audio_text,
        'status': 'placeholder',
        'note': 'Real audio parsing coming soon!'
    }
    
    return mock_result


def parse_ticket_and_audio(ticket_text, audio_text):
    """
    Parse both a ticket (image/text) and audio to extract expense info.
    This combines two sources for better accuracy.
    
    SCENARIO:
    - User takes a photo of a receipt (OCR extracted as ticket_text)
    - User also speaks what the expense is for (transcribed as audio_text)
    - Combine to get best guess at who owes what
    
    FUTURE: Integrate with:
    - Google Cloud Vision (for receipt OCR)
    - Tesseract (open-source OCR)
    - Fuzzy matching to reconcile ticket vs. audio data
    
    Args:
        ticket_text (str): Extracted text from receipt/invoice
        audio_text (str): Transcribed audio from user
    
    Returns:
        dict: Combined structured expense data
    """
    
    # TODO: Implement real dual-source parsing
    # For now, return mock data
    
    mock_result = {
        'description': 'Receipt + Audio Expense',
        'total_amount': 0.0,
        'participants': [],
        'confidence': 0.0,
        'ticket_text': ticket_text,
        'audio_text': audio_text,
        'status': 'placeholder',
        'note': 'Real dual-source parsing coming soon!'
    }
    
    return mock_result


def extract_amount(text):
    """
    Help function: Extract monetary amounts from text.
    
    EXAMPLES:
    - "It cost $25" → 25.0
    - "fifty dollars" → 50.0
    - "USD 100.50" → 100.50
    
    FUTURE: Use regex + word-to-number conversion
    
    Args:
        text (str): Input text
    
    Returns:
        list: List of found amounts
    """
    # TODO: Implement real extraction
    return []


def extract_participants(text, group_members=None):
    """
    Help function: Extract participant names from text.
    
    EXAMPLES:
    - "with Alice and Bob" → ['Alice', 'Bob']
    - "John paid, 3 people split" → ['John', and 2 others]
    
    FUTURE: Use NER + fuzzy matching against group members
    
    Args:
        text (str): Input text
        group_members (list): Known members to match against
    
    Returns:
        list: Extracted participant names/IDs
    """
    # TODO: Implement real extraction with NER
    return []


def estimate_number_of_people(text):
    """
    Help function: Try to estimate the number of people in an expense.
    
    EXAMPLES:
    - "split 3 ways" → 3
    - "for two of us" → 2
    - "each person pays" → unknown
    
    Args:
        text (str): Input text
    
    Returns:
        int: Estimated count, or None if unknown
    """
    # TODO: Implement regex pattern matching
    return None


# ============================================================================
# FUTURE API INTEGRATION EXAMPLES
# ============================================================================

"""
EXAMPLE 1: Using OpenAI Whisper for audio transcription
----
import openai

def transcribe_audio(audio_file_path):
    with open(audio_file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript["text"]

EXAMPLE 2: Using spaCy for Named Entity Recognition
----
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_entities(text):
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    return entities

EXAMPLE 3: Using regex for amount extraction
----
import re

def extract_amounts(text):
    pattern = r'\$?(\d+\.?\d*)'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]

"""
