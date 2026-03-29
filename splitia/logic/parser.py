import json
import os
import re
import ssl
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on environment
    OpenAI = None

try:
    import assemblyai as aai
except ImportError:  # pragma: no cover - depends on environment
    aai = None

try:
    import certifi
except ImportError:  # pragma: no cover - depends on environment
    certifi = None

from .schemas import ExpenseDraft, ExpenseParticipantDraft

load_dotenv()

_AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.ogg', '.webm'}
_DEFAULT_TRANSCRIPT = 'Cena total 24000 pesos, pague yo, participaron Juan y Sofi.'
_DEFAULT_TRANSCRIPTION_MODEL = os.getenv('OPENAI_AUDIO_MODEL', 'gpt-4o-transcribe')
_DEFAULT_PARSER_MODEL = os.getenv('ASSEMBLYAI_LLM_MODEL', 'gemini-2.5-flash-lite')


def _get_assemblyai_key() -> str:
    return os.getenv('ASSEMBLYAI_API_KEY', '').strip()


def _has_assemblyai() -> bool:
    return bool(_get_assemblyai_key() and aai is not None)


def _get_api_key() -> str:
    return os.getenv('OPENAI_API_KEY', '').strip()


def _has_openai() -> bool:
    return bool(_get_api_key() and OpenAI is not None)


def _get_openai_client() -> OpenAI | None:
    if not _has_openai():
        return None
    return OpenAI(api_key=_get_api_key())


def _sanitize_openai_error(exc: Exception) -> str:
    message = str(exc).lower()

    if 'invalid_api_key' in message or 'incorrect api key' in message or '401' in message:
        return 'La configuracion de OpenAI no es valida en este momento. Probá escribirlo manualmente mientras actualizamos la key.'

    if 'rate limit' in message or '429' in message:
        return 'OpenAI está rechazando la solicitud por límite de uso. Probá de nuevo en unos segundos.'

    return 'No pudimos transcribir el audio con OpenAI en este momento.'


def _sanitize_assemblyai_error(exc: Exception) -> str:
    message = str(exc).lower()

    if 'unauthorized' in message or '401' in message or 'api key' in message:
        return 'La configuracion de AssemblyAI no es valida en este momento. Probá escribirlo manualmente mientras actualizamos la key.'

    if 'payment' in message or 'credit' in message or 'quota' in message or 'limit' in message or '429' in message:
        return 'AssemblyAI está rechazando la solicitud por límite o cuota. Probá de nuevo en unos segundos.'

    return 'No pudimos transcribir el audio con AssemblyAI en este momento.'


def _sanitize_assemblyai_gateway_error(exc: Exception) -> str:
    message = str(exc).lower()

    if 'unauthorized' in message or '401' in message or 'api key' in message:
        return 'La configuracion de AssemblyAI LLM Gateway no es valida en este momento.'

    if '429' in message or 'quota' in message or 'limit' in message:
        return 'AssemblyAI LLM Gateway está rechazando la solicitud por límite o cuota.'

    return 'No pudimos estructurar el transcript con AssemblyAI en este momento.'


def _parse_number(raw_value: str | int | float | None) -> float:
    if raw_value is None or raw_value == '':
        return 0.0

    if isinstance(raw_value, (int, float)):
        return round(float(raw_value), 2)

    value = str(raw_value).strip().replace('$', '').replace('€', '')
    value = value.replace('ars', '').replace('usd', '')
    value = value.replace('pesos argentinos', '').replace('pesos', '').replace('peso', '').strip()

    if ',' in value and '.' in value:
        value = value.replace('.', '').replace(',', '.')
    elif '.' in value and value.count('.') >= 1 and ',' not in value:
        chunks = value.split('.')
        if all(chunk.isdigit() for chunk in chunks) and len(chunks[-1]) == 3:
            value = ''.join(chunks)
        else:
            value = value.replace('.', '.')
    else:
        value = value.replace(',', '.')

    try:
        return round(float(value), 2)
    except ValueError:
        return 0.0


def _parse_spoken_amount(text: str) -> float:
    match = re.search(
        r'(\d[\d.,]*)\s*(mil|mil pesos|mil ars|lucas|luca)\b',
        text,
    )
    if not match:
        return 0.0

    base_amount = _parse_number(match.group(1))
    if base_amount <= 0:
        return 0.0

    return round(base_amount * 1000, 2)


def _normalize_whitespace(value: str) -> str:
    return ' '.join((value or '').strip().split())


def _normalize_name(name: str) -> str:
    clean_name = _normalize_whitespace(name)
    if not clean_name:
        return ''
    return ' '.join(piece.capitalize() for piece in clean_name.split())


def _safe_json_loads(raw_content: str) -> dict:
    if not raw_content:
        return {}

    content = raw_content.strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _expense_draft_json_schema() -> dict:
    return {
        'name': 'expense_draft',
        'strict': True,
        'schema': {
            'type': 'object',
            'properties': {
                'description': {'type': 'string'},
                'total_amount': {'type': 'number'},
                'currency': {'type': 'string'},
                'payer_name': {'type': 'string'},
                'participants': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'amount': {'type': 'number'},
                        },
                        'required': ['name', 'amount'],
                        'additionalProperties': False,
                    },
                },
                'tip_amount': {'type': 'number'},
                'notes': {'type': 'string'},
                'confidence': {'type': 'number'},
                'needs_review': {'type': 'boolean'},
            },
            'required': [
                'description',
                'total_amount',
                'currency',
                'payer_name',
                'participants',
                'tip_amount',
                'notes',
                'confidence',
                'needs_review',
            ],
            'additionalProperties': False,
        },
    }


def _build_ssl_context():
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _guess_description(text: str) -> str:
    match = re.search(
        r'(?:por|de|fue|era|compramos|compre|compré|cena|almuerzo|desayuno)\s+([a-záéíóúñ ]+?)(?:,|\.| total| pago| pagó| participaron|$)',
        text
    )
    if match:
        candidate = _normalize_whitespace(match.group(1))
        if candidate and not re.search(r'\d', candidate):
            return candidate.capitalize()

    for keyword in ['cena', 'almuerzo', 'desayuno', 'supermercado', 'taxi', 'uber', 'pizza', 'asado']:
        if keyword in text:
            return keyword.capitalize()

    return 'Expense from chat'


def _extract_total(text: str) -> float:
    spoken_amount = _parse_spoken_amount(text)
    if spoken_amount > 0:
        return spoken_amount

    patterns = [
        r'(?:total|importe|monto|salio|salió|fue)\s*(?:de\s*)?(\d[\d.,]*)',
        r'(\d[\d.,]*)\s*(?:pesos argentinos|pesos|ars|usd|dolares|dólares)',
        r'(?:pague|pagué|pago|pagó|abon(?:e|é|o|ó))\s*(?:yo\s*)?(\d[\d.,]*)',
        r'\b(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_number(match.group(1))
    return 0.0


def _extract_tip_amount(text: str) -> float:
    match = re.search(r'(?:propina|tip)\s*(?:de\s*)?(\d[\d.,]*)', text)
    return _parse_number(match.group(1)) if match else 0.0


def _extract_currency(text: str) -> str:
    if any(token in text for token in ['usd', 'dolar', 'dólar', 'dolares', 'dólares']):
        return 'USD'
    return 'ARS'


def _extract_payer_name(text: str) -> str:
    yo_patterns = [
        r'\byo pag(?:ue|ué)\b',
        r'\blo pag(?:ue|ué) yo\b',
        r'\bpagu(?:e|é) yo\b',
    ]
    if any(re.search(pattern, text) for pattern in yo_patterns):
        return 'Yo'

    match = re.search(
        r'(?:pag(?:o|ó)|pagaron|paga|abon(?:o|ó)|puso)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)?)',
        text
    )
    if match:
        return _normalize_name(match.group(1))

    return 'Unknown'


def _extract_participant_names(text: str, payer_name: str) -> list[str]:
    match = re.search(
        r'(?:particip(?:an|amos|aron)|entre|dividido entre|split entre|para|eramos|éramos)\s+(.+?)(?:\.| total| pago| pagó|$)',
        text
    )
    if match:
        names = [
            _normalize_name(piece)
            for piece in re.split(r',| y | e ', match.group(1))
            if _normalize_whitespace(piece)
        ]
        unique_names = [name for name in dict.fromkeys(names) if name]
        if unique_names:
            return unique_names

    return [payer_name] if payer_name and payer_name != 'Unknown' else []


def _build_participants(names: list[str], total_amount: float) -> list[ExpenseParticipantDraft]:
    if not names:
        return []

    share = round(total_amount / len(names), 2) if total_amount else 0.0
    return [ExpenseParticipantDraft(name=name, amount=share) for name in names]


def _normalize_participants(raw_participants, total_amount: float) -> list[ExpenseParticipantDraft]:
    if not isinstance(raw_participants, list):
        return []

    normalized = []
    fallback_names = []

    for participant in raw_participants:
        if isinstance(participant, dict):
            name = _normalize_name(str(participant.get('name') or ''))
            amount = _parse_number(participant.get('amount'))
        else:
            name = _normalize_name(str(participant or ''))
            amount = 0.0

        if not name:
            continue

        fallback_names.append(name)
        normalized.append(ExpenseParticipantDraft(name=name, amount=amount))

    if not normalized:
        return []

    if any(participant.amount <= 0 for participant in normalized):
        return _build_participants(fallback_names, total_amount)

    return normalized


def _fallback_parse_transcript(
    transcript: str,
    transcription_used_ai: bool = False,
    transcription_source: str = 'demo',
) -> ExpenseDraft:
    normalized_text = transcript.lower().strip()
    total_amount = _extract_total(normalized_text)
    payer_name = _extract_payer_name(normalized_text)
    participants = _build_participants(
        _extract_participant_names(normalized_text, payer_name),
        total_amount,
    )
    tip_amount = _extract_tip_amount(normalized_text)

    confidence = 0.3
    if total_amount > 0:
        confidence += 0.2
    if payer_name != 'Unknown':
        confidence += 0.2
    if participants:
        confidence += 0.15
    if transcription_used_ai:
        confidence += 0.05

    return ExpenseDraft(
        description=_guess_description(normalized_text),
        total_amount=total_amount,
        currency=_extract_currency(normalized_text),
        payer_name=payer_name,
        participants=participants,
        tip_amount=tip_amount,
        notes=(
            'parser=fallback; transcription='
            + transcription_source
            + f'; transcript="{transcript}"'
        ),
        confidence=min(round(confidence, 2), 0.8),
        needs_review=True,
    )


def _normalize_structured_draft(
    candidate: dict,
    transcript: str,
    transcription_used_ai: bool,
    parser_name: str,
    transcription_source: str = 'manual',
) -> ExpenseDraft:
    total_amount = _parse_number(candidate.get('total_amount'))
    currency = str(candidate.get('currency') or 'ARS').upper()
    if currency not in {'ARS', 'USD'}:
        currency = 'ARS'

    payer_name = _normalize_name(str(candidate.get('payer_name') or 'Unknown')) or 'Unknown'
    participants = _normalize_participants(candidate.get('participants') or [], total_amount)
    tip_amount = _parse_number(candidate.get('tip_amount'))
    description = _normalize_whitespace(str(candidate.get('description') or '')) or _guess_description(transcript.lower())
    notes = _normalize_whitespace(str(candidate.get('notes') or ''))
    confidence = candidate.get('confidence')

    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.86 if transcription_used_ai else 0.72

    return ExpenseDraft(
        description=description,
        total_amount=total_amount,
        currency=currency,
        payer_name=payer_name,
        participants=participants,
        tip_amount=tip_amount,
        notes=(
            'parser='
            + parser_name
            + '; transcription='
            + transcription_source
            + '; '
            + (notes if notes else 'parsed from transcript')
            + f'; transcript="{transcript}"'
        ),
        confidence=max(0.0, min(round(confidence, 2), 0.98)),
        needs_review=bool(candidate.get('needs_review', True)),
    )


def _assemblyai_structured_parse_transcript(
    transcript: str,
    transcription_used_ai: bool = False,
    transcription_source: str = 'manual',
) -> ExpenseDraft | None:
    if not _has_assemblyai():
        return None

    prompt = (
        'Extrae un borrador de gasto estructurado a partir de una transcripcion en español. '
        'No inventes datos. Si algo no está claro, usa "Unknown", lista vacía o 0 según corresponda. '
        'Asumí ARS salvo que la transcripción indique claramente USD. '
        'needs_review debe ser true. '
        'Si hay monto total y participantes detectados pero no amounts individuales, repartí en partes iguales. '
        'confidence debe ser un número entre 0 y 1.'
    )

    payload = {
        'model': _DEFAULT_PARSER_MODEL,
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': transcript},
        ],
        'response_format': {
            'type': 'json_schema',
            'json_schema': _expense_draft_json_schema(),
        },
    }

    try:
        req = urllib_request.Request(
            'https://llm-gateway.assemblyai.com/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'authorization': _get_assemblyai_key(),
                'content-type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=30, context=_build_ssl_context()) as response:
            raw_response = json.loads(response.read().decode('utf-8'))
    except (urllib_error.HTTPError, urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None

    choices = raw_response.get('choices') or []
    if not choices:
        return None

    message = choices[0].get('message') or {}
    content = message.get('content') or ''

    parsed = _safe_json_loads(content)
    if not parsed:
        return None

    return _normalize_structured_draft(
        parsed,
        transcript,
        transcription_used_ai,
        parser_name='assemblyai-structured',
        transcription_source=transcription_source,
    )


def _transcribe_with_assemblyai(audio_file_path: str) -> str:
    aai.settings.api_key = _get_assemblyai_key()
    transcriber = aai.Transcriber()
    config = aai.TranscriptionConfig(speech_models=['universal-2'])

    try:
        transcript = transcriber.transcribe(audio_file_path, config=config)
    except Exception as exc:
        raise RuntimeError(_sanitize_assemblyai_error(exc)) from exc

    if getattr(transcript, 'status', None) == aai.TranscriptStatus.error:
        raise RuntimeError(_sanitize_assemblyai_error(Exception(transcript.error)))

    text = getattr(transcript, 'text', None)
    if not text:
        raise RuntimeError('No se obtuvo texto de la transcripcion')

    return _normalize_whitespace(text)


def transcribe_audio_with_source(audio_file_path: str) -> tuple[str, str]:
    path = Path(audio_file_path)

    if not path.exists():
        raise FileNotFoundError(f'Archivo no encontrado: {audio_file_path}')

    if path.suffix.lower() not in _AUDIO_EXTS:
        raise ValueError(f'Formato de audio no soportado: {path.suffix}')

    if _has_assemblyai():
        return _transcribe_with_assemblyai(audio_file_path), 'assemblyai'

    client = _get_openai_client()
    if not client:
        return _DEFAULT_TRANSCRIPT, 'demo'

    try:
        with open(path, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model=_DEFAULT_TRANSCRIPTION_MODEL,
                file=audio_file,
            )
    except Exception as exc:
        raise RuntimeError(_sanitize_openai_error(exc)) from exc

    text = response.text if hasattr(response, 'text') else None
    if not text:
        raise RuntimeError('No se obtuvo texto de la transcripcion')

    return _normalize_whitespace(text), 'openai'


def transcribe_audio(audio_file_path: str) -> str:
    transcript, _source = transcribe_audio_with_source(audio_file_path)
    return transcript


def parse_transcript(
    transcript: str,
    transcription_used_ai: bool = False,
    transcription_source: str = 'manual',
) -> ExpenseDraft:
    normalized_transcript = _normalize_whitespace(transcript)
    structured_draft = _assemblyai_structured_parse_transcript(
        normalized_transcript,
        transcription_used_ai=transcription_used_ai,
        transcription_source=transcription_source,
    )
    if structured_draft is not None:
        return structured_draft

    return _fallback_parse_transcript(
        normalized_transcript,
        transcription_used_ai=transcription_used_ai,
        transcription_source=transcription_source,
    )


def parse_audio_to_draft(audio_file_path: str) -> ExpenseDraft:
    transcript, source = transcribe_audio_with_source(audio_file_path)
    return parse_transcript(
        transcript,
        transcription_used_ai=_has_openai(),
        transcription_source=source,
    )
