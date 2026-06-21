import html
import re
from pathlib import Path
from typing import List


PRESENTATION_PATH = Path(__file__).parents[1] / "presentation" / "index.html"
SLIDE_PATTERN = re.compile(
    r'<section class="slide(?: active)?">(.*?)</section>', re.DOTALL
)


def _presentation_html() -> str:
    return PRESENTATION_PATH.read_text(encoding="utf-8")


def _slides() -> List[str]:
    return SLIDE_PATTERN.findall(_presentation_html())


def _plain_text(fragment: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(without_tags).split())


def test_presentation_contains_approved_18_slide_sequence() -> None:
    expected_headings = [
        "AI-Based Lecture Note Question Answering System",
        "Problem Statement",
        "Project Objectives",
        "Project Scope and Boundaries",
        "Literature Review — Top Three Studies",
        "Research Gap and Project Contribution",
        "Methodology",
        "System Architecture and Technology Stack",
        "PDF Ingestion and Indexing",
        "Retrieval and Answer-Generation Flow",
        "Core Technical Design",
        "Interface and User Workflow",
        "Chat Demonstration",
        "Evaluation Method — RAGAS",
        "RAGAS Results",
        "Findings and Discussion",
        "Limitations and Future Work",
        "Conclusion",
    ]
    slide_text = [_plain_text(slide) for slide in _slides()]
    assert len(slide_text) == 18
    assert all(
        expected in actual
        for expected, actual in zip(expected_headings, slide_text)
    )


def test_research_slides_include_required_scope_and_methodology() -> None:
    source = _presentation_html()
    required_phrases = [
        "In scope",
        "Out of scope",
        "Project and Problem Understanding",
        "Lecture-Note Data Understanding",
        "PDF Extraction and Text Preparation",
        "RAG Modelling and Application Development",
        "Technical and Functional Evaluation",
        "Deployment and Iterative Refinement",
    ]
    assert all(phrase in source for phrase in required_phrases)


def test_literature_slide_uses_verified_top_three_studies() -> None:
    source = _presentation_html()
    expected = [
        ('data-study-rank="1"', "Alawwad et al. (2025)", "84.24%"),
        ('data-study-rank="2"', "Hu et al. (2025)", "20.1%"),
        ('data-study-rank="3"', "Neumann et al. (2024)", "88%"),
    ]
    for rank_attribute, citation, result in expected:
        assert rank_attribute in source
        assert citation in source
        assert result in source


def test_results_graph_embeds_recalculated_ragas_means() -> None:
    source = _presentation_html()
    expected_attributes = [
        'data-series="baseline" data-values="0.85,0.86,0.67,0.84"',
        'data-series="smart-chunking" data-values="0.59,0.60,0.29,0.24"',
        'data-series="enhanced-retrieval" data-values="0.65,0.80,0.53,0.58"',
    ]
    assert all(attribute in source for attribute in expected_attributes)
    assert "25 identical question/reference pairs" in source


def test_unsupported_legacy_claims_are_removed() -> None:
    source = _presentation_html()
    unsupported_claims = [
        "150 lecture PDFs",
        "1,800 pages",
        "12 pages/sec",
        "320 ms",
        "+16.7% improvement",
        "Hybrid retrieval combining BM25 and dense vectors",
    ]
    assert all(claim not in source for claim in unsupported_claims)


def test_navigation_uses_computed_slide_count() -> None:
    source = _presentation_html()
    assert "var total = slides.length;" in source
    assert "totalEl.textContent = total;" in source
    assert '<span id="total">18</span>' in source
