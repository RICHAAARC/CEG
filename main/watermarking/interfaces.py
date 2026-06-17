"""CEG 水印运行时的通用接口契约。

该模块只定义方法原语之间交换数据的轻量结构, 不负责 Colab 编排、harness 门禁、
Google Drive 打包或 CEG-WM 兼容层。这样设计的主要考虑在于: 后续 semantic mask、
LF/HF 内容链、几何恢复和 attestation backend 可以在 CEG 项目内部逐步替换实现,
同时保持 image generation、detection 和 artifact rebuild 对同一组字段有稳定理解。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class WatermarkPromptContext:
    """描述一次图像生成请求与 prompt 的绑定关系。

    该结构属于通用工程写法: 它把 prompt、seed、模型标识和生成参数集中保存,
    避免各个 backend 通过松散字典重复猜测字段含义。在 CEG 项目中, 这些字段后续可
    同时供 clean image 生成、watermark embedding、detection records 和论文结果追溯复用。
    """

    image_id: str
    prompt_id: str
    prompt_text: str
    seed: int | None = None
    model_id: str | None = None
    generation_params: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """转换为可写入 manifest 或 record 的普通字典。"""

        return {
            "image_id": self.image_id,
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "seed": self.seed,
            "model_id": self.model_id,
            "generation_params": dict(self.generation_params),
        }


@dataclass(frozen=True)
class WatermarkEmbeddingRequest:
    """描述水印嵌入 backend 所需的最小输入。

    该结构不绑定具体算法。CEG 的正式 backend 可以在 `watermark_config` 中读取
    semantic mask、LF/HF、geometry 或 attestation 参数, pilot backend 也可以只读取少量参数。
    """

    clean_image_path: Path
    watermarked_image_path: Path
    prompt_context: WatermarkPromptContext
    method_name: str = "ceg"
    watermark_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WatermarkEmbeddingResult:
    """描述一次水印嵌入的输出与可追溯元数据。

    `paper_main_method_ready` 是 CEG 项目特定字段, 用于防止 pilot 或 smoke backend 被误认为
    顶会论文正式主方法。正式 CEG backend 只有在实现 semantic mask、内容链、几何恢复和
    attestation 等必要机制后, 才应该显式设置为 True。
    """

    watermarked_image_path: Path
    backend_id: str
    backend_role: str
    method_name: str
    paper_main_method_ready: bool
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """转换为 manifest 可序列化记录, 供脚本和 artifact rebuild 复用。"""

        return {
            "watermarked_image_path": self.watermarked_image_path.as_posix(),
            "backend_id": self.backend_id,
            "backend_role": self.backend_role,
            "method_name": self.method_name,
            "paper_main_method_ready": self.paper_main_method_ready,
            "diagnostics": dict(self.diagnostics),
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class WatermarkDetectionRequest:
    """描述水印检测 backend 所需的最小输入。"""

    image_path: Path
    prompt_context: WatermarkPromptContext
    method_name: str = "ceg"
    detector_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WatermarkDetectionResult:
    """描述检测分数、阈值判定和检测 provenance。

    该结构为后续 TPP@FPR 统计提供稳定字段。`score` 是连续检测分数,
    `threshold` 是固定 FPR 校准得到的阈值, `decision` 是在阈值可用时的布尔判定。
    """

    score: float
    threshold: float | None
    decision: bool | None
    backend_id: str
    method_name: str
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """转换为 detection records 可直接消费的普通字典。"""

        return {
            "score": self.score,
            "threshold": self.threshold,
            "decision": self.decision,
            "backend_id": self.backend_id,
            "method_name": self.method_name,
            "diagnostics": dict(self.diagnostics),
            "provenance": dict(self.provenance),
        }


class WatermarkEmbedder(Protocol):
    """水印嵌入 backend 的可替换接口。"""

    backend_id: str
    backend_role: str

    def embed(self, request: WatermarkEmbeddingRequest) -> WatermarkEmbeddingResult:
        """读取 clean 图像并写出 watermarked 图像。"""


class WatermarkDetector(Protocol):
    """水印检测 backend 的可替换接口。"""

    backend_id: str
    backend_role: str

    def detect(self, request: WatermarkDetectionRequest) -> WatermarkDetectionResult:
        """读取图像并返回可用于 TPP@FPR 统计的检测分数。"""
