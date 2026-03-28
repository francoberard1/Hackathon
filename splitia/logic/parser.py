import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}


def _parse_number(s: str) -> float:
    s = s.replace("$", "").replace("€", "").strip()
    s = s.replace(",", ".")
    return float(s)


def transcribe_audio(audio_file_path: str) -> str:
    path = Path(audio_file_path)

    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {audio_file_path}")

    if path.suffix.lower() not in _AUDIO_EXTS:
        raise ValueError(f"Formato de audio no soportado: {path.suffix}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "esto fue una compra de 10, juan gastó 8 y sofi 2"

    client = OpenAI(api_key=api_key)

    try:
        with open(path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=f
            )
    except Exception as e:
        raise RuntimeError(f"Error al transcribir audio: {e}")

    text = resp.get("text") if isinstance(resp, dict) else getattr(resp, "text", None)

    if not text:
        raise RuntimeError("No se obtuvo texto")

    return text


def _extract_total(text: str):
    m = re.search(r"(?:compra|total|importe|valor).*?(\d+[.,]?\d*)", text)
    if m:
        return _parse_number(m.group(1))

    m = re.search(r"\b(\d+[.,]?\d*)\b", text)
    if m:
        return _parse_number(m.group(1))

    return None


def _extract_allocations(text: str):
    allocations = {}

    pattern = re.findall(
        r"([a-zA-Záéíóúñ]+)\s*(?:gasto|gastó|pago|pagó)?\s*(\d+[.,]?\d*)",
        text,
    )

    for name, amount in pattern:
        allocations[name.title()] = _parse_number(amount)

    return allocations


def _extract_only_participants(text: str):
    m = re.search(r"solo(?: entre)? (.+)", text)
    if not m:
        return []

    names = re.split(r",| y ", m.group(1))
    return [n.strip().title() for n in names if n.strip()]


def _extract_excludes(text: str):
    excludes = re.findall(r"(?:sin|menos|excepto) ([a-zA-Záéíóúñ]+)", text)
    return [e.title() for e in excludes]


def parse_transcript(transcript: str) -> dict:
    text = transcript.lower().strip()

    allocations = _extract_allocations(text)
    total = _extract_total(text)
    only = _extract_only_participants(text)
    excludes = _extract_excludes(text)

    result = {
        "transcript": transcript,
        "total_amount": None,
        "split_type": "unknown",
        "participants": [],
        "allocations": {},
        "excluded_members": excludes,
    }

    # 🔹 Caso 1: custom
    if allocations:
        total_calc = sum(allocations.values())

        if total is None:
            total = total_calc

        if abs(total - total_calc) > 0.01:
            raise ValueError("Las cuentas no cierran")

        result.update({
            "total_amount": total,
            "split_type": "custom",
            "participants": list(allocations.keys()),
            "allocations": allocations
        })
        return result

    # 🔹 Caso 2: solo
    if only and total:
        share = total / len(only)
        result.update({
            "total_amount": total,
            "split_type": "equal",
            "participants": only,
            "allocations": {p: round(share, 2) for p in only}
        })
        return result

    # 🔹 Caso 3: fallback
    if total:
        participants = ["A", "B"]
        share = total / 2

        result.update({
            "total_amount": total,
            "split_type": "equal",
            "participants": participants,
            "allocations": {p: round(share, 2) for p in participants}
        })
        return result

    return result
