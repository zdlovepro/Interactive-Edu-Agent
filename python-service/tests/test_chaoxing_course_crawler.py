from __future__ import annotations

import asyncio

import pytest

from app.course_resource_importer import chaoxing_course_crawler as crawler
from app.course_resource_importer.authorized_fetcher import AuthorizedHtmlFetchResult
from app.course_resource_importer.models import AuthorizedFetchContext


def test_discover_from_chapter_uses_final_chapter_url_as_referer(monkeypatch: pytest.MonkeyPatch):
    final_chapter_url = (
        "https://mooc1.chaoxing.com/mycourse/studentstudy?"
        "chapterId=987654&courseId=260728285&clazzid=139811358&cpi=final_cpi&mooc2=1"
    )
    captured: dict[str, str] = {}

    async def fake_fetch_with_final_url(url: str, context: AuthorizedFetchContext):
        captured["transfer_url"] = url
        captured["transfer_referer"] = context.referer or ""
        return AuthorizedHtmlFetchResult(html="<html>chapter</html>", final_url=final_chapter_url, status=200)

    async def fake_post_form(url: str, *, body: str, context: AuthorizedFetchContext):
        captured["ajax_url"] = url
        captured["ajax_body"] = body
        captured["ajax_referer"] = context.referer or ""
        return '<input id="cardcount" value="1">'

    async def fake_fetch_html(url: str, context: AuthorizedFetchContext):
        captured["cards_url"] = url
        captured["cards_referer"] = context.referer or ""
        return 'mArg = {"downloadUrl":"https://p.ananas.chaoxing.com/course/deck.pdf","name":"deck.pdf"};'

    monkeypatch.setattr(crawler, "fetch_authorized_html_with_final_url", fake_fetch_with_final_url)
    monkeypatch.setattr(crawler, "_post_chaoxing_form", fake_post_form)
    monkeypatch.setattr(crawler, "fetch_authorized_html", fake_fetch_html)

    chapter = crawler._ChapterRef(
        courseid="260728285",
        clazzid="139811358",
        knowledgeid="987654",
        transfer_url="https://mooc1.chaoxing.com/mycourse/transfer?moocId=260728285",
    )
    context = AuthorizedFetchContext(cookie="UID=secret", rate_limit_per_host=1000.0)

    resources = asyncio.run(crawler._discover_from_chapter(chapter, cpi="original_cpi", context=context))

    assert captured["transfer_referer"] == "https://mooc2-ans.chaoxing.com/"
    assert captured["ajax_referer"] == final_chapter_url
    assert captured["cards_referer"] == final_chapter_url
    assert "cpi=final_cpi" in captured["ajax_body"]
    assert "cpi=final_cpi" in captured["cards_url"]
    assert resources
