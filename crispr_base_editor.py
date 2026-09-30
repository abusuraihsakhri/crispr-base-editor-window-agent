#!/usr/bin/env python3
"""Research-use CRISPR base-editor activity-window and bystander heuristic.

Profiles below are fixed relative weights, not assay-calibrated probabilities.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

STOP_CODONS = {"TAG", "TAA", "TGA"}
IUPAC_DNA = set("ACGTRYSWKMBDHVN")
EDITOR_WINDOW_PROFILES: Dict[str, Dict[int, float]] = {
    "BE4MAX": {3: .15, 4: .65, 5: .95, 6: .90, 7: .70, 8: .35, 9: .10},
    "BE3": {4: .50, 5: .85, 6: .80, 7: .55, 8: .25},
    "TARGET_AID": {2: .75, 3: .90, 4: .85, 5: .60, 6: .40, 7: .25, 8: .15},
    "ABE7.10": {4: .45, 5: .85, 6: .80, 7: .50},
    "ABE8E": {3: .60, 4: .88, 5: .98, 6: .96, 7: .92, 8: .80, 9: .55, 10: .30},
}
EDITOR_PROPERTIES: Dict[str, Tuple[str, str, str]] = {
    "BE4MAX": ("CBE", "C", "T"), "BE3": ("CBE", "C", "T"),
    "TARGET_AID": ("CBE", "C", "T"), "ABE7.10": ("ABE", "A", "G"),
    "ABE8E": ("ABE", "A", "G"),
}
EDITOR_ALIASES = {
    "BE4_MAX": "BE4MAX", "TARGETAID": "TARGET_AID", "ABE7_10": "ABE7.10",
    "ABE8_E": "ABE8E",
}
SUPPORTED_EDITORS = tuple(EDITOR_PROPERTIES)


@dataclass
class TargetBaseEditDetail:
    position_1_indexed: int
    original_base: str
    edited_base: str
    is_intended_target: bool
    is_in_deamination_window: bool
    predicted_efficiency_percent: float
    is_bystander: bool
    edit_classification: str


@dataclass
class BaseEditorAnalysisResult:
    editor_name: str
    editor_type: str
    protospacer_sequence: str
    pam_sequence: str
    intended_position: Optional[int]
    total_target_bases: int
    target_bases_in_window: int
    bystander_count_in_window: int
    predicted_on_target_efficiency_percent: float
    predicted_purity_ratio: float
    base_edits: List[TargetBaseEditDetail]
    stop_codon_created: bool
    edited_sequence_preview: str
    overall_suitability: str
    clinical_recommendation: str  # retained for backwards-compatible result schema

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class CRISPRBaseEditorEngine:
    @staticmethod
    def normalize_editor_name(name: str) -> str:
        key = str(name).strip().upper().replace("-", "_")
        key = EDITOR_ALIASES.get(key, key)
        if key not in EDITOR_PROPERTIES:
            raise ValueError(f"Unsupported editor '{name}'. Supported editors: {', '.join(SUPPORTED_EDITORS)}.")
        return key

    @classmethod
    def get_editor_type(cls, name: str) -> Tuple[str, str, str]:
        return EDITOR_PROPERTIES[cls.normalize_editor_name(name)]

    @staticmethod
    def _protospacer(value: str) -> str:
        seq = str(value).upper().strip().replace("U", "T")
        if len(seq) != 20:
            raise ValueError(f"Protospacer must be exactly 20 nucleotides in length (received {len(seq)}).")
        invalid = sorted(set(seq) - set("ACGT"))
        if invalid:
            raise ValueError(f"Protospacer contains unsupported nucleotide(s): {', '.join(invalid)}. Use A/C/G/T only.")
        return seq

    @staticmethod
    def _pam(value: str) -> str:
        pam = str(value).upper().strip().replace("U", "T")
        if len(pam) != 3:
            raise ValueError(f"PAM must be exactly 3 IUPAC nucleotide symbols (received {len(pam)}).")
        invalid = sorted(set(pam) - IUPAC_DNA)
        if invalid:
            raise ValueError(f"PAM contains unsupported IUPAC symbol(s): {', '.join(invalid)}.")
        return pam

    @classmethod
    def evaluate_protospacer(
        cls, protospacer_20nt: str, pam_3nt: str = "NGG", editor_name: str = "BE4MAX",
        intended_position: Optional[int] = None, base_efficiency_scaling: float = 65.0,
    ) -> BaseEditorAnalysisResult:
        """Analyze a 20-nt protospacer; positions are 1-indexed from its 5' end."""
        seq, pam = cls._protospacer(protospacer_20nt), cls._pam(pam_3nt)
        editor = cls.normalize_editor_name(editor_name)
        editor_type, target_base, edited_base = EDITOR_PROPERTIES[editor]
        profile = EDITOR_WINDOW_PROFILES[editor]
        scale = float(base_efficiency_scaling)
        if not math.isfinite(scale) or not 0 <= scale <= 100:
            raise ValueError("base_efficiency_scaling must be a finite percentage between 0 and 100.")
        if intended_position is not None:
            if isinstance(intended_position, bool) or not isinstance(intended_position, int) or not 1 <= intended_position <= 20:
                raise ValueError("intended_position must be an integer from 1 to 20.")
            if seq[intended_position - 1] != target_base:
                raise ValueError(f"Position {intended_position} is '{seq[intended_position - 1]}', but {editor} edits '{target_base}'.")

        target_indices = [i for i, base in enumerate(seq) if base == target_base]
        active_positions = [i + 1 for i in target_indices if profile.get(i + 1, 0) > 0]
        intended = intended_position
        if intended is None and active_positions:
            intended = max(active_positions, key=profile.get)

        edits: List[TargetBaseEditDetail] = []
        preview = list(seq)
        on_target = 0.0
        bystander_scores: List[float] = []
        for i in target_indices:
            pos = i + 1
            score = round(profile.get(pos, 0) * scale, 1)
            in_window, is_target = score > 0, pos == intended
            is_bystander = in_window and not is_target
            if is_target:
                on_target = score
                preview[i] = edited_base.lower()
            elif is_bystander:
                bystander_scores.append(score)
                if score >= 25:
                    preview[i] = edited_base.lower()
            classification = (
                "INTENDED_TARGET" if is_target else
                ("HIGH_RISK_BYSTANDER" if is_bystander and score > 30 else
                 ("MINOR_BYSTANDER" if is_bystander else "OUTSIDE_WINDOW"))
            )
            edits.append(TargetBaseEditDetail(pos, target_base, edited_base, is_target, in_window, score, is_bystander, classification))

        total = on_target + sum(bystander_scores)
        purity = round(on_target / total, 3) if total else 0.0
        edited_upper = "".join(preview).upper()
        stop_created = any(
            seq[i:i + 3] not in STOP_CODONS and edited_upper[i:i + 3] in STOP_CODONS
            for i in range(0, len(seq) - 2, 3)
        )
        bystanders = len(bystander_scores)
        if on_target >= 40 and bystanders == 0:
            suitability = "HIGH_PRECISION"
            interpretation = "Heuristic profile favors a single editable target with no modeled in-window bystanders."
        elif on_target >= 30 and bystanders and purity >= .70:
            suitability = "MODERATE_BYSTANDER_RISK"
            interpretation = "Target activity is favorable, but modeled in-window bystander editing is present."
        elif on_target > 0 and purity < .70:
            suitability = "HIGH_BYSTANDER_RISK"
            interpretation = "Modeled bystander contribution is large relative to the intended edit; consider an alternative guide or narrower-window editor."
        else:
            suitability = "SUB_OPTIMAL_WINDOW"
            interpretation = "The intended target has little or no activity in the selected heuristic window; consider an alternative guide/editor configuration."

        return BaseEditorAnalysisResult(
            editor, editor_type, seq, pam, intended, len(target_indices), len(active_positions), bystanders,
            round(on_target, 1), purity, edits, stop_created, "".join(preview), suitability, interpretation,
        )


def _safe_csv_path(path: str) -> str:
    if "\x00" in path:
        raise ValueError("Invalid path: contains a null byte.")
    if ".." in path.replace("\\", "/").split("/"):
        raise ValueError(f"Path traversal is not allowed: '{path}'.")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="crispr-base-editor-window-agent", description="CRISPR base-editor activity-window and bystander heuristic")
    subs = parser.add_subparsers(dest="command", required=True)
    ev = subs.add_parser("eval", help="Evaluate a 20-nt protospacer")
    ev.add_argument("--spacer", "-s", required=True)
    ev.add_argument("--pam", default="NGG")
    ev.add_argument("--editor", "-e", default="BE4MAX", choices=list(SUPPORTED_EDITORS))
    ev.add_argument("--pos", type=int, default=None)
    ev.add_argument("--scale", type=float, default=65.0)
    ev.add_argument("--json", action="store_true")
    chat = subs.add_parser("chat", help="Show concise editor/window information")
    chat.add_argument("query", nargs="+")
    batch = subs.add_parser("batch", help="Batch process a CSV of guide sequences")
    batch.add_argument("-i", "--input", required=True)
    batch.add_argument("-o", "--output", default="base_editor_results.csv")
    args = parser.parse_args(argv)

    if args.command == "eval":
        try:
            result = CRISPRBaseEditorEngine.evaluate_protospacer(args.spacer, args.pam, args.editor, args.pos, args.scale)
        except ValueError as exc:
            parser.error(str(exc))
        if args.json:
            print(result.to_json())
        else:
            print(f"CRISPR Base Editor Window Heuristic — {result.editor_name} ({result.editor_type})")
            print(f"Suitability: {result.overall_suitability}; edit-share ratio: {result.predicted_purity_ratio:.3f}")
            print(f"Protospacer: {result.protospacer_sequence}  PAM: {result.pam_sequence}")
            print(f"Edited preview: {result.edited_sequence_preview}; intended position: {result.intended_position}")
            print(f"Target score: {result.predicted_on_target_efficiency_percent:.1f}%; bystanders: {result.bystander_count_in_window}; new stop: {result.stop_codon_created}")
            for item in result.base_edits:
                role = "TARGET" if item.is_intended_target else ("BYSTANDER" if item.is_bystander else "OUTSIDE")
                print(f"Pos {item.position_1_indexed:02d}: {item.original_base}->{item.edited_base} | {item.predicted_efficiency_percent:4.1f}% | {role}")
            print(f"Interpretation: {result.clinical_recommendation}")
            print("Note: fixed activity profiles are heuristic, not assay-calibrated probabilities.")
        return 0

    if args.command == "chat":
        query = " ".join(args.query).lower()
        if "window" in query:
            print("BE4MAX: positions 3-9; ABE8E: positions 3-10. Profiles are heuristic relative-activity weights.")
        elif "bystander" in query:
            print("A bystander is another editable C (CBE) or A (ABE) in the modeled window at the same locus; it is distinct from genomic off-target editing.")
        else:
            print("Supported editors: " + ", ".join(SUPPORTED_EDITORS) + ".")
        return 0

    try:
        in_path, out_path = _safe_csv_path(args.input), _safe_csv_path(args.output)
        with open(in_path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields, rows = list(reader.fieldnames or []), list(reader)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    extras = ["editor", "intended_position", "on_target_efficiency", "purity_ratio", "bystander_count", "stop_codon_created", "overall_suitability"]
    output_fields, output_rows = list(dict.fromkeys(fields + extras)), []
    for row_number, row in enumerate(rows, 2):
        sequence = row.get("spacer") or row.get("protospacer") or row.get("sequence")
        if not sequence:
            print(f"Error in CSV row {row_number}: missing spacer/protospacer/sequence value.", file=sys.stderr)
            return 2
        try:
            pos = int(row["pos"]) if row.get("pos") else None
            result = CRISPRBaseEditorEngine.evaluate_protospacer(sequence, row.get("pam") or "NGG", row.get("editor") or "BE4MAX", pos)
        except ValueError as exc:
            print(f"Error in CSV row {row_number}: {exc}", file=sys.stderr)
            return 2
        output_rows.append({**row, "editor": result.editor_name, "intended_position": result.intended_position,
                            "on_target_efficiency": result.predicted_on_target_efficiency_percent,
                            "purity_ratio": result.predicted_purity_ratio, "bystander_count": result.bystander_count_in_window,
                            "stop_codon_created": result.stop_codon_created, "overall_suitability": result.overall_suitability})
    try:
        with open(out_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=output_fields)
            writer.writeheader(); writer.writerows(output_rows)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr); return 2
    print(f"Batch processed {len(output_rows)} row(s) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
