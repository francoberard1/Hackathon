from __future__ import annotations

import json
import os
import re
import ssl
import unicodedata
from datetime import date, datetime, timedelta
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

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - depends on environment
    ZoneInfo = None

from .schemas import ExpenseDraft, ExpenseParticipantDraft

load_dotenv()

_AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.ogg', '.webm'}
_DEFAULT_TRANSCRIPT = 'Cena total 24000 pesos, pague yo, participaron Juan y Sofi.'
_DEFAULT_TRANSCRIPTION_MODEL = os.getenv('OPENAI_AUDIO_MODEL', 'gpt-4o-transcribe')
_DEFAULT_PARSER_MODEL = os.getenv('ASSEMBLYAI_LLM_MODEL', 'gemini-2.5-flash-lite')
_AMOUNT_FRAGMENT = r'(\d[\d.,]*(?:\s*(?:mil|mil pesos|mil ars|lucas|luca))?)'
_DEFAULT_TIMEZONE = os.getenv('APP_TIMEZONE', 'America/Argentina/Buenos_Aires')
_SPANISH_MONTHS = {
    'enero': 1,
    'febrero': 2,
    'marzo': 3,
    'abril': 4,
    'mayo': 5,
    'junio': 6,
    'julio': 7,
    'agosto': 8,
    'septiembre': 9,
    'setiembre': 9,
    'octubre': 10,
    'noviembre': 11,
    'diciembre': 12,
}


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


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value or '')
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def _normalize_match_text(value: str) -> str:
    text = _strip_accents(_normalize_whitespace(value).lower())
    text = text.replace('coca cola zero', 'coca light')
    text = text.replace('coca zero', 'coca light')
    text = text.replace('coca-cola', 'coca cola')
    text = text.replace('tagliatella', 'tagliatela')
    text = text.replace('pene', 'penne')
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_tokens(value: str) -> list[str]:
    text = _normalize_match_text(value)
    if not text:
        return []
    tokens = []
    for token in text.split():
        tokens.append(token)
        if len(token) > 4 and token.endswith('s'):
            tokens.append(token[:-1])
    seen = []
    for token in tokens:
        if token and token not in seen:
            seen.append(token)
    return seen


def _normalize_group_members(group_members: list[str] | None) -> list[str]:
    if not isinstance(group_members, list):
        return []

    normalized = []
    seen = set()
    for member in group_members:
        clean_member = _normalize_name(str(member or ''))
        if not clean_member:
            continue
        member_key = clean_member.lower()
        if member_key in seen:
            continue
        seen.add(member_key)
        normalized.append(clean_member)

    return normalized


def _parse_amount_phrase(raw_value: str | None) -> float:
    if not raw_value:
        return 0.0

    normalized = _normalize_whitespace(str(raw_value).lower())
    if any(token in normalized for token in [' mil', 'mil ', 'luca', 'lucas']):
        spoken_amount = _parse_spoken_amount(normalized)
        if spoken_amount > 0:
            return spoken_amount

    return _parse_number(normalized)


def _split_amount_evenly(total_amount: float, count: int) -> list[float]:
    if count <= 0:
        return []

    total_cents = int(round(total_amount * 100))
    base_share = total_cents // count
    remainder = total_cents - (base_share * count)

    shares = []
    for index in range(count):
        cents = base_share + (1 if index < remainder else 0)
        shares.append(round(cents / 100, 2))

    return shares


def _mentions_equal_split(text: str) -> bool:
    patterns = [
        r'partes iguales',
        r'divid(?:imos|ieron)\s+igual',
        r'divid(?:imos|ieron)\s+en\s+partes\s+iguales',
        r'entre\s+todos',
        r'a medias',
        r'mitad y mitad',
        r'todos\s+pagamos\s+lo mismo',
        r'todos\s+deben\s+lo mismo',
        r'en partes iguales',
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _mentions_all_group(text: str) -> bool:
    return bool(
        re.search(r'\btodos\b', text)
        or re.search(r'fuimos\s+todos', text)
        or re.search(r'estabamos\s+todos', text)
        or re.search(r'estábamos\s+todos', text)
    )


def _mentions_remainder_equal_split(text: str) -> bool:
    return bool(
        re.search(r'resto\s+(?:lo\s+)?divid(?:imos|ieron)?\s+en\s+partes\s+iguales', text)
        or re.search(r'resto\s+(?:en|a)\s+partes\s+iguales', text)
        or re.search(r'lo\s+que\s+queda\s+(?:en|a)\s+partes\s+iguales', text)
    )


def _extract_explicit_participant_names(text: str, group_members: list[str]) -> list[str]:
    patterns = [
        r'(?:particip(?:an|amos|aron)|entre|dividido entre|split entre|eramos|éramos)\s+(.+?)(?:\.| total| pago| pagó|$)',
        r'fuimos\s+(.+?)(?:,|\.| y gast| gast| pag| total|$)',
    ]
    best_mentioned = []

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        mentioned = _find_group_member_mentions(match.group(1), group_members)
        if len(mentioned) > len(best_mentioned):
            best_mentioned = mentioned

    pre_payment_segment = re.split(r'\b(?:pag(?:o|ó)|salio|salió|total|gast(?:amos|e|é|aron))\b', text, maxsplit=1)[0]
    mentioned_before_payment = _find_group_member_mentions(pre_payment_segment, group_members)
    if len(mentioned_before_payment) > len(best_mentioned):
        best_mentioned = mentioned_before_payment

    return best_mentioned


def _find_group_member_mentions(text: str, group_members: list[str]) -> list[str]:
    mentioned = []
    normalized_text = f' {text.lower()} '

    for member in group_members:
        member_tokens = [re.escape(token.lower()) for token in member.split() if token]
        if not member_tokens:
            continue

        full_name_pattern = r'\b' + r'\s+'.join(member_tokens) + r'\b'
        first_name_pattern = r'\b' + member_tokens[0] + r'\b'

        if re.search(full_name_pattern, normalized_text) or re.search(first_name_pattern, normalized_text):
            mentioned.append(member)

    return mentioned


def _extract_member_amounts(text: str, group_members: list[str], payer_name: str = 'Unknown') -> dict[str, float]:
    explicit_amounts = {}
    normalized_text = text.lower()

    for member in group_members:
        member_patterns = [
            rf'\b{re.escape(member.lower())}\b[^.\n,;:]*?(?:debe|deberia|debería|comio|comió|consumio|consumió|gasto|gastó|por)\s*(?:unos?\s*)?{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
            rf'\ba\s+{re.escape(member.lower())}\b[^.\n,;:]*?(?:le\s+toca|le\s+tocan|le\s+corresponde|le\s+corresponden|le\s+quedo|le\s+quedó)\s*(?:un\s+gasto\s+de\s*|unos?\s*)?{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
            rf'\b{re.escape(member.lower())}\b[^.\n,;:]*?(?:le\s+toca|le\s+tocan|le\s+corresponde|le\s+corresponden)\s*(?:un\s+gasto\s+de\s*|unos?\s*)?{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
        ]

        for pattern in member_patterns:
            match = re.search(pattern, normalized_text)
            if not match:
                continue

            amount = _parse_amount_phrase(match.group(1))
            if amount > 0:
                explicit_amounts[member] = amount
                break

    if payer_name and payer_name != 'Unknown' and payer_name in group_members and payer_name not in explicit_amounts:
        pronoun_patterns = [
            rf'\ba\s+(?:el|él)\b[^.\n,;:]*?(?:le\s+corresponde|le\s+corresponden|le\s+toca|le\s+tocan|le\s+quedo|le\s+quedó|debe|gasto|gastó|comio|comió)\s*(?:un\s+gasto\s+de\s*|unos?\s*)?{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
            rf'\b(?:el|él)\b[^.\n,;:]*?(?:debe|gasto|gastó|comio|comió|pagó|puso)\s*(?:unos?\s*)?{_AMOUNT_FRAGMENT}',
            rf'\b(?:el|él)\b[^.\n,;:]*?(?:tuvo|tiene)\s+(?:un\s+gasto\s+de\s*|unos?\s*)?{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
            rf'\b(?:tuvo|tiene)\s+un\s+gasto\s+de\s*{_AMOUNT_FRAGMENT}(?:\s+de\s+gasto)?',
        ]

        for pattern in pronoun_patterns:
            match = re.search(pattern, normalized_text)
            if not match:
                continue

            amount = _parse_amount_phrase(match.group(1))
            if amount > 0:
                explicit_amounts[payer_name] = amount
                break

    return explicit_amounts


def _resolve_narrator_member(
    text: str,
    group_members: list[str],
    mentioned_members: list[str],
    narrator_name: str | None = None,
) -> str | None:
    yo_patterns = [
        r'\byo pag(?:ue|ué)\b',
        r'\blo pag(?:ue|ué) yo\b',
        r'\bpagu(?:e|é) yo\b',
        r'\byo puse\b',
        r'\byo invite\b',
        r'\byo invité\b',
    ]
    if not any(re.search(pattern, text) for pattern in yo_patterns):
        return None

    normalized_narrator = _normalize_name(narrator_name or '')
    if normalized_narrator and normalized_narrator in group_members:
        return normalized_narrator

    missing_members = [member for member in group_members if member not in mentioned_members]
    if len(missing_members) == 1:
        return missing_members[0]

    return None


def _resolve_payer_name(
    text: str,
    group_members: list[str],
    narrator_name: str | None = None,
) -> str:
    mentioned_members = _find_group_member_mentions(text, group_members)
    narrator_member = _resolve_narrator_member(text, group_members, mentioned_members, narrator_name=narrator_name)
    if narrator_member:
        return narrator_member

    extracted_payer = _extract_payer_name(text)
    if extracted_payer != 'Unknown':
        normalized_extracted = _normalize_name(extracted_payer)
        for member in group_members:
            if member.lower() == normalized_extracted.lower():
                return member
        return normalized_extracted

    return 'Unknown'


def _resolve_participant_names(
    text: str,
    group_members: list[str],
    payer_name: str,
) -> list[str]:
    explicit_participants = _extract_explicit_participant_names(text, group_members)
    mentioned_members = _find_group_member_mentions(text, group_members)

    if group_members:
        if _mentions_all_group(text):
            return group_members

        if explicit_participants:
            return explicit_participants

        if _mentions_equal_split(text):
            if mentioned_members:
                return mentioned_members
            return group_members

        if mentioned_members:
            return mentioned_members

        return group_members

    if explicit_participants:
        return explicit_participants

    return [payer_name] if payer_name and payer_name != 'Unknown' else []


def _build_participants_from_context(
    text: str,
    total_amount: float,
    group_members: list[str],
    payer_name: str,
) -> list[ExpenseParticipantDraft]:
    participant_names = _resolve_participant_names(text, group_members, payer_name)
    if not participant_names:
        return []

    explicit_amounts = _extract_member_amounts(text, participant_names, payer_name=payer_name)
    if not explicit_amounts:
        return _build_participants(participant_names, total_amount)

    remaining_names = [name for name in participant_names if name not in explicit_amounts]
    explicit_total = round(sum(explicit_amounts.values()), 2)
    remaining_total = round(max(total_amount - explicit_total, 0.0), 2)

    participant_amounts = {name: explicit_amounts.get(name, 0.0) for name in participant_names}

    if remaining_names:
        should_split_remaining = (
            _mentions_remainder_equal_split(text)
            or _mentions_equal_split(text)
            or True
        )
        if should_split_remaining:
            split_amounts = _split_amount_evenly(remaining_total, len(remaining_names))
            for index, name in enumerate(remaining_names):
                participant_amounts[name] = split_amounts[index]

    participants = [
        ExpenseParticipantDraft(name=name, amount=round(participant_amounts.get(name, 0.0), 2))
        for name in participant_names
    ]

    if total_amount > 0:
        normalized_total = round(sum(participant.amount for participant in participants), 2)
        difference = round(total_amount - normalized_total, 2)
        if participants and abs(difference) > 0.01:
            participants[-1].amount = round(participants[-1].amount + difference, 2)

    return participants


def _normalize_ticket_items(ticket_items: list[dict] | None) -> list[dict]:
    if not isinstance(ticket_items, list):
        return []

    normalized_items = []
    for index, item in enumerate(ticket_items):
        if not isinstance(item, dict):
            continue

        name = _normalize_whitespace(str(item.get('name') or ''))
        amount = _parse_number(item.get('amount'))
        if not name or amount <= 0:
            continue

        normalized_items.append({
            'index': index,
            'name': name,
            'amount': amount,
            'match_text': _normalize_match_text(name),
            'tokens': _normalize_tokens(name),
        })

    return normalized_items


def _extract_excluded_participants(text: str, group_members: list[str]) -> list[str]:
    excluded = []
    normalized_text = _normalize_match_text(text)

    for member in group_members:
        member_pattern = re.escape(_normalize_match_text(member))
        patterns = [
            rf'\b{member_pattern}\b[^.]*\bno fue\b',
            rf'\b{member_pattern}\b[^.]*\bno vino\b',
            rf'\bmenos\s+{member_pattern}\b',
            rf'\bexcepto\s+{member_pattern}\b',
            rf'\bsin\s+{member_pattern}\b',
        ]
        if any(re.search(pattern, normalized_text) for pattern in patterns):
            excluded.append(member)

    return excluded


def _extract_remainder_target(text: str, group_members: list[str], payer_name: str) -> str | None:
    normalized_text = _normalize_match_text(text)

    for member in group_members:
        member_pattern = re.escape(_normalize_match_text(member))
        if re.search(
            rf'\b(?:el\s+resto|lo\s+que\s+falta|todo\s+lo\s+que\s+falta|todo\s+el\s+resto)\b[^.]*\bpara\s+{member_pattern}\b',
            normalized_text,
        ):
            return member

    if payer_name and payer_name in group_members and re.search(
        r'\b(?:el\s+resto|lo\s+que\s+falta|todo\s+lo\s+que\s+falta|todo\s+el\s+resto)\b[^.]*\bpara\s+(?:el|el mismo|el\b|el que pago|el que pagó|él)\b',
        normalized_text,
    ):
        return payer_name

    return None


def _split_clauses(text: str) -> list[str]:
    return [
        _normalize_whitespace(fragment)
        for fragment in re.split(r'[.;:,\n]+', text)
        if _normalize_whitespace(fragment)
    ]


def _resolve_clause_subject(
    clause: str,
    group_members: list[str],
    payer_name: str,
    carry_subject: str | None,
) -> str | None:
    mentioned_members = _find_group_member_mentions(clause, group_members)
    if len(mentioned_members) == 1:
        return mentioned_members[0]

    normalized_clause = _normalize_match_text(clause)
    if payer_name and payer_name in group_members and re.search(r'\b(?:el|el mismo|el que pago|el que pagó|el que puso|él)\b', normalized_clause):
        return payer_name

    if carry_subject and re.search(
        r'^(?:y\s+)?(?:comio|comió|tomo|tomó|pidio|pidió|bebio|bebió|se pidio|se pidió|le corresponde|le toco|le tocó|tuvo|gasto|gastó)\b',
        normalized_clause,
    ):
        return carry_subject

    return None


def _item_aliases(item_name: str) -> list[str]:
    base = _normalize_match_text(item_name)
    if not base:
        return []

    aliases = {base}

    if 'coca cola light' in base or 'coca light' in base:
        aliases.update({'coca light', 'coca cola light'})
    elif 'coca cola' in base:
        aliases.update({'coca cola', 'coca'})

    if 'penne' in base:
        aliases.update({'penne', 'pene'})

    if 'tagliatela' in base:
        aliases.update({'tagliatela'})

    singular_tokens = []
    for token in base.split():
        singular_tokens.append(token[:-1] if len(token) > 4 and token.endswith('s') else token)
    aliases.add(' '.join(singular_tokens))

    return [alias for alias in aliases if alias]


def _match_item_score(clause: str, item: dict) -> float:
    normalized_clause = _normalize_match_text(clause)
    clause_tokens = set(_normalize_tokens(clause))
    best_score = 0.0

    for alias in _item_aliases(item['name']):
        alias_tokens = set(_normalize_tokens(alias))
        if not alias_tokens:
            continue

        if f' {alias} ' in f' {normalized_clause} ':
            return 1.0 + (0.05 * len(alias_tokens))

        overlap = len(alias_tokens & clause_tokens)
        if overlap <= 0:
            continue

        score = overlap / len(alias_tokens)
        if score > best_score:
            best_score = score

    return best_score


def _build_ticket_assignment_payload(
    transcript: str,
    group_members: list[str],
    payer_name: str,
    ticket_items: list[dict],
    ticket_total: float,
    ticket_tax_amount: float,
    ticket_tip_amount: float,
) -> dict:
    normalized_text = _normalize_whitespace(transcript.lower())
    normalized_group_members = _normalize_group_members(group_members)
    normalized_items = _normalize_ticket_items(ticket_items)
    excluded_participants = _extract_excluded_participants(normalized_text, normalized_group_members)
    explicit_participants = _extract_explicit_participant_names(normalized_text, normalized_group_members)

    if _mentions_all_group(normalized_text):
        active_participants = [member for member in normalized_group_members if member not in excluded_participants]
    elif explicit_participants:
        active_participants = [member for member in explicit_participants if member not in excluded_participants]
    else:
        active_participants = [member for member in normalized_group_members if member not in excluded_participants]

    if not active_participants:
        active_participants = [member for member in normalized_group_members if member not in excluded_participants]

    item_assignments = []
    assigned_item_indexes = set()
    explicit_item_totals = {member: 0.0 for member in active_participants}
    unmatched_audio_mentions = []
    carry_subject = None

    for clause in _split_clauses(normalized_text):
        subject = _resolve_clause_subject(clause, active_participants or normalized_group_members, payer_name, carry_subject)
        if subject:
            carry_subject = subject

        if not subject:
            continue

        scored_items = []
        for item in normalized_items:
            if item['index'] in assigned_item_indexes:
                continue
            score = _match_item_score(clause, item)
            if score >= 0.75:
                scored_items.append((score, item))

        if not scored_items and re.search(r'\b(?:comio|comió|tomo|tomó|pidio|pidió|bebio|bebió|se pidio|se pidió)\b', clause):
            unmatched_audio_mentions.append(clause)
            continue

        for _score, item in sorted(scored_items, key=lambda entry: entry[0], reverse=True):
            assigned_item_indexes.add(item['index'])
            explicit_item_totals[subject] = round(explicit_item_totals.get(subject, 0.0) + item['amount'], 2)
            item_assignments.append({
                'item_index': item['index'],
                'assigned_user_name': subject,
                'confidence': round(min(_score, 1.0), 2),
                'match_type': 'explicit-item',
            })

    explicit_amount_targets = _extract_member_amounts(
        normalized_text,
        active_participants or normalized_group_members,
        payer_name=payer_name,
    )
    explicit_members = {
        assignment['assigned_user_name']
        for assignment in item_assignments
    } | {
        member for member, amount in explicit_amount_targets.items() if amount > 0
    }

    share_amounts = {member: 0.0 for member in active_participants}
    for member, amount in explicit_item_totals.items():
        share_amounts[member] = round(share_amounts.get(member, 0.0) + amount, 2)

    unresolved_item_total = round(sum(
        item['amount'] for item in normalized_items if item['index'] not in assigned_item_indexes
    ), 2)

    for member, target_amount in explicit_amount_targets.items():
        if member not in share_amounts:
            share_amounts[member] = 0.0
        delta = round(max(target_amount - share_amounts[member], 0.0), 2)
        if delta <= 0:
            continue
        allocation = min(delta, unresolved_item_total)
        share_amounts[member] = round(share_amounts[member] + allocation, 2)
        unresolved_item_total = round(max(unresolved_item_total - allocation, 0.0), 2)

    remainder_target = _extract_remainder_target(normalized_text, active_participants or normalized_group_members, payer_name)
    if remainder_target and remainder_target not in share_amounts:
        share_amounts[remainder_target] = 0.0

    if unresolved_item_total > 0:
        if remainder_target:
            remainder_targets = [remainder_target]
        else:
            unnamed_targets = [
                member for member in active_participants
                if member not in explicit_members
            ]
            remainder_targets = unnamed_targets or active_participants or normalized_group_members

        split_remainder = _split_amount_evenly(unresolved_item_total, len(remainder_targets))
        for index, member in enumerate(remainder_targets):
            share_amounts[member] = round(share_amounts.get(member, 0.0) + split_remainder[index], 2)

    tax_tip_total = round(ticket_tax_amount + ticket_tip_amount, 2)
    tax_tip_targets = active_participants or normalized_group_members
    if tax_tip_total > 0 and tax_tip_targets:
        split_tax_tip = _split_amount_evenly(tax_tip_total, len(tax_tip_targets))
        for index, member in enumerate(tax_tip_targets):
            share_amounts[member] = round(share_amounts.get(member, 0.0) + split_tax_tip[index], 2)

    expected_total = round(ticket_total, 2) if ticket_total > 0 else round(sum(share_amounts.values()), 2)
    current_total = round(sum(share_amounts.values()), 2)
    difference = round(expected_total - current_total, 2)
    if tax_tip_targets and abs(difference) > 0.01:
        share_amounts[tax_tip_targets[-1]] = round(share_amounts.get(tax_tip_targets[-1], 0.0) + difference, 2)

    return {
        'item_assignments': item_assignments,
        'share_amounts_by_user_name': {
            member: round(amount, 2)
            for member, amount in share_amounts.items()
            if amount > 0
        },
        'detected_participants': active_participants,
        'excluded_participants': excluded_participants,
        'unmatched_audio_mentions': unmatched_audio_mentions,
    }


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
                'expense_date': {'type': 'string'},
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
                'expense_date',
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


def _guess_description(text: str, group_members: list[str] | None = None) -> str:
    normalized_group_members = _normalize_group_members(group_members)

    def clean_candidate(raw_candidate: str) -> str:
        candidate = _normalize_whitespace(raw_candidate)
        candidate = re.sub(r'^(?:fueron|fue|eran|era)\s+', '', candidate, flags=re.IGNORECASE)
        for member in normalized_group_members:
            candidate = re.sub(rf'(?:\s+|,)+{re.escape(member.lower())}\b', '', candidate.lower(), flags=re.IGNORECASE)
        candidate = _normalize_whitespace(candidate)
        return candidate

    specific_patterns = [
        r'fuimos a comer\s+([a-záéíóúñ ]+?)(?:,|\.| y | en total| nos sali|$)',
        r'comimos\s+([a-záéíóúñ ]+?)(?:,|\.| y | en total| nos sali|$)',
        r'lo que comimos\s+([a-záéíóúñ ]+?)(?:,|\.| y | en total| nos sali|$)',
        r'fuimos a\s+([a-záéíóúñ ]+?)(?:,|\.| y | en total| nos sali|$)',
    ]
    for pattern in specific_patterns:
        match = re.search(pattern, text)
        if match:
            candidate = clean_candidate(match.group(1))
            if candidate and not re.search(r'\d', candidate):
                return candidate.capitalize()

    match = re.search(
        r'(?:por|de|fue|era|compramos|compre|compré|cena|almuerzo|desayuno)\s+([a-záéíóúñ ]+?)(?:,|\.| total| pago| pagó| participaron|$)',
        text
    )
    if match:
        candidate = clean_candidate(match.group(1))
        if candidate and not re.search(r'\d', candidate):
            return candidate.capitalize()

    for keyword in ['cena', 'almuerzo', 'desayuno', 'supermercado', 'taxi', 'uber', 'pizza', 'asado']:
        if keyword in text:
            return keyword.capitalize()

    return 'Expense from chat'


def _safe_iso_date(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ''


def _today_local() -> date:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(_DEFAULT_TIMEZONE)).date()
        except Exception:
            pass
    return date.today()


def _extract_expense_date(text: str) -> str:
    today = _today_local()

    if re.search(r'\bhoy\b', text):
        return today.isoformat()

    if re.search(r'\bayer\b', text):
        return (today - timedelta(days=1)).isoformat()

    if re.search(r'\banteayer\b', text):
        return (today - timedelta(days=2)).isoformat()

    numeric_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', text)
    if numeric_match:
        day_value = int(numeric_match.group(1))
        month_value = int(numeric_match.group(2))
        year_value = numeric_match.group(3)
        if year_value:
            parsed_year = int(year_value)
            if parsed_year < 100:
                parsed_year += 2000
        else:
            parsed_year = today.year
        iso_value = _safe_iso_date(parsed_year, month_value, day_value)
        if iso_value:
            return iso_value

    textual_match = re.search(r'\b(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?\b', text)
    if textual_match:
        day_value = int(textual_match.group(1))
        month_name = textual_match.group(2).lower()
        month_value = _SPANISH_MONTHS.get(month_name)
        if month_value:
            year_value = int(textual_match.group(3)) if textual_match.group(3) else today.year
            iso_value = _safe_iso_date(year_value, month_value, day_value)
            if iso_value:
                return iso_value

    return ''


def _extract_total(text: str) -> float:
    spoken_amount = _parse_spoken_amount(text)
    if spoken_amount > 0:
        return spoken_amount

    patterns = [
        r'(?:total|importe|monto|salio|salió|fue)\s*(?:de\s*)?(\d[\d.,]*)',
        r'(?:gast(?:amos|e|é|aste|aron)|salimos)\s*(?:de\s*)?(\d[\d.,]*)',
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
    def clean_candidate(raw_candidate: str) -> str:
        candidate = _normalize_name(raw_candidate)
        candidate = re.sub(r'^(?:Este|Esta|El|La|Lo|Gasto|Ticket)\s+', '', candidate)
        candidate = re.sub(r'\s+(?:Y|E|Salio|Salió)$', '', candidate)
        banned = {'Este', 'Esta', 'El', 'La', 'Lo', 'Gasto', 'Ticket'}
        candidate_tokens = [token for token in candidate.split() if token not in banned]
        candidate = ' '.join(candidate_tokens[:2]).strip()
        return candidate or 'Unknown'

    yo_patterns = [
        r'\byo pag(?:ue|ué)\b',
        r'\blo pag(?:ue|ué) yo\b',
        r'\bpagu(?:e|é) yo\b',
    ]
    if any(re.search(pattern, text) for pattern in yo_patterns):
        return 'Yo'

    direct_object_match = re.search(
        r'\blo\s+pag(?:o|ó)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)?)',
        text
    )
    if direct_object_match:
        candidate = clean_candidate(direct_object_match.group(1))
        return candidate or 'Unknown'

    leading_name_match = re.search(
        r'([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)?)\s+(?:pag(?:o|ó)|pagaron|paga|abon(?:o|ó)|puso)\b',
        text
    )
    if leading_name_match:
        candidate = clean_candidate(leading_name_match.group(1))
        return candidate or 'Unknown'

    match = re.search(
        r'(?:pag(?:o|ó)|pagaron|paga|abon(?:o|ó)|puso)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)?)',
        text
    )
    if match:
        candidate = clean_candidate(match.group(1))
        return candidate or 'Unknown'

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
    group_members: list[str] | None = None,
    narrator_name: str | None = None,
) -> ExpenseDraft:
    normalized_text = transcript.lower().strip()
    normalized_group_members = _normalize_group_members(group_members)
    total_amount = _extract_total(normalized_text)
    payer_name = _resolve_payer_name(
        normalized_text,
        normalized_group_members,
        narrator_name=narrator_name,
    ) if normalized_group_members else _extract_payer_name(normalized_text)
    participants = _build_participants_from_context(
        normalized_text,
        total_amount,
        normalized_group_members,
        payer_name,
    ) if normalized_group_members else _build_participants(
        _extract_participant_names(normalized_text, payer_name),
        total_amount,
    )
    tip_amount = _extract_tip_amount(normalized_text)
    expense_date = _extract_expense_date(normalized_text)

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
        description=_guess_description(normalized_text, group_members=normalized_group_members),
        total_amount=total_amount,
        currency=_extract_currency(normalized_text),
        payer_name=payer_name,
        expense_date=expense_date,
        participants=participants,
        tip_amount=tip_amount,
        notes=(
            'parser=fallback; transcription='
            + transcription_source
            + ('; group_context=' + ', '.join(normalized_group_members) if normalized_group_members else '')
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
    expense_date = _normalize_whitespace(str(candidate.get('expense_date') or ''))
    participants = _normalize_participants(candidate.get('participants') or [], total_amount)
    tip_amount = _parse_number(candidate.get('tip_amount'))
    description = _normalize_whitespace(str(candidate.get('description') or '')) or _guess_description(transcript.lower(), group_members=None)
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
        expense_date=expense_date or _extract_expense_date(transcript.lower()),
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
    group_members: list[str] | None = None,
    narrator_name: str | None = None,
) -> ExpenseDraft | None:
    if not _has_assemblyai():
        return None

    normalized_group_members = _normalize_group_members(group_members)
    group_context_line = (
        'Miembros reales del grupo: ' + ', '.join(normalized_group_members) + '. '
        if normalized_group_members else
        ''
    )
    narrator_context_line = (
        'Si la transcripción usa "yo", interpretalo como ' + narrator_name + '. '
        if narrator_name else
        ''
    )

    prompt = (
        'Extrae un borrador de gasto estructurado a partir de una transcripcion en español. '
        'No inventes datos. Si algo no está claro, usa "Unknown", lista vacía o 0 según corresponda. '
        'Asumí ARS salvo que la transcripción indique claramente USD. '
        'needs_review debe ser true. '
        'Si hay monto total y participantes detectados pero no amounts individuales, repartí en partes iguales. '
        'Si el usuario dice "dividimos en partes iguales", incluí a todos los miembros reales del grupo y repartí el total entre todos. '
        'Si menciona un monto puntual para una persona y luego dice que el resto va en partes iguales, asigná ese monto puntual y repartí lo que sobra entre el resto de los miembros. '
        'Salvo que la transcripción excluya a alguien de forma explícita, asumí que participa todo el grupo. '
        + group_context_line
        + narrator_context_line
        + 'confidence debe ser un número entre 0 y 1.'
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
    group_members: list[str] | None = None,
    narrator_name: str | None = None,
) -> ExpenseDraft:
    normalized_transcript = _normalize_whitespace(transcript)
    structured_draft = _assemblyai_structured_parse_transcript(
        normalized_transcript,
        transcription_used_ai=transcription_used_ai,
        transcription_source=transcription_source,
        group_members=group_members,
        narrator_name=narrator_name,
    )
    if structured_draft is not None:
        return structured_draft

    return _fallback_parse_transcript(
        normalized_transcript,
        transcription_used_ai=transcription_used_ai,
        transcription_source=transcription_source,
        group_members=group_members,
        narrator_name=narrator_name,
    )


def parse_transcript_with_ticket_context(
    transcript: str,
    transcription_used_ai: bool = False,
    transcription_source: str = 'manual',
    group_members: list[str] | None = None,
    narrator_name: str | None = None,
    ticket_items: list[dict] | None = None,
    ticket_total: float = 0.0,
    ticket_tax_amount: float = 0.0,
    ticket_tip_amount: float = 0.0,
    ticket_merchant_name: str = '',
    ticket_expense_date: str = '',
) -> dict:
    draft = parse_transcript(
        transcript,
        transcription_used_ai=transcription_used_ai,
        transcription_source=transcription_source,
        group_members=group_members,
        narrator_name=narrator_name,
    )

    normalized_group_members = _normalize_group_members(group_members)
    normalized_items = _normalize_ticket_items(ticket_items)
    if not normalized_items or not normalized_group_members:
        return {'draft': draft.model_dump()}

    assignment = _build_ticket_assignment_payload(
        transcript,
        normalized_group_members,
        draft.payer_name,
        normalized_items,
        ticket_total=_parse_number(ticket_total),
        ticket_tax_amount=_parse_number(ticket_tax_amount),
        ticket_tip_amount=_parse_number(ticket_tip_amount),
    )

    share_amounts = assignment.get('share_amounts_by_user_name') or {}
    if share_amounts:
        draft.participants = [
            ExpenseParticipantDraft(name=name, amount=round(amount, 2))
            for name, amount in share_amounts.items()
        ]
        if _parse_number(ticket_total) > 0:
            draft.total_amount = _parse_number(ticket_total)

    if ticket_merchant_name:
        draft.description = _normalize_whitespace(ticket_merchant_name)

    if ticket_expense_date and not draft.expense_date:
        draft.expense_date = _normalize_whitespace(ticket_expense_date)

    draft.currency = 'ARS'

    return {
        'draft': draft.model_dump(),
        'ticket_assignment': assignment,
    }


def parse_audio_to_draft(audio_file_path: str) -> ExpenseDraft:
    transcript, source = transcribe_audio_with_source(audio_file_path)
    return parse_transcript(
        transcript,
        transcription_used_ai=_has_openai(),
        transcription_source=source,
    )
