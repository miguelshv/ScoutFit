import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from scoutfit.benchmark_review import campaign, campaign_report
from scoutfit.datasets import ESPN_FEATURES, activate
from scoutfit.demo_export import export_demo


@pytest.fixture
def sample():
    players = pd.DataFrame(
        [
            {
                "profile_id": f"espn:{i}:{i}",
                "player_id": i,
                "player_name": f"Player {i}",
                "team_id": i,
                "team_name": f"Club {i}",
                "role": "Mediocentro",
                "provider": "espn",
                "competition_id": 740,
                "season_id": 2026,
                "gender": "male",
                "minutes": 950,
                "matches": 11,
                **{f: (i + j) / 3 for j, f in enumerate(ESPN_FEATURES)},
            }
            for i in range(1, 9)
        ]
    )
    metadata = {
        "snapshot": "snapshot-a",
        "provider": "espn",
        "gender": "male",
        "downloaded_at": "2026-11-03T12:00:00Z",
        "season": "2026/27",
        "team_count": 8,
    }
    return players, metadata


def test_campaign_is_frozen_and_detects_modifications(tmp_path, sample):
    players, metadata = sample
    pairs, config = campaign(tmp_path, players, metadata, ESPN_FEATURES, queries=2)
    again, same = campaign(tmp_path, players.iloc[::-1], metadata, ESPN_FEATURES, queries=7)
    assert config == same
    assert pairs.reference_id.tolist() == again.reference_id.tolist()
    assert config["references"] == 2
    assert all(str(value) in ("", "None") for value in pairs.relevance)
    path = next((tmp_path / "data/evaluation/campaigns").glob("*/pairs.csv"))
    path.write_text("modified")
    with pytest.raises(ValueError, match="modificada"):
        campaign(tmp_path, players, metadata, ESPN_FEATURES)


def test_evidence_requires_humans_and_excludes_private_notes(tmp_path, sample):
    players, metadata = sample
    pairs, config = campaign(tmp_path, players, metadata, ESPN_FEATURES, queries=2)
    report = campaign_report(players, ESPN_FEATURES, pairs, config, [])
    assert report["status"] == "pending_review"
    assert report["summary"] == [] and report["pairs_reviewed"] == 0
    judgments = [
        {
            "snapshot": metadata["snapshot"],
            "reference_id": row.reference_id,
            "candidate_id": row.candidate_id,
            "relevance": i % 3,
            "note": "PRIVATE_SECRET",
            "reviewer": "PRIVATE_REVIEWER",
        }
        for i, row in enumerate(pairs.itertuples())
    ]
    stale = [{**judgments[0], "snapshot": "other"}, {**judgments[0], "reference_id": "unknown"}]
    partial = campaign_report(players, ESPN_FEATURES, pairs, config, judgments[:3] + stale)
    assert partial["status"] == "partial_review"
    assert partial["pairs_reviewed"] == 3
    complete = campaign_report(players, ESPN_FEATURES, pairs, config, judgments + stale)
    assert complete["status"] == "evaluated"
    assert complete["review_fraction"] == 1
    content = json.dumps(complete, allow_nan=False)
    assert "PRIVATE" not in content
    revised = [{**r, "relevance": (r["relevance"] + 1) % 3} for r in judgments]
    changed = campaign_report(players, ESPN_FEATURES, pairs, config, revised)
    assert changed["pairs_reviewed"] == complete["pairs_reviewed"]
    assert changed["review_digest"] != complete["review_digest"]


def test_demo_export_is_an_allowlist_and_does_not_publish_local_work(tmp_path, sample):
    players, metadata = sample
    root, output = tmp_path / "app", tmp_path / "public"
    source = root / "data/processed/espn/snapshot-a"
    source.mkdir(parents=True)
    players.assign(private_note="PRIVATE_SECRET").to_csv(source / "profiles.csv", index=False)
    (source / "metadata.json").write_text(json.dumps(metadata))
    activate(root / "data/processed", source)
    for folder in ("data/user", "data/raw", ".streamlit"):
        path = root / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / "secret.txt").write_text("PRIVATE_SECRET")
    shutil.copytree(Path(__file__).resolve().parents[1] / "demo/site", root / "demo/site")
    result = export_demo(root, output)
    assert result["profiles"] == 8 and result["parity_cases"] == 72
    names = {p.name for p in (output / "dist").iterdir()}
    assert names == {
        "index.html",
        "app.js",
        "engine.mjs",
        "style.css",
        "data.json",
        "evidence.json",
    }
    payload = (output / "dist/data.json").read_text(encoding="utf-8")
    assert "PRIVATE_SECRET" not in payload and "private_note" not in payload
    assert json.loads(payload)["evaluation"]["status"] == "pending_review"
    (output / "dist/unrelated.txt").write_text("Keep this")
    with pytest.raises(ValueError, match="ajenos"):
        export_demo(root, output)
    assert (output / "dist/unrelated.txt").read_text() == "Keep this"
