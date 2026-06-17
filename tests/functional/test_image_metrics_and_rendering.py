"""验证图像质量指标计算和论文图表渲染出口。"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from main.analysis.figure_specs import build_paper_figure_specs
from main.analysis.image_metrics import build_quality_metric_rows, compute_pair_quality_metrics
from main.analysis.render_figures import render_paper_figure_package, render_figure_svg


def _write_ppm(path, pixels: list[tuple[int, int, int]]) -> None:
    """写入极小 PPM 图像, 避免测试依赖 Pillow。"""
    body = "\n".join(f"{r} {g} {b}" for r, g, b in pixels)
    path.write_text(f"P3\n2 2\n255\n{body}\n", encoding="ascii")


@pytest.mark.quick
def test_compute_pair_quality_metrics_from_pnm(tmp_path) -> None:
    """图像质量模块应能从真实图像文件计算 PSNR 和 SSIM。"""
    reference = tmp_path / "reference.ppm"
    watermarked = tmp_path / "watermarked.ppm"
    _write_ppm(reference, [(10, 10, 10), (20, 20, 20), (30, 30, 30), (40, 40, 40)])
    _write_ppm(watermarked, [(10, 10, 10), (22, 22, 22), (30, 30, 30), (44, 44, 44)])

    metrics = compute_pair_quality_metrics(reference, watermarked, image_id="sample_1")

    assert metrics.image_id == "sample_1"
    assert metrics.width == 2
    assert metrics.height == 2
    assert metrics.mse > 0
    assert metrics.mae > 0
    assert metrics.psnr is not None
    assert 0 <= metrics.ssim <= 1


@pytest.mark.quick
def test_build_quality_metric_rows_preserves_protocol_fields(tmp_path) -> None:
    """批量质量指标计算应保留 event_id、method_name 和攻击族字段。"""
    reference = tmp_path / "reference.ppm"
    watermarked = tmp_path / "watermarked.ppm"
    _write_ppm(reference, [(0, 0, 0), (10, 10, 10), (20, 20, 20), (30, 30, 30)])
    _write_ppm(watermarked, [(1, 1, 1), (11, 11, 11), (21, 21, 21), (31, 31, 31)])

    rows = build_quality_metric_rows(
        [
            {
                "event_id": "event_quality",
                "method_name": "ceg",
                "attack_family": "gaussian_noise",
                "reference_path": str(reference),
                "watermarked_path": str(watermarked),
            }
        ]
    )

    assert rows[0]["event_id"] == "event_quality"
    assert rows[0]["method_name"] == "ceg"
    assert rows[0]["attack_family"] == "gaussian_noise"
    assert rows[0]["psnr"] is not None

    fallback_rows = build_quality_metric_rows(
        [
            {
                "event_id": "event_quality_fallback",
                "method_name": "ceg",
                "clean_image_path": str(reference),
                "watermarked_image_path": str(watermarked),
            }
        ]
    )
    assert fallback_rows[0]["event_id"] == "event_quality_fallback"
    assert fallback_rows[0]["psnr"] is not None


@pytest.mark.quick
def test_render_paper_figure_package_writes_svg_and_html(tmp_path) -> None:
    """图表渲染器应把 figure specs 写成 SVG 和 HTML 报告。"""
    specs = build_paper_figure_specs(
        [
            {
                "method_name": "ceg",
                "sample_role": "positive_source",
                "attack_family": "rotation",
                "is_watermarked": True,
                "final_decision": True,
                "content_score_raw": 0.9,
                "bit_accuracy": 0.95,
                "psnr": 40.0,
            },
            {
                "method_name": "tree_ring",
                "sample_role": "clean_negative",
                "attack_family": "clean",
                "is_watermarked": False,
                "final_decision": False,
                "baseline_score": 0.2,
                "bit_accuracy": 0.5,
                "psnr": 38.0,
            },
        ]
    )

    manifest = render_paper_figure_package(specs, tmp_path)

    assert manifest["figure_count"] == 8
    assert (tmp_path / "paper_figures_report.html").exists()
    assert (tmp_path / "figures" / "main_detection_comparison.svg").exists()
    assert "<svg" in (tmp_path / "figures" / "main_detection_comparison.svg").read_text(encoding="utf-8")


@pytest.mark.quick
def test_render_figure_svg_handles_empty_data() -> None:
    """缺失可绘制数值时也应生成包含提示的 SVG, 而不是中断产物链路。"""
    svg = render_figure_svg({"figure_id": "empty", "title": "空图", "chart_type": "bar", "data": []})

    assert "<svg" in svg
    assert "没有可绘制" in svg


@pytest.mark.quick
def test_quality_metric_cli_and_render_cli(tmp_path) -> None:
    """脚本入口应能从临时输入生成质量指标和渲染图表。"""
    reference = tmp_path / "reference.ppm"
    watermarked = tmp_path / "watermarked.ppm"
    _write_ppm(reference, [(0, 0, 0), (10, 10, 10), (20, 20, 20), (30, 30, 30)])
    _write_ppm(watermarked, [(1, 1, 1), (11, 11, 11), (21, 21, 21), (31, 31, 31)])
    pairs_path = tmp_path / "pairs.json"
    metrics_path = tmp_path / "quality_metrics.json"
    pairs_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "event_cli",
                    "reference_path": str(reference),
                    "watermarked_path": str(watermarked),
                }
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/compute_image_quality_metrics.py",
            "--pairs",
            str(pairs_path),
            "--out",
            str(metrics_path),
            "--formal-result-claim",
        ],
        cwd=".",
        check=True,
    )
    assert json.loads(metrics_path.read_text(encoding="utf-8"))[0]["event_id"] == "event_cli"
    metric_manifest = json.loads((tmp_path / "metric_execution_manifest.json").read_text(encoding="utf-8"))
    assert metric_manifest["artifact_name"] == "metric_execution_manifest.json"
    assert metric_manifest["producer_id"] == "ceg_basic_image_quality_metric_runner"
    assert metric_manifest["formal_result_claim"] is True
    assert metric_manifest["metric_readiness"]["overall_decision"] == "pass"
    assert metric_manifest["metric_names"] == ["mse", "mae", "psnr", "ssim"]

    specs_path = tmp_path / "paper_figure_specs.json"
    specs_path.write_text(
        json.dumps(
            {
                "figures": [
                    {
                        "figure_id": "simple_bar",
                        "title": "简单柱状图",
                        "chart_type": "bar",
                        "data": [{"method_name": "ceg", "metric_value": 1.0}],
                        "encodings": {"x": "method_name", "y": "metric_value"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    render_out = tmp_path / "rendered"
    subprocess.run(
        [sys.executable, "scripts/render_paper_figures.py", "--figure-specs", str(specs_path), "--out", str(render_out)],
        cwd=".",
        check=True,
    )
    assert (render_out / "figures" / "simple_bar.svg").exists()

@pytest.mark.quick
def test_build_paper_outputs_cli_writes_records_artifacts_and_rendered_figures(tmp_path) -> None:
    """一键论文输出脚本应同时生成 records、指标产物、SVG 图表和 HTML 报告。"""
    events_path = tmp_path / "events.json"
    thresholds_path = tmp_path / "thresholds.json"
    output_root = tmp_path / "paper_outputs"
    events_path.write_text(
        json.dumps(
            [
                {
                    "event_id": "event_full_output",
                    "split": "test",
                    "sample_role": "positive_source",
                    "attack_family": "rotation",
                    "attack_condition": "rotation_light",
                    "is_watermarked": True,
                    "payload": {
                        "thresholds": {"content_threshold": 0.5, "attestation_threshold": 0.5},
                        "content": {"content_score_raw": 0.8},
                        "geometry": {
                            "registration_confidence": 0.9,
                            "anchor_inlier_ratio": 0.8,
                            "recovered_sync_consistency": 0.8,
                        },
                        "attestation": {"attestation_score": 0.9},
                        "standard_metrics": {
                            "bit_accuracy": 0.95,
                            "payload_recovered": True,
                            "psnr": 41.0,
                            "ssim": 0.97,
                        },
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    thresholds_path.write_text(json.dumps({"ceg": 0.5}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_paper_outputs.py",
            "--events",
            str(events_path),
            "--thresholds",
            str(thresholds_path),
            "--profile",
            "paper_main_probe",
            "--out",
            str(output_root),
        ],
        cwd=".",
        check=True,
    )

    assert (output_root / "event_records.json").exists()
    assert (output_root / "artifacts" / "standard_watermark_metrics.json").exists()
    assert (output_root / "artifacts" / "paper_figure_specs.json").exists()
    assert (output_root / "rendered_figures" / "paper_figures_report.html").exists()
    assert (output_root / "rendered_figures" / "figures" / "main_detection_comparison.svg").exists()
    summary = json.loads((output_root / "paper_outputs_summary.json").read_text(encoding="utf-8"))
    assert summary["figure_count"] == 8
