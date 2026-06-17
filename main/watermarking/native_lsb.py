"""CEG 内部 pilot 级图像水印原语。

该模块把此前脚本内联的 `ceg_native_lsb` 抽出为可复用模块。它的作用是为
Colab 图像生成链路提供项目内自包含、可复现、可检测的像素级水印输出, 从而避免
运行时调用其他项目。

重要边界:
- 该实现是真实像素写入, 不是复制、mock 或空输出。
- 该实现属于 pilot backend, 不是顶会论文主方法的最终 CEG 水印机制。
- 正式论文主方法仍应在本包内补齐 semantic mask、LF / HF、geometry 和 attestation。
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping


NATIVE_LSB_BACKEND_ID = "ceg_native_lsb"
NATIVE_LSB_BACKEND_ROLE = "pilot_self_contained_pixel_watermark"


@dataclass(frozen=True)
class NativeLsbWatermarkResult:
    """描述一次 CEG 内部 LSB 水印嵌入结果。

    该结构可直接写入 backend manifest。字段保持简单, 便于后续正式 CEG pipeline
    复用相同 reporting surface, 将 pilot backend 替换为正式 LF / HF / geometry backend。
    """

    watermarked_path: str
    bit_count: int
    changed_channel_count: int
    capacity_channel_count: int
    seed_digest_prefix: str

    def to_report(self) -> dict[str, Any]:
        """转换为图像生成 backend 可写入的报告字典。"""
        return {
            "watermark_backend": NATIVE_LSB_BACKEND_ID,
            "watermark_backend_role": NATIVE_LSB_BACKEND_ROLE,
            "returncode": 0,
            "watermarked_path": self.watermarked_path,
            "bit_count": self.bit_count,
            "changed_channel_count": self.changed_channel_count,
            "capacity_channel_count": self.capacity_channel_count,
            "seed_digest_prefix": self.seed_digest_prefix,
            "paper_main_method_ready": False,
            "paper_main_method_blocking_reason": "pilot_lsb_backend_not_full_ceg_watermark",
        }


def _as_text(value: Any, default: str = "") -> str:
    """把可选字段转换为去空白字符串。"""
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def bytes_to_bits(payload: bytes) -> list[int]:
    """把字节串转换为高位优先的 bit 列表。"""
    bits: list[int] = []
    for byte in payload:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def build_native_watermark_bits(
    row: Mapping[str, Any],
    generation_meta: Mapping[str, Any],
    *,
    bit_count: int,
) -> list[int]:
    """构造 CEG 项目内原生图像水印 bit 序列。

    通用工程写法是由稳定元数据生成 digest, 再扩展为 bit 流。项目特定部分是:
    当前 bit payload 绑定 image_id、prompt_id、prompt、seed 和生成参数, 使后续 detector
    可以用同一规则恢复期望 bit。该规则不依赖任何外部项目运行时。
    """
    if bit_count < 1:
        raise ValueError("bit_count must be >= 1")
    payload = {
        "image_id": _as_text(row.get("image_id") or row.get("event_id")),
        "prompt_id": _as_text(row.get("prompt_id")),
        "prompt_text": generation_meta.get("prompt_text"),
        "seed": generation_meta.get("seed"),
        "num_inference_steps": generation_meta.get("num_inference_steps"),
        "guidance_scale": generation_meta.get("guidance_scale"),
    }
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).digest()
    bits = bytes_to_bits(digest)
    while len(bits) < bit_count:
        digest = hashlib.sha256(digest).digest()
        bits.extend(bytes_to_bits(digest))
    return bits[:bit_count]


def _build_position_seed(row: Mapping[str, Any], generation_meta: Mapping[str, Any]) -> bytes:
    """构造像素通道位置采样的稳定随机种子。"""
    seed_material = {
        "image_id": _as_text(row.get("image_id") or row.get("event_id")),
        "seed": generation_meta.get("seed"),
        "prompt_text": generation_meta.get("prompt_text"),
        "backend": NATIVE_LSB_BACKEND_ID,
    }
    return hashlib.sha256(json.dumps(seed_material, ensure_ascii=False, sort_keys=True).encode("utf-8")).digest()


def embed_native_lsb_watermark(
    *,
    clean_path: str | Path,
    watermarked_path: str | Path,
    row: Mapping[str, Any],
    generation_meta: Mapping[str, Any],
    bit_count: int,
) -> NativeLsbWatermarkResult:
    """使用 CEG 仓库内原生 LSB 图像水印原语生成 watermarked 图像。

    算法流程是: 读取 clean 图像, 由样本元数据生成稳定 bit 流, 再按 seed 派生的
    伪随机位置选择像素通道, 将最低有效位改写为水印 bit。该函数可在其他项目中复用为
    “可追溯像素级 pilot watermark”实现, 但不能替代正式 CEG 方法中的语义路由、LF / HF、
    geometry 和 attestation 机制。
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - 由运行环境依赖决定
        raise RuntimeError("CEG 原生图像水印需要安装 Pillow。") from exc

    clean = Path(clean_path)
    watermarked = Path(watermarked_path)
    image = Image.open(clean).convert("RGB")
    width, height = image.size
    pixels = bytearray(image.tobytes())
    capacity = len(pixels)
    if capacity < bit_count:
        raise RuntimeError(f"图像容量不足以嵌入水印: capacity={capacity}, bit_count={bit_count}")

    seed_digest = _build_position_seed(row, generation_meta)
    positions = list(range(capacity))
    rng = random.Random(int.from_bytes(seed_digest[:8], "big"))
    rng.shuffle(positions)
    bits = build_native_watermark_bits(row, generation_meta, bit_count=bit_count)

    changed_count = 0
    for position, bit in zip(positions, bits):
        old_value = pixels[position]
        new_value = (old_value & 0xFE) | bit
        if new_value != old_value:
            changed_count += 1
        pixels[position] = new_value

    watermarked.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGB", (width, height), bytes(pixels)).save(watermarked)
    return NativeLsbWatermarkResult(
        watermarked_path=str(watermarked),
        bit_count=bit_count,
        changed_channel_count=changed_count,
        capacity_channel_count=capacity,
        seed_digest_prefix=seed_digest.hex()[:16],
    )
