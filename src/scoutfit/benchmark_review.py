"""Frozen human-review campaigns and privacy-safe, explicitly scoped evidence."""

import hashlib
import json

import pandas as pd

from scoutfit.evaluation import METHODS, benchmark_template, evaluate_judgments
from scoutfit.updates import atomic_json


def campaign(root, profiles, metadata, features, queries=20):
    snapshot = metadata["snapshot"]
    # Snapshot identifiers are filenames supplied by data providers, never paths.
    identity = hashlib.sha256(snapshot.encode()).hexdigest()[:20]
    folder = root / "data/evaluation/campaigns" / identity
    manifest = folder / "campaign.json"
    if manifest.exists():
        config = json.loads(manifest.read_text(encoding="utf-8"))
        content = (folder / "pairs.csv").read_bytes()
        if (
            config["snapshot"] != snapshot
            or config["features"] != features
            or hashlib.sha256(content).hexdigest() != config["pairs_sha256"]
        ):
            raise ValueError("La campaña no coincide con su consulta o ha sido modificada.")
        from io import BytesIO

        pairs = pd.read_csv(BytesIO(content), keep_default_na=False)
    else:
        pairs = benchmark_template(profiles, features, snapshot, queries, min_minutes=450)
        if pairs.empty:
            raise ValueError("No hay suficientes candidatos para preparar la revisión.")
        content = pairs.to_csv(index=False).encode("utf-8")
        config = {
            "snapshot": snapshot,
            "consulted_at": metadata["downloaded_at"],
            "features": features,
            "min_minutes": 450,
            "top_k": 5,
            "seed": 7,
            "references": int(pairs.reference_id.nunique()),
            "pairs": len(pairs),
            "pairs_sha256": hashlib.sha256(content).hexdigest(),
            "protocol": "balanced_weights_position_cohort_other_teams_judged_pool_only_v1",
        }
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "pairs.csv").write_bytes(content)
        atomic_json(manifest, config)
    return pairs, config


def campaign_judgments(pairs, judgments, snapshot):
    allowed = set(zip(pairs.reference_id, pairs.candidate_id))
    return [
        row
        for row in judgments
        if row.get("snapshot") == snapshot
        and (row.get("reference_id"), row.get("candidate_id")) in allowed
    ]


def judgment_digest(scoped):
    values = sorted((r["reference_id"], r["candidate_id"], r["relevance"]) for r in scoped)
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()


def campaign_report(profiles, features, pairs, config, judgments):
    scoped = campaign_judgments(pairs, judgments, config["snapshot"])
    scores, skipped = evaluate_judgments(
        profiles, features, scoped, config["snapshot"], config["top_k"], config["min_minutes"]
    )
    total = len(pairs)
    done = len(scoped)
    complete = done == total and len(scores) == config["references"] * len(METHODS)
    summary = []
    if not scores.empty:
        for method, group in scores.groupby("method"):
            summary.append(
                {
                    "method": method,
                    "references": int(group.reference_id.nunique()),
                    "ndcg": float(group.ndcg.mean()),
                    "precision": float(group.precision.mean()),
                    "recall": float(group.recall.mean()),
                    "top_k_coverage": float(group.judged_top_k_coverage.mean()),
                }
            )
    return {
        "snapshot": config["snapshot"],
        "status": "evaluated" if complete else "partial_review" if summary else "pending_review",
        "scope": "judged_pool_only",
        "protocol": config["protocol"],
        "min_minutes": config["min_minutes"],
        "top_k": config["top_k"],
        "pairs_sha256": config["pairs_sha256"],
        "references_planned": config["references"],
        "pairs_planned": total,
        "pairs_reviewed": done,
        "review_digest": judgment_digest(scoped),
        "review_fraction": done / total if total else 0,
        "summary": summary,
        "results": scores.to_dict("records"),
        "skipped": skipped,
        "limitations": [
            "Revisión humana de una muestra seleccionada, no de todos los posibles jugadores.",
            "Se reordena solo el conjunto revisado; los candidatos sin valorar no son negativos.",
            "No mide calidad global, encaje táctico validado ni éxito de fichajes.",
            "Las notas e identidades de revisores no se incluyen en este informe.",
        ],
    }
