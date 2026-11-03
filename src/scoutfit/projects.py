"""Persistent local scouting projects and allowlisted search restoration."""

import json
import math
from datetime import UTC, datetime
from uuid import uuid4

from scoutfit.candidate_filters import CandidateFilters
from scoutfit.target_search import available_presets
from scoutfit.workspace import load_records, player_key, write_records

STATUSES = ("Pendiente de revisar", "Interesante", "Descartado")


def now():
    return datetime.now(UTC).isoformat()


def text_field(value, maximum, label, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{label}: usa {'1–' if required else '0–'}{maximum} caracteres")
    return value.strip()


def project_by_id(path, project_id):
    return next((p for p in load_records(path) if p.get("id") == project_id), None)


def update_project(path, project_id, change):
    rows = load_records(path)
    project = next((p for p in rows if p.get("id") == project_id), None)
    if project is None:
        raise ValueError("El proyecto ya no está disponible")
    change(project)
    project["updated_at"] = now()
    write_records(path, rows)


def create_project(path, name, description=""):
    name = text_field(name, 100, "Nombre", True)
    description = text_field(description, 4000, "Descripción")
    rows = load_records(path)
    if any(p["name"].casefold() == name.casefold() for p in rows):
        raise ValueError("Ya existe un proyecto con ese nombre")
    project = {
        "id": uuid4().hex,
        "name": name,
        "description": description,
        "created_at": now(),
        "updated_at": now(),
        "searches": [],
        "candidates": [],
    }
    write_records(path, [*rows, project])
    return project["id"]


def scope_for(profiles, metadata):
    return {
        "provider": metadata.get("provider", "statsbomb"),
        "competition_id": int(profiles.iloc[0]["competition_id"]),
        "season_id": int(profiles.iloc[0]["season_id"]),
    }


def save_search(path, project_id, name, config, profiles, metadata):
    name = text_field(name, 100, "Nombre de búsqueda", True)
    config = json.loads(json.dumps(config, allow_nan=False))
    prepare_search_state(config, profiles, metadata)  # Validate before touching the file.

    def change(project):
        old = next(
            (s for s in project["searches"] if s["name"].casefold() == name.casefold()), None
        )
        record = {
            "id": old["id"] if old else uuid4().hex,
            "name": name,
            "config": config,
            "scope": scope_for(profiles, metadata),
            "snapshot": metadata.get("snapshot", metadata.get("revision", "historical")),
            "saved_at": now(),
        }
        project["searches"] = [s for s in project["searches"] if s["id"] != record["id"]] + [record]

    update_project(path, project_id, change)


def add_candidate(path, project_id, player, metadata):
    identity = player_key(player, metadata)

    def change(project):
        if any(c["key"] == identity for c in project["candidates"]):
            return
        project["candidates"].append(
            {
                "key": identity,
                "player_id": int(player["player_id"]),
                "profile_id": str(player["profile_id"]),
                "player_name": str(player["player_name"]),
                "team_at_save": str(player["team_name"]),
                "role": str(player["role"]),
                "provider": metadata.get("provider", "statsbomb"),
                "competition_id": int(player["competition_id"]),
                "season_id": int(player["season_id"]),
                "snapshot": metadata.get("snapshot", "historical"),
                "status": STATUSES[0],
                "note": "",
                "saved_at": now(),
                "updated_at": now(),
            }
        )

    update_project(path, project_id, change)


def update_candidate(path, project_id, identity, status, note):
    if status not in STATUSES:
        raise ValueError("Estado de seguimiento no válido")
    note = text_field(note, 4000, "Nota")

    def change(project):
        candidate = next((c for c in project["candidates"] if c["key"] == identity), None)
        if candidate is None:
            raise ValueError("El candidato ya no está en el proyecto")
        candidate.update(status=status, note=note, updated_at=now())

    update_project(path, project_id, change)


def number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} no válido")
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f"{label} fuera de rango")
    return int(value) if integer else float(value)


def prepare_search_state(config, profiles, metadata, scope=None):
    """Produce a validated patch; callers apply it before creating any search widgets."""
    if scope is not None and scope != scope_for(profiles, metadata):
        raise ValueError("La búsqueda pertenece a otra liga, temporada o fuente")
    features = metadata.get("features")
    if features is None:
        from scoutfit.datasets import metric_definitions

        features = metric_definitions(metadata)
    raw = config.get("candidate_filters", {})
    filters = CandidateFilters(**raw)
    known_teams = set(int(t) for t in profiles["team_id"])
    if (set(filters.include_teams) | set(filters.exclude_teams)) - known_teams:
        raise ValueError("Un club de los filtros ya no está en la consulta; revisa la búsqueda")
    minimum = number(config["minimum_minutes"], 0, 5000, "Mínimo de muestra", True)
    patch = {
        "candidate_teams_include": list(filters.include_teams),
        "candidate_teams_exclude": list(filters.exclude_teams),
        "candidate_min_minutes": number(filters.min_minutes, 0, 5000, "Minutos", True),
        "candidate_max_minutes": number(filters.max_minutes, 0, 5000, "Minutos", True),
    }
    if config.get("mode", "similarity") == "target":
        position, goals, weights = config["position"], config["goals"], config["weights"]
        if position not in set(profiles["role"]) or not goals or set(goals) - set(features):
            raise ValueError("La posición o las métricas del objetivo no están disponibles")
        if set(weights) != set(goals) or not isinstance(config["strict"], bool):
            raise ValueError("Configuración de objetivos no válida")
        presets = available_presets(position, features)
        preset = config.get("preset", "Personalizado")
        if preset not in presets:
            preset = "Personalizado"
        token = f"{position}_{preset}"
        patch.update(
            search_mode="Por objetivo",
            target_position=position,
            target_preset=preset,
            target_min_minutes=minimum,
            target_top_k=number(config["top_k"], 1, 20, "Resultados", True),
            target_strict=config["strict"],
            target_workspace_tab="Resultados del objetivo",
        )
        patch[f"target_features_{token}"] = list(goals)
        for feature in goals:
            patch[f"target_goal_{token}_{feature}"] = number(
                goals[feature], 0, 100, "Percentil", True
            )
            patch[f"target_weight_{token}_{feature}"] = number(
                weights[feature], 1, 5, "Importancia", True
            )
    elif config.get("mode", "similarity") == "similarity":
        candidates = profiles.loc[profiles["profile_id"] == config["reference_id"]]
        if "reference_player_id" in config:
            candidates = profiles.loc[profiles["player_id"] == config["reference_player_id"]]
        if len(candidates) != 1 or candidates.iloc[0]["minutes"] < minimum:
            raise ValueError("La referencia ya no está disponible con ese mínimo de muestra")
        weights = config["weights"]
        if set(weights) != set(features):
            raise ValueError("Las métricas de la búsqueda ya no coinciden con la fuente")
        validated = {f"weight_{f}": number(w, 0, 5, "Peso") for f, w in weights.items()}
        if sum(validated.values()) <= 0:
            raise ValueError("Al menos un peso debe ser positivo")
        if not isinstance(config["exclude_team"], bool) or not isinstance(
            config["match_inferred_role"], bool
        ):
            raise ValueError("Opciones de búsqueda no válidas")
        priorities = (
            ("Equilibrada", "Creación", "Defensa")
            if metadata.get("provider") == "espn"
            else ("Equilibrada", "Progresión", "Defensa")
        )
        priority = config.get("priority", "Equilibrada")
        if priority not in priorities:
            raise ValueError("Prioridad de búsqueda no válida")
        if config["match_inferred_role"] and not candidates.iloc[0].get("inferred_role", ""):
            raise ValueError("La referencia ya no tiene un perfil inferido; revisa ese requisito")
        patch.update(validated)
        patch.update(
            search_mode="Por parecido",
            player_search="",
            reference_team="Todos",
            reference_position="Todas",
            reference_player=candidates.iloc[0]["profile_id"],
            min_minutes=minimum,
            top_k=number(config["top_k"], 1, 10, "Resultados", True),
            exclude_team=config["exclude_team"],
            same_profile=config["match_inferred_role"],
            custom_weights=True,
            priority=priority,
            workspace_tab="Recomendaciones",
        )
    else:
        raise ValueError("Modo de búsqueda desconocido")
    return patch
