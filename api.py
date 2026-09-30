"""FastAPI interface for the CRISPR base-editor window heuristic."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from crispr_base_editor import CRISPRBaseEditorEngine, EDITOR_WINDOW_PROFILES, SUPPORTED_EDITORS


app = FastAPI(
    title="CRISPR Base Editor Window API",
    description=(
        "Research-use API for fixed, heuristic CBE/ABE activity-window scoring and "
        "same-locus bystander identification. Scores are not assay-calibrated probabilities."
    ),
    version="2.1.0",
)


class AnalyzeRequest(BaseModel):
    spacer: str = Field(..., description="20-nt protospacer sequence, 5' to 3'")
    pam: str = Field(default="NGG", description="3-symbol IUPAC PAM annotation")
    editor: str = Field(default="BE4MAX", description="Supported base-editor name")
    intended_position: Optional[int] = Field(default=None, ge=1, le=20)
    base_efficiency_scaling: float = Field(default=65.0, ge=0.0, le=100.0)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "crispr-base-editor-window-agent",
        "version": "2.1.0",
        "supported_editors": list(SUPPORTED_EDITORS),
    }


@app.get("/api/profiles")
def profiles():
    return {
        "note": "Relative activity weights only; not calibrated probabilities.",
        "profiles": EDITOR_WINDOW_PROFILES,
    }


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    try:
        result = CRISPRBaseEditorEngine.evaluate_protospacer(
            protospacer_20nt=request.spacer,
            pam_3nt=request.pam,
            editor_name=request.editor,
            intended_position=request.intended_position,
            base_efficiency_scaling=request.base_efficiency_scaling,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result.to_dict()
