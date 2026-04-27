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
