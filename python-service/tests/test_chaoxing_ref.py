from __future__ import annotations

import pytest

from app.course_resource_importer.chaoxing_ref import build_chaoxing_course_url, parse_chaoxing_course_url
from app.course_resource_importer.errors import InvalidCourseRefError, UnsafeUrlError
from app.course_resource_importer.models import ChaoxingCourseRef


def test_parse_chaoxing_course_url_extracts_required_fields():
    url = (
        "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu"
        "?courseid=260728285&clazzid=139811358&cpi=356891153"
        "&enc=2448a3080846a1ab7a7c597107a9c576&t=1779005233298&pageHeader=0&v=0&hideHead=0"
    )

    ref = parse_chaoxing_course_url(url)

    assert ref == ChaoxingCourseRef(
        courseid="260728285",
        clazzid="139811358",
        cpi="356891153",
        enc="2448a3080846a1ab7a7c597107a9c576",
        t="1779005233298",
        raw_url=url,
        referer=url,
    )


def test_parse_chaoxing_course_url_requires_courseid():
    url = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu?clazzid=139811358&cpi=356891153"

    with pytest.raises(InvalidCourseRefError, match="courseid"):
        parse_chaoxing_course_url(url)


def test_parse_chaoxing_course_url_rejects_non_chaoxing_domain():
    url = "https://example.com/mooc2-ans/mycourse/stu?courseid=260728285"

    with pytest.raises(UnsafeUrlError, match="chaoxing.com"):
        parse_chaoxing_course_url(url)


def test_build_chaoxing_course_url_constructs_expected_url():
    ref = ChaoxingCourseRef(
        courseid="260728285",
        clazzid="139811358",
        cpi="356891153",
        enc="2448a3080846a1ab7a7c597107a9c576",
    )

    url = build_chaoxing_course_url(ref)

    assert url == (
        "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/stu"
        "?courseid=260728285&clazzid=139811358&cpi=356891153"
        "&enc=2448a3080846a1ab7a7c597107a9c576&pageHeader=0&v=0&hideHead=0"
    )
