"""验证外部 baseline 文件适配器。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys

import pytest

from experiments.baseline_file_adapter import (
    attach_baseline_observations,
    build_baseline_observation_import_manifest,
    load_baseline_observation_rows,
)
from main.protocol.experiment import EventProtocolRecord
from main.protocol.runtime import run_protocol_events


def _event() -> EventProtocolRecord:
    """构造一个不内置 baseline 的协议事件。"""
    return EventProtocolRecord(
        event_id="event_external_baseline",
        method_name="ceg",
        split="test",
        sample_role="positive_source",
        attack_family="rotate",
        attack_condition="rotate_light",
        is_watermarked=True,
        payload={
            "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
            "content": {"content_score_raw": 0.51},
            "geometry": {},
            "attestation": {"attestation_score": 0.8},
        },
    )


@pytest.mark.quick
def test_load_baseline_observation_rows_from_csv(tmp_path) -> None:
    """CSV baseline 输出应被读取为统一 observation rows。"""
    path = tmp_path / "baseline_rows.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "baseline_id", "score", "threshold"])
        writer.writeheader()
        writer.writerow(
            {
                "event_id": "event_external_baseline",
                "baseline_id": "tree_ring",
                "score": "0.7",
                "threshold": "0.5",
            }
        )

    rows = load_baseline_observation_rows(path)

    assert rows[0]["baseline_id"] == "tree_ring"


@pytest.mark.quick
def test_attach_baseline_observations_enters_protocol_records() -> None:
    """外部 baseline 文件适配后应进入统一 protocol records。"""
    rows = [
        {"event_id": "event_external_baseline", "baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5},
        {"event_id": "event_external_baseline", "baseline_id": "stable_signaturedee", "score": 0.8, "threshold": 0.5},
    ]
    events = attach_baseline_observations([_event()], rows)
    records = run_protocol_events(events)

    assert {record["method_name"] for record in records} == {"ceg", "tree_ring", "stable_signature_dee"}


@pytest.mark.quick
def test_baseline_observation_import_manifest_requires_formal_evidence(tmp_path) -> None:
    """正式离线 baseline 导入必须显式绑定外部运行证据."""
    rows = [{"event_id": "event_external_baseline", "baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5}]

    with pytest.raises(ValueError, match="formal baseline import requires"):
        build_baseline_observation_import_manifest(
            rows,
            source_observation_path=tmp_path / "source.json",
            output_observation_path=tmp_path / "baseline_observations.json",
            formal_result_claim=True,
        )


@pytest.mark.quick
def test_import_baseline_observations_cli_writes_package_ready_manifest(tmp_path) -> None:
    """离线 baseline observation 导入应写出 build_paper_outputs 可直接消费的文件."""
    source_path = tmp_path / "offline_tree_ring.json"
    output_root = tmp_path / "baseline_results"
    source_path.write_text(
        json.dumps(
            [{"event_id": "event_external_baseline", "baseline_id": "tree_ring", "score": 0.7, "threshold": 0.5}]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/import_baseline_observations.py",
            "--observations",
            str(source_path),
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )

    rows = json.loads((output_root / "baseline_observations.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_root / "baseline_execution_manifest.json").read_text(encoding="utf-8"))
    assert rows[0]["baseline_id"] == "tree_ring"
    assert manifest["producer_role"] == "offline_external_baseline_observation_import"
    assert manifest["formal_result_claim"] is False
    assert manifest["baseline_ids"] == ["tree_ring"]
