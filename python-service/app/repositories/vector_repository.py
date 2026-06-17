from __future__ import annotations

import json
import re
import socket
from itertools import count
from typing import Any, Dict, List
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import VectorStoreException
from app.utils.logger import logger

try:  # pragma: no cover - optional dependency
    import jieba  # type: ignore
except Exception:  # noqa: BLE001
    jieba = None

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
except Exception:  # noqa: BLE001
    Collection = None
    CollectionSchema = None
    DataType = None
    FieldSchema = None
    connections = None
    utility = None


class MilvusVectorRepository:
    _REQUIRED_FIELDS = {
        "courseware_id",
        "node_id",
        "chunk_id",
        "page_index",
        "content",
        "metadata_json",
        "vector",
    }

    def __init__(self, collection_name: str, dim: int) -> None:
        if connections is None:
            raise VectorStoreException("Milvus 依赖不可用")

        self.collection_name = collection_name
        self.dim = dim
        self.collection = None
        self._connect()

    def insert_documents(
        self,
        courseware_id: str,
        documents: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> int:
        if not documents:
            return 0
        if self.collection is None:
            raise VectorStoreException("Milvus collection 未初始化")
        if len(documents) != len(vectors):
            raise VectorStoreException("向量数量与文档数量不一致")

        entities = [
            [courseware_id] * len(documents),
            [str(document.get("node_id", "")) for document in documents],
            [str(document.get("chunk_id", "")) for document in documents],
            [int(document.get("page_index", 0)) for document in documents],
            [_normalize_content(document) for document in documents],
            [_metadata_json(document) for document in documents],
            vectors,
        ]

        try:
            result = self.collection.insert(entities)
            self.collection.flush()
            logger.info("Milvus insert completed. coursewareId=%s count=%s", courseware_id, len(documents))
            return len(result.primary_keys)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Milvus insert failed. coursewareId=%s count=%s", courseware_id, len(documents))
            raise VectorStoreException("Milvus 写入失败") from exc

    def search_similar(
        self,
        *,
        query: str,
        query_vector: List[float] | None,
        courseware_id: str | None,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if self.collection is None:
            raise VectorStoreException("Milvus collection 未初始化")
        if query_vector is None:
            raise VectorStoreException("查询向量缺失")

        search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
        expr = f"courseware_id == '{courseware_id}'" if courseware_id else None

        try:
            results = self.collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=[
                    "courseware_id",
                    "node_id",
                    "chunk_id",
                    "page_index",
                    "content",
                    "metadata_json",
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Milvus search failed. coursewareId=%s topK=%s", courseware_id, top_k)
            raise VectorStoreException("Milvus 检索失败") from exc

        output: List[Dict[str, Any]] = []
        for hits in results:
            for hit in hits:
                metadata = _parse_metadata_json(hit.entity.get("metadata_json"))
                output.append(
                    {
                        "id": hit.id,
                        "score": float(hit.distance),
                        "distance": float(hit.distance),
                        "courseware_id": hit.entity.get("courseware_id"),
                        "node_id": hit.entity.get("node_id"),
                        "chunk_id": hit.entity.get("chunk_id"),
                        "page_index": int(hit.entity.get("page_index") or 0),
                        "content": hit.entity.get("content"),
                        "metadata": metadata,
                    }
                )
        return output

    def _connect(self) -> None:
        logger.info("Initializing Milvus vector repository.")
        if not _is_milvus_endpoint_reachable(settings.MILVUS_URI, settings.MILVUS_CONNECT_TIMEOUT_SECONDS):
            logger.warning("Milvus endpoint is unreachable. Fallback will be used. uri=%s", settings.MILVUS_URI)
            raise VectorStoreException("Milvus endpoint is unreachable")
        try:
            connections.connect(
                alias="default",
                uri=settings.MILVUS_URI,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
                db_name=settings.MILVUS_DB_NAME,
                timeout=settings.MILVUS_CONNECT_TIMEOUT_SECONDS,
            )
            self._init_collection()
            logger.info("Milvus vector repository is ready. collection=%s", self.collection_name)
        except VectorStoreException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Milvus unavailable. Fallback will be used. reason=%s", type(exc).__name__)
            raise VectorStoreException("Milvus 不可用") from exc

    def _init_collection(self) -> None:
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            if not self._is_collection_schema_compatible():
                logger.warning(
                    "Milvus collection schema incompatible. collection=%s requiredFields=%s",
                    self.collection_name,
                    sorted(self._REQUIRED_FIELDS),
                )
                raise VectorStoreException("Milvus collection schema incompatible")
            self.collection.load()
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="courseware_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="node_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="page_index", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
        ]
        schema = CollectionSchema(fields=fields, description="Courseware knowledge fragments")
        self.collection = Collection(name=self.collection_name, schema=schema)
        self.collection.create_index(
            field_name="vector",
            index_params={
                "metric_type": "IP",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            },
        )
        self.collection.load()

    def _is_collection_schema_compatible(self) -> bool:
        if self.collection is None or getattr(self.collection, "schema", None) is None:
            return False

        fields = {field.name: field for field in self.collection.schema.fields}
        if not self._REQUIRED_FIELDS.issubset(fields.keys()):
            return False

        vector_field = fields.get("vector")
        vector_dim = getattr(vector_field, "params", {}).get("dim") if vector_field is not None else None
        return vector_dim == self.dim


class KeywordVectorRepository:
    def __init__(self) -> None:
        self._documents: List[Dict[str, Any]] = []
        self._id_sequence = count(1)

    def insert_documents(
        self,
        courseware_id: str,
        documents: List[Dict[str, Any]],
        vectors: List[List[float]] | None = None,
    ) -> int:
        inserted = 0
        for document in documents:
            content = _normalize_content(document)
            if not content:
                continue
            self._documents.append(
                {
                    "id": next(self._id_sequence),
                    "courseware_id": courseware_id,
                    "node_id": str(document.get("node_id", "")),
                    "chunk_id": str(document.get("chunk_id", "")),
                    "page_index": int(document.get("page_index", 0)),
                    "content": content,
                    "metadata": _metadata_dict(document),
                }
            )
            inserted += 1
        logger.info("Keyword fallback repository stored documents. coursewareId=%s count=%s", courseware_id, inserted)
        return inserted

    def search_similar(
        self,
        *,
        query: str,
        query_vector: List[float] | None,
        courseware_id: str | None,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        filtered = [
            document
            for document in self._documents
            if courseware_id is None or document["courseware_id"] == courseware_id
        ]

        scored = []
        for document in filtered:
            score = _keyword_score(query, document["content"])
            if score <= 0:
                continue
            scored.append(
                {
                    "id": document["id"],
                    "score": float(score),
                    "distance": float(score),
                    "courseware_id": document["courseware_id"],
                    "node_id": document["node_id"],
                    "chunk_id": document["chunk_id"],
                    "page_index": document["page_index"],
                    "content": document["content"],
                    "metadata": document["metadata"],
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        # Deduplicate by chunk_id to avoid repeated evidence when ingested multiple times.
        deduped: List[Dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()
        for item in scored:
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            deduped.append(item)
            if len(deduped) >= top_k:
                break
        return deduped


def _normalize_content(document: Dict[str, Any]) -> str:
    content = document.get("content") or document.get("text") or ""
    return str(content).strip()


def _metadata_dict(document: Dict[str, Any]) -> Dict[str, Any]:
    metadata = document.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def _metadata_json(document: Dict[str, Any]) -> str:
    return json.dumps(_metadata_dict(document), ensure_ascii=False, sort_keys=True)


def _is_milvus_endpoint_reachable(uri: str, timeout_seconds: float) -> bool:
    normalized_uri = (uri or "").strip()
    if not normalized_uri:
        return False

    parsed = urlparse(normalized_uri if "://" in normalized_uri else f"tcp://{normalized_uri}")
    host = parsed.hostname
    port = parsed.port or 19530
    if not host:
        return False

    try:
        with socket.create_connection((host, port), timeout=max(0.2, float(timeout_seconds))):
            return True
    except OSError:
        return False


def _parse_metadata_json(raw_value: Any) -> Dict[str, Any]:
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    try:
        parsed = json.loads(str(raw_value))
    except Exception:  # noqa: BLE001
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _keyword_score(query: str, content: str) -> float:
    query_lower = query.lower().strip()
    content_lower = content.lower()
    score = 2.0 if query_lower and query_lower in content_lower else 0.0
    for token in _tokenize(query_lower):
        if token and token in content_lower:
            score += 1.0
    return score


def _tokenize(text: str) -> List[str]:
    raw_tokens = [
        token
        for token in re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text)
        if token
    ]
    if not raw_tokens:
        return []

    expanded: List[str] = []
    for token in raw_tokens:
        expanded.append(token)

        # Expand long Chinese token into smaller units for better matching.
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if jieba is not None:
                try:
                    expanded.extend([part for part in jieba.cut(token) if part and part.strip()])
                except Exception:  # noqa: BLE001
                    pass

            if len(token) >= 4:
                # 2-gram shingles to capture key terms like “图表/流程图/表格”.
                expanded.extend([token[i:i + 2] for i in range(0, len(token) - 1)])

    # Deduplicate while keeping order.
    seen = set()
    result: List[str] = []
    for item in expanded:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
