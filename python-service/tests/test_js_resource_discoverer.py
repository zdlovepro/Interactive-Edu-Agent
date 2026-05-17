from __future__ import annotations

from app.course_resource_importer.js_resource_discoverer import discover_resources_from_js_text


def test_js_discoverer_finds_pdf_from_download_url():
    js_text = """
    const courseware = {
      title: "课程讲义",
      downloadUrl: "https://mooc1.chaoxing.com/files/lesson.pdf"
    };
    """

    resources = discover_resources_from_js_text(js_text)

    assert len(resources) == 1
    resource = resources[0]
    assert resource.url == "https://mooc1.chaoxing.com/files/lesson.pdf"
    assert resource.extension == "pdf"
    assert resource.resource_kind == "courseware_file"


def test_js_discoverer_marks_ui_assets_and_skips_css_js_files():
    js_text = """
    const ui = {
      icon: "https://mooc1.chaoxing.com/static/icon-tool.png",
      loading: "https://mooc1.chaoxing.com/static/read-loading.gif",
      gallery: "https://mooc1.chaoxing.com/static/baguettebox.png",
      style: "https://mooc1.chaoxing.com/static/site.css",
      script: "https://mooc1.chaoxing.com/static/site.js"
    };
    """

    resources = discover_resources_from_js_text(js_text)

    assert len(resources) == 3
    assert all(resource.resource_kind == "ui_asset" for resource in resources)
    assert {resource.extension for resource in resources} == {"png", "gif"}
