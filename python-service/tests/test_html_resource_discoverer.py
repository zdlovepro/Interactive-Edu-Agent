from __future__ import annotations

from app.course_resource_importer.html_resource_discoverer import discover_resources_from_html


def test_html_discoverer_finds_content_image_and_pdf_link():
    html = """
    <html>
      <body>
        <img src="/courseware/Machine-Learning-cover.png" alt="Machine Learning 封面" width="1280" height="720" />
        <a href="https://mooc1.chaoxing.com/files/lecture-notes.pdf">课程讲义 PDF</a>
      </body>
    </html>
    """

    resources = discover_resources_from_html(
        html,
        page_url="https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
    )

    assert len(resources) == 2
    by_extension = {resource.extension: resource for resource in resources}

    assert by_extension["png"].resource_kind in {"slide_image", "content_image"}
    assert by_extension["png"].url == "https://mooc2-ans.chaoxing.com/courseware/Machine-Learning-cover.png"
    assert by_extension["pdf"].resource_kind == "courseware_file"
    assert by_extension["pdf"].title == "课程讲义 PDF"


def test_html_discoverer_marks_ui_assets_and_filters_unsafe_urls():
    html = """
    <html>
      <body>
        <img src="/static/icon-tool.png" alt="工具图标" width="32" height="32" />
        <img src="/static/read-loading.gif" alt="加载中" />
        <img src="javascript:alert('xss')" alt="bad" />
        <link href="/static/site.css" rel="stylesheet" />
      </body>
    </html>
    """

    resources = discover_resources_from_html(
        html,
        page_url="https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
    )

    assert len(resources) == 2
    assert all(resource.resource_kind == "ui_asset" for resource in resources)
    assert all(resource.extension in {"png", "gif"} for resource in resources)


def test_html_discoverer_parses_inline_script_for_relative_urls():
    html = """
    <html>
      <body>
        <script>
          window.pageData = {
            downloadUrl: "/ananas/modules/download/123/demo.pdf"
          };
        </script>
      </body>
    </html>
    """

    resources = discover_resources_from_html(
        html,
        page_url="https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?courseid=260728285",
    )

    assert len(resources) == 1
    assert resources[0].url == "https://mooc2-ans.chaoxing.com/ananas/modules/download/123/demo.pdf"
    assert resources[0].resource_kind == "courseware_file"
