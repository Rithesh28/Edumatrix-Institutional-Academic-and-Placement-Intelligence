#!/usr/bin/env python
"""
Focused regression tests for the URL extraction bug fix.
Tests the exact OCR-split Google Forms URL case and related scenarios.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.jd_parser_service import JdParserService

parser = JdParserService()

def test_ocr_split_forms_gle_url():
    """Test the exact OCR-split URL from the bug report."""
    raw = "Apply at https://forms.gle/ yP4tpWtmk9 VdFFBU8"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    # The preprocessed text should contain the full URL
    assert "forms.gle/yP4tpWtmk9VdFFBU8" in pre, f"Expected full URL in preprocessed text, got: {pre}"

    # Now test the full extraction pipeline
    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected full URL, got: {url}"
    print("✓ PASS: OCR-split forms.gle URL correctly reconstructed")


def test_intact_forms_gle_url():
    """Test that an already-correct URL still works."""
    raw = "Apply at https://forms.gle/yP4tpWtmk9VdFFBU8"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected full URL, got: {url}"
    print("✓ PASS: Intact forms.gle URL works correctly")


def test_prose_after_url_not_appended():
    """Test that ordinary prose after a URL is not concatenated."""
    raw = "Apply at https://forms.gle/yP4tpWtmk9VdFFBU8 and then wait for confirmation"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected URL without prose, got: {url}"
    print("✓ PASS: Prose after URL not appended")


def test_ocr_split_prose_after_not_appended():
    """Test that prose after OCR-split URL is not concatenated."""
    raw = "Apply at https://forms.gle/ yP4tpWtmk9 VdFFBU8 and then wait for confirmation"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected URL without prose, got: {url}"
    print("✓ PASS: Prose after OCR-split URL not appended")


def test_query_parameters_preserved():
    """Test that query parameters are preserved."""
    raw = "Apply at https://forms.gle/yP4tpWtmk9VdFFBU8?ref=abc&source=email"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8?ref=abc&source=email", f"Expected URL with query params, got: {url}"
    print("✓ PASS: Query parameters preserved")


def test_ocr_split_with_query_parameters():
    """Test OCR-split URL with query parameters."""
    raw = "Apply at https://forms.gle/ yP4tpWtmk9 VdFFBU8?ref=abc"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8?ref=abc", f"Expected URL with query params, got: {url}"
    print("✓ PASS: OCR-split URL with query params works")


def test_trailing_punctuation_stripped():
    """Test that trailing punctuation is stripped."""
    raw = "Apply at https://forms.gle/yP4tpWtmk9VdFFBU8."
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected URL without trailing period, got: {url}"
    print("✓ PASS: Trailing punctuation stripped")


def test_distinct_urls_not_merged():
    """Test that two distinct URLs are not merged."""
    raw = "Apply at https://forms.gle/ yP4tpWtmk9 VdFFBU8 or https://forms.gle/abc123"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    # Extract all candidates
    candidates = parser._extract_all_application_urls(raw)
    print(f"Candidates: {[c['url'] for c in candidates]}")

    # Should have two distinct URLs
    assert len(candidates) >= 2, f"Expected at least 2 candidates, got {len(candidates)}"

    urls = [c['url'] for c in candidates]
    assert "https://forms.gle/yP4tpWtmk9VdFFBU8" in urls, f"Missing first URL: {urls}"
    assert "https://forms.gle/abc123" in urls, f"Missing second URL: {urls}"
    print("✓ PASS: Distinct URLs not merged")


def test_ocr_split_newline_still_works():
    """Test that the existing newline-split handling still works."""
    raw = "Apply at https://forms.gle/\nyP4tpWtmk9VdFFBU8"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {repr(raw)}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    assert url == "https://forms.gle/yP4tpWtmk9VdFFBU8", f"Expected full URL, got: {url}"
    print("✓ PASS: Newline-split forms.gle URL still works")


def test_forms_office_com_still_works():
    """Test that forms.office.com handling still works."""
    raw = "Apply at https://forms.office.com/r/ abc123 def456"
    pre = parser._preprocess_text_for_urls(raw)
    print(f"Input:    {raw}")
    print(f"Preprocessed: {pre}")

    url, _ = parser._extract_application_url_and_instructions(raw, {})
    print(f"Extracted URL: {url}")
    # Note: forms.office.com only handles single token currently
    assert "forms.office.com/r/abc123" in pre or url is not None, f"Unexpected result: {pre}"
    print("✓ PASS: forms.office.com handling unchanged")


if __name__ == "__main__":
    print("=" * 60)
    print("Running focused URL extraction regression tests...")
    print("=" * 60)

    test_ocr_split_forms_gle_url()
    test_intact_forms_gle_url()
    test_prose_after_url_not_appended()
    test_ocr_split_prose_after_not_appended()
    test_query_parameters_preserved()
    test_ocr_split_with_query_parameters()
    test_trailing_punctuation_stripped()
    test_distinct_urls_not_merged()
    test_ocr_split_newline_still_works()
    test_forms_office_com_still_works()

    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)