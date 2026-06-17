"""CEG 内容链原语导出。"""

from main.watermarking.content_chain.embedding import (
    CONTENT_CHAIN_EMBEDDING_BACKEND_ID,
    CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE,
    ContentChainEmbeddingRequest,
    ContentChainEmbeddingResult,
    embed_content_chain_watermark,
)
from main.watermarking.content_chain.scoring import (
    CONTENT_CHAIN_BACKEND_ID,
    CONTENT_CHAIN_BACKEND_ROLE,
    ContentChainRequest,
    ContentChainResult,
    extract_content_chain_evidence,
)

__all__ = [
    "CONTENT_CHAIN_BACKEND_ID",
    "CONTENT_CHAIN_BACKEND_ROLE",
    "CONTENT_CHAIN_EMBEDDING_BACKEND_ID",
    "CONTENT_CHAIN_EMBEDDING_BACKEND_ROLE",
    "ContentChainEmbeddingRequest",
    "ContentChainEmbeddingResult",
    "ContentChainRequest",
    "ContentChainResult",
    "embed_content_chain_watermark",
    "extract_content_chain_evidence",
]
