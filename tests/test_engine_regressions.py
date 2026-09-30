import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import HTTPException

from api import AnalyzeRequest, analyze
from crispr_base_editor import CRISPRBaseEditorEngine, main


def test_unknown_editor_is_rejected():
    with pytest.raises(ValueError, match="Unsupported editor"):
        CRISPRBaseEditorEngine.evaluate_protospacer("TTTTCTTTTTTTTTTTTTTT", editor_name="ABE9")


def test_invalid_protospacer_symbol_is_rejected():
    with pytest.raises(ValueError, match="unsupported nucleotide"):
        CRISPRBaseEditorEngine.evaluate_protospacer("TTTTNTTTTTTTTTTTTTTT")


def test_intended_position_must_match_editable_base():
    with pytest.raises(ValueError, match="edits 'C'"):
        CRISPRBaseEditorEngine.evaluate_protospacer(
            "TTTTCTTTTTTTTTTTTTTT", editor_name="BE4MAX", intended_position=4
        )


def test_automatic_target_uses_highest_activity_position():
    result = CRISPRBaseEditorEngine.evaluate_protospacer(
        "TTTCCCTTTTTTTTTTTTTT", editor_name="BE4MAX"
    )
    assert result.intended_position == 5


def test_preexisting_stop_codon_is_not_reported_as_created():
    result = CRISPRBaseEditorEngine.evaluate_protospacer(
        "TAATCTTTTTTTTTTTTTTT", editor_name="BE4MAX", intended_position=5
    )
    assert result.stop_codon_created is False


def test_batch_rejects_missing_sequence_column_value(tmp_path: Path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_path.write_text("editor,pam\nBE4MAX,NGG\n", encoding="utf-8")
    assert main(["batch", "-i", str(input_path), "-o", str(output_path)]) == 2
    assert not output_path.exists()


def test_batch_writes_scientific_results(tmp_path: Path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    input_path.write_text(
        "spacer,pam,editor,pos\nTTTTCTTTTTTTTTTTTTTT,NGG,BE4MAX,5\n",
        encoding="utf-8",
    )
    assert main(["batch", "-i", str(input_path), "-o", str(output_path)]) == 0
    with output_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["editor"] == "BE4MAX"
    assert rows[0]["overall_suitability"] == "HIGH_PRECISION"


def test_api_uses_sequence_engine():
    data = analyze(
        AnalyzeRequest(
            spacer="TTTTCTTTTTTTTTTTTTTT",
            pam="NGG",
            editor="BE4MAX",
            intended_position=5,
        )
    )
    assert data["editor_name"] == "BE4MAX"
    assert data["intended_position"] == 5
    assert data["overall_suitability"] == "HIGH_PRECISION"


def test_api_rejects_invalid_sequence():
    with pytest.raises(HTTPException) as exc_info:
        analyze(AnalyzeRequest(spacer="TTTTNTTTTTTTTTTTTTTT", editor="BE4MAX"))
    assert exc_info.value.status_code == 422
    assert "unsupported nucleotide" in exc_info.value.detail
