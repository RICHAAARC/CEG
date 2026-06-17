"""从 image_pairs 和 attack manifest 生成 CEG detection 协议事件。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ceg_detection_producer import write_detection_inputs_from_image_manifests
from experiments.ceg_real_detection_backend import write_content_chain_detection_inputs


def _load_rows(path: Path) -> list[dict[str, object]]:
    """读取 JSON / JSONL / CSV 行文件。"""
    if path.suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError("row JSON must contain a list")
        return [dict(row) for row in payload]
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if path.suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"unsupported row extension: {path.suffix}")


def _load_manifest(path: str | None) -> dict[str, object] | None:
    """读取可选 attack manifest。"""
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise TypeError("attacked image manifest must contain an object")
    return dict(payload)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="生成 CEG detection 协议事件。")
    parser.add_argument("--image-pairs", required=True, help="image_pairs.json / jsonl / csv 路径。")
    parser.add_argument("--attacked-image-manifest", default=None, help="可选 attacked_image_manifest.json 路径。")
    parser.add_argument("--out", required=True, help="detection 输入输出目录。")
    parser.add_argument(
        "--detection-backend",
        choices=("contract_dry_run", "ceg_content_chain_detection"),
        default="contract_dry_run",
        help="检测 backend。contract_dry_run 保留旧协议演练, ceg_content_chain_detection 运行真实内容链 scoring。",
    )
    parser.add_argument("--mask-threshold-quantile", type=float, default=0.80, help="semantic mask 分位数阈值。")
    parser.add_argument("--mask-open-iters", type=int, default=1, help="semantic mask 开运算次数。")
    parser.add_argument("--mask-close-iters", type=int, default=1, help="semantic mask 闭运算次数。")
    parser.add_argument("--lf-grid-size", type=int, default=8, help="LF 内容链网格大小。")
    parser.add_argument("--hf-grid-size", type=int, default=8, help="HF 内容链网格大小。")
    parser.add_argument("--geometry-search-radius", type=int, default=8, help="几何 registration 平移搜索半径。")
    parser.add_argument("--geometry-downsample-size", type=int, default=96, help="几何 registration 下采样最长边。")
    parser.add_argument("--geometry-anchor-grid-size", type=int, default=4, help="几何 registration 局部锚点网格大小。")
    parser.add_argument("--attestation-key-env", default=None, help="可选 HMAC attestation 密钥环境变量名。")
    parser.add_argument("--attestation-key-id", default=None, help="可选 HMAC attestation 密钥标识, 只写入 digest。")
    return parser


def main() -> None:
    """CLI 入口。"""
    args = build_parser().parse_args()
    if args.detection_backend == "ceg_content_chain_detection":
        manifest = write_content_chain_detection_inputs(
            args.image_pairs,
            args.out,
            attacked_image_manifest_path=args.attacked_image_manifest,
            detector_config={
                "mask_threshold_quantile": args.mask_threshold_quantile,
                "mask_open_iters": args.mask_open_iters,
                "mask_close_iters": args.mask_close_iters,
                "lf_grid_size": args.lf_grid_size,
                "hf_grid_size": args.hf_grid_size,
                "geometry_search_radius": args.geometry_search_radius,
                "geometry_downsample_size": args.geometry_downsample_size,
                "geometry_anchor_grid_size": args.geometry_anchor_grid_size,
                "attestation_key_env": args.attestation_key_env,
                "attestation_key_id": args.attestation_key_id,
            },
        )
    else:
        manifest = write_detection_inputs_from_image_manifests(
            _load_rows(Path(args.image_pairs)),
            args.out,
            attacked_image_manifest=_load_manifest(args.attacked_image_manifest),
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
