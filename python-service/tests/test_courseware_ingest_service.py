from __future__ import annotations

from app.schemas.parse import ParseRequest
from app.services import courseware_ingest_service as ingest_pipeline_module


def test_ingest_courseware_from_parse_request_builds_chunks_and_visual_docs(monkeypatch) -> None:
    # Arrange: fake parse output with visualSummary on page 2
    def fake_parse_courseware_file(_request: ParseRequest):
        return {
            "pages": 2,
            "outline": ["p1", "p2"],
            "segments": [
                {
                    "pageIndex": 1,
                    "title": "第一页",
                    "content": "文本1",
                    "knowledgePoints": ["KP1"],
                },
                {
                    "pageIndex": 2,
                    "title": "第二页",
                    "content": "文本2",
                    "knowledgePoints": ["KP2"],
                    "visualSummary": "这里有一个柱状图，对比了A和B",
                    "visualObjects": ["图表"],
                    "pageImagePath": "/abs/page_2.png",
                },
            ],
        }

    captured_pages = {}

    class FakeChunker:
        def __init__(self, chunk_size: int, chunk_overlap: int):
            captured_pages["chunk_size"] = chunk_size
            captured_pages["chunk_overlap"] = chunk_overlap

        def chunk_courseware_pages(self, courseware_id: str, pages):
            captured_pages["courseware_id"] = courseware_id
            captured_pages["pages"] = pages
            # Return one chunk per page
            return [
                {
                    "chunk_id": f"{courseware_id}_p001_c000",
                    "page_index": 1,
                    "content": "文本1",
                    "metadata": {"page_index": 1},
                },
                {
                    "chunk_id": f"{courseware_id}_p002_c000",
                    "page_index": 2,
                    "content": "文本2",
                    "metadata": {"page_index": 2, "visual_summary": "这里有一个柱状图，对比了A和B"},
                },
            ]

    captured_ingest = {}

    def fake_ingest_courseware_chunks(courseware_id: str, chunks):
        captured_ingest["courseware_id"] = courseware_id
        captured_ingest["chunks"] = chunks
        return {"courseware_id": courseware_id, "inserted": len(chunks), "backend": "keyword_fallback"}

    monkeypatch.setattr(ingest_pipeline_module, "parse_courseware_file", fake_parse_courseware_file)
    monkeypatch.setattr(ingest_pipeline_module, "TextChunkerService", FakeChunker)
    monkeypatch.setattr(ingest_pipeline_module, "ingest_courseware_chunks", fake_ingest_courseware_chunks)

    req = ParseRequest(coursewareId="cware_demo", storage="local", key="/abs/demo.pdf")

    # Act
    result = ingest_pipeline_module.ingest_courseware_from_parse_request(
        request=req,
        chunk_size=400,
        chunk_overlap=20,
        include_visual_summary_docs=True,
    )

    # Assert: chunker got visual fields mapped and knowledge_points normalized
    assert captured_pages["chunk_size"] == 400
    assert captured_pages["chunk_overlap"] == 20
    assert captured_pages["courseware_id"] == "cware_demo"

    pages = captured_pages["pages"]
    assert pages[0]["page_index"] == 1
    assert pages[0]["knowledge_points"] == ["KP1"]
    assert pages[0].get("visualSummary") is None

    assert pages[1]["page_index"] == 2
    assert pages[1]["knowledge_points"] == ["KP2"]
    assert pages[1]["visualSummary"] == "这里有一个柱状图，对比了A和B"
    assert pages[1]["visualObjects"] == ["图表"]
    assert pages[1]["pageImagePath"] == "/abs/page_2.png"

    # Assert: ingest received 2 normal chunks + 1 visual summary doc
    assert captured_ingest["courseware_id"] == "cware_demo"
    docs = captured_ingest["chunks"]
    assert len(docs) == 3

    visual_doc = next(item for item in docs if item.get("chunk_id", "").endswith("_visual"))
    assert visual_doc["page_index"] == 2
    assert visual_doc["content"].startswith("视觉摘要：")
    assert visual_doc["metadata"]["source"] == "visual_summary"

    assert result["inserted"] == 3
    assert result["chunk_count"] == 2
    assert result["visual_doc_count"] == 1
    assert result["pages"] == 2
