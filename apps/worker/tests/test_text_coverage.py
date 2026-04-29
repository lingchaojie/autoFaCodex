import pytest

from autofacodex.tools.text_coverage import compare_text_coverage, normalize_text


def test_normalize_text_handles_whitespace_and_full_width_punctuation():
    assert normalize_text("高管 访谈\nTraining，Materials") == "高管访谈training,materials"


def test_compare_text_coverage_scores_complete_text_as_one():
    result = compare_text_coverage("高管访谈培训材料", "高管 访谈 培训 材料")

    assert result["score"] == 1.0
    assert result["missing_ratio"] == 0.0


def test_compare_text_coverage_detects_missing_source_text():
    result = compare_text_coverage("Executive Interview Training Materials", "Executive Training")

    assert 0 < result["score"] < 1
    assert result["missing_ratio"] > 0
    assert "interview" in result["missing_text"].lower()


def test_compare_text_coverage_accepts_empty_source_text():
    result = compare_text_coverage("", "")

    assert result["score"] == 1.0
    assert result["source_length"] == 0


def test_compare_text_coverage_counts_repeated_chinese_text_quantity():
    result = compare_text_coverage("高管高管高管", "高管")

    assert result["score"] == pytest.approx(2 / 6)
    assert result["missing_ratio"] == pytest.approx(4 / 6)
    assert result["missing_ratio"] != 0


def test_compare_text_coverage_counts_repeated_english_words_quantity():
    result = compare_text_coverage("Executive Executive Training", "Executive Training")

    assert result["score"] == pytest.approx(17 / 26)
    assert result["missing_ratio"] == pytest.approx(9 / 26)
    assert "executive" in result["missing_text"].lower()


def test_compare_text_coverage_does_not_cover_numeric_substrings():
    result = compare_text_coverage("CEO Q1", "CEO Q10")

    assert result["score"] == pytest.approx(3 / 5)
    assert result["missing_ratio"] == pytest.approx(2 / 5)


def test_compare_text_coverage_scores_normalized_identical_short_ascii_as_complete():
    result = compare_text_coverage("CEO Q1", "CEOQ1")

    assert result["score"] == 1.0
    assert result["missing_ratio"] == 0.0


def test_compare_text_coverage_scores_normalized_identical_words_as_complete():
    result = compare_text_coverage("Executive Interview", "ExecutiveInterview")

    assert result["score"] == 1.0


def test_compare_text_coverage_counts_missing_full_width_ascii_after_normalization():
    result = compare_text_coverage("ＡＢＣ１２３", "")

    assert result["score"] == 0.0
    assert result["missing_ratio"] == 1.0
    assert result["missing_text"]
