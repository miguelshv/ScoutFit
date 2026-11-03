"""Append-only field observations and explicitly human individual assessments."""

from datetime import date, datetime
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from scoutfit.projects import now, text_field, update_project

VERDICTS = ("Sin conclusión", "Seguir mirando", "Encaja parcialmente", "Descartar")


def local_today():
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def video_url(value):
    value = text_field(value, 2000, "Enlace al vídeo")
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        port = parsed.port
        valid = (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
            and "\\" not in value
            and port != 0
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Usa un enlace http/https válido, sin credenciales ni espacios.")
    return value


def video_seconds(value):
    value = text_field(value, 12, "Posición del vídeo")
    if not value:
        return None
    parts = value.split(":")
    if len(parts) not in (2, 3) or not all(p.isascii() and p.isdigit() for p in parts):
        raise ValueError("La posición del vídeo debe tener formato mm:ss o hh:mm:ss.")
    numbers = [int(p) for p in parts]
    if numbers[-1] > 59 or (len(parts) == 3 and numbers[1] > 59):
        raise ValueError("Los segundos y los minutos de hh:mm:ss deben estar entre 00 y 59.")
    seconds = sum(number * 60**index for index, number in enumerate(reversed(numbers)))
    if seconds > 359999:
        raise ValueError("La posición del vídeo no puede superar 99:59:59.")
    return seconds


def video_position(seconds):
    if seconds is None:
        return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


def candidate_record(project, identity):
    candidate = next((c for c in project["candidates"] if c["key"] == identity), None)
    if candidate is None:
        raise ValueError("El candidato ya no está en el proyecto.")
    return candidate


def append_observation(path, project_id, identity, values, statistics_snapshot=""):
    raw_date = values.get("observed_on", "")
    try:
        observed_on = date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        raise ValueError("Indica una fecha de observación válida.") from None
    if not date(1900, 1, 1) <= observed_on <= local_today():
        raise ValueError("La fecha de observación no puede estar en el futuro ni antes de 1900.")
    fields = {
        "context": text_field(values.get("context", ""), 200, "Partido o contexto", True),
        "strengths": text_field(values.get("strengths", ""), 4000, "Fortalezas"),
        "doubts": text_field(values.get("doubts", ""), 4000, "Dudas"),
        "next_step": text_field(values.get("next_step", ""), 2000, "Próxima observación"),
        "video_url": video_url(values.get("video_url", "")),
        "video_seconds": video_seconds(values.get("video_position", "")),
    }
    if not any(fields[k] for k in ("strengths", "doubts", "next_step")):
        raise ValueError("Anota al menos una fortaleza, una duda o una próxima observación.")
    if fields["video_seconds"] is not None and not fields["video_url"]:
        raise ValueError("Añade el enlace al vídeo para guardar su posición.")
    record = {
        "id": uuid4().hex,
        "observed_on": observed_on.isoformat(),
        **fields,
        "created_at": now(),
        "statistics_snapshot": text_field(statistics_snapshot, 200, "Consulta estadística"),
    }

    def change(project):
        candidate = candidate_record(project, identity)
        candidate.setdefault("observations", []).append(record)
        candidate["updated_at"] = record["created_at"]

    update_project(path, project_id, change)
    return record["id"]


def save_assessment(path, project_id, identity, verdict, rationale, author=""):
    if verdict not in VERDICTS:
        raise ValueError("Elige una conclusión del informe válida.")
    rationale = text_field(rationale, 6000, "Motivos de la conclusión", verdict != "Sin conclusión")
    author = text_field(author, 100, "Firma")
    assessment = {"verdict": verdict, "rationale": rationale, "author": author, "updated_at": now()}

    def change(project):
        candidate = candidate_record(project, identity)
        candidate["assessment"] = assessment
        candidate["updated_at"] = assessment["updated_at"]

    update_project(path, project_id, change)


def observation_history(candidate):
    return sorted(
        candidate.get("observations", []),
        key=lambda r: (r["observed_on"], r["created_at"], r["id"]),
        reverse=True,
    )
