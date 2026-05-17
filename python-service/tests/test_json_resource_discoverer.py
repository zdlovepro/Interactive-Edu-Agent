from __future__ import annotations

from app.course_resource_importer.json_resource_discoverer import discover_resources_from_json


def test_json_discoverer_finds_pptx_from_fileinfo_download():
    payload = {
        "title": "第一章 机器学习概览",
        "fileinfo": {
            "download": "https://pan-yz.chaoxing.com/files/chapter01.pptx",
            "objectid": "obj_123",
            "size": 2048,
            "md5": "ABCDEF123456",
        },
    }

    resources = discover_resources_from_json(payload)

    assert len(resources) == 1
    resource = resources[0]
    assert resource.url == "https://pan-yz.chaoxing.com/files/chapter01.pptx"
    assert resource.extension == "pptx"
    assert resource.resource_kind == "courseware_file"
    assert resource.object_id == "obj_123"
    assert resource.expected_size == 2048
    assert resource.expected_md5 == "abcdef123456"
    assert resource.title == "第一章 机器学习概览"


def test_json_discoverer_ignores_non_http_urls():
    payload = {
        "attachments": [
            {"downloadUrl": "javascript:alert(1)", "name": "bad"},
            {"downloadUrl": "data:text/plain;base64,SGVsbG8=", "name": "bad2"},
        ]
    }

    resources = discover_resources_from_json(payload)

    assert resources == []
