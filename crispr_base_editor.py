#!/usr/bin/env python3
"""
CRISPR Base Editor Deamination Window & Bystander Mutation Prediction Engine
-----------------------------------------------------------------------------
Simulates Cytosine Base Editors (CBE: BE3, BE4max, Target-AID) and Adenine Base Editors
(ABE: ABE7.10, ABE8e, ABE9) activity windows, calculates position-dependent deamination
efficiencies, predicts bystander edit probabilities, and models codon alteration consequences.

Domain: Synthetic Biology / Genome Engineering / Molecular Therapeutics
Reference: Komor et al. Nature 2016; Gaudelli et al. Nature 2017; Richter et al. Nat Biotech 2020
"""

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple


GENETIC_CODE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Deamination profiles: {position: relative_efficiency (0.0 to 1.0)}
EDITOR_WINDOW_PROFILES = {
    "BE4MAX": {  # Canonical C->T, window 4-8, peak at 5-6
        3: 0.15, 4: 0.65, 5: 0.95, 6: 0.90, 7: 0.70, 8: 0.35, 9: 0.10
    },
    "BE3": {  # Canonical C->T, window 4-8
        4: 0.50, 5: 0.85, 6: 0.80, 7: 0.55, 8: 0.25
    },
    "TARGET_AID": {  # PmCDA1 C->T, window 2-8, peak 2-4
        2: 0.75, 3: 0.90, 4: 0.85, 5: 0.60, 6: 0.40, 7: 0.25, 8: 0.15
    },
    "ABE7.10": {  # Canonical A->G, window 4-7, peak 5-6
        4: 0.45, 5: 0.85, 6: 0.80, 7: 0.50
    },
    "ABE8E": {  # Evolved TadA8e A->G, broad high-activity window 3-10
        3: 0.60, 4: 0.88, 5: 0.98, 6: 0.96, 7: 0.92, 8: 0.80, 9: 0.55, 10: 0.30
    }
}


@dataclass
class TargetBaseEditDetail:
    """Individual editable base within protospacer."""
    position_1_indexed: int
    original_base: str
    edited_base: str
    is_intended_target: bool
    is_in_deamination_window: bool
    predicted_efficiency_percent: float
    is_bystander: bool
    edit_classification: str  # 'INTENDED_TARGET', 'HIGH_RISK_BYSTANDER', 'MINOR_BYSTANDER', 'OUTSIDE_WINDOW'


@dataclass
class BaseEditorAnalysisResult:
    """Complete CRISPR base editor protospacer evaluation."""
    editor_name: str
    editor_type: str  # 'CBE' or 'ABE'
    protospacer_sequence: str  # 20 nt (5' to 3')
    pam_sequence: str  # 3 nt (e.g. NGG)
    intended_position: Optional[int]
    total_target_bases: int
    target_bases_in_window: int
    bystander_count_in_window: int
    predicted_on_target_efficiency_percent: float
    predicted_purity_ratio: float  # on_target / (on_target + sum_bystanders)
    base_edits: List[TargetBaseEditDetail]
    stop_codon_created: bool
    edited_sequence_preview: str
    overall_suitability: str  # 'HIGH_PRECISION', 'MODERATE_BYSTANDER_RISK', 'POOR_OFF_TARGET_RISK', 'SUB_OPTIMAL_WINDOW'
    clinical_recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class CRISPRBaseEditorEngine:
    """Engine for simulating base editor deamination windows and bystander edits."""

    @staticmethod
    def get_editor_type(editor_name: str) -> Tuple[str, str, str]:
        """Returns (editor_type, target_base, edited_base)."""
        name = editor_name.upper().replace("-", "_")
        if "ABE" in name:
            return "ABE", "A", "G"
        else:
            return "CBE", "C", "T"

    @classmethod
    def evaluate_protospacer(
        cls,
        protospacer_20nt: str,
        pam_3nt: str = "NGG",
        editor_name: str = "BE4MAX",
        intended_position: Optional[int] = None,
        base_efficiency_scaling: float = 65.0,  # Peak edit efficiency %
    ) -> BaseEditorAnalysisResult:
        """
        Analyze a 20nt protospacer sequence for a given base editor.
        Protospacer positions are 1 to 20 from 5' to 3' (PAM at 21-23).
        """
        seq = protospacer_20nt.upper().strip().replace("U", "T")
        if len(seq) != 20:
            raise ValueError(f"Protospacer must be exactly 20 nucleotides in length (received {len(seq)}).")

        editor_key = editor_name.upper().replace("-", "_")
        profile = EDITOR_WINDOW_PROFILES.get(editor_key, EDITOR_WINDOW_PROFILES["BE4MAX"])
        ed_type, target_base, edited_base = cls.get_editor_type(editor_name)

        edits: List[TargetBaseEditDetail] = []
        target_indices = [i for i, b in enumerate(seq) if b == target_base]

        on_target_eff = 0.0
        bystander_effs = []
        bystander_in_window_count = 0
        target_in_window_count = 0

        # Build modified preview sequence (replacing high-probability bases in window)
        preview_list = list(seq)

        for idx in target_indices:
            pos = idx + 1  # 1-indexed
            rel_eff = profile.get(pos, 0.0)
            in_window = rel_eff > 0.0
            eff_pct = round(rel_eff * base_efficiency_scaling, 1)

            is_intended = (pos == intended_position) if intended_position else (in_window and on_target_eff == 0.0)

            if in_window:
                target_in_window_count += 1
                if is_intended:
                    on_target_eff = eff_pct
                    classification = "INTENDED_TARGET"
                    preview_list[idx] = edited_base.lower()
                else:
                    bystander_in_window_count += 1
                    bystander_effs.append(eff_pct)
                    classification = "HIGH_RISK_BYSTANDER" if eff_pct > 30.0 else "MINOR_BYSTANDER"
                    if eff_pct >= 25.0:
                        preview_list[idx] = edited_base.lower()
            else:
                classification = "OUTSIDE_WINDOW"

            edits.append(TargetBaseEditDetail(
                position_1_indexed=pos,
                original_base=target_base,
                edited_base=edited_base,
                is_intended_target=is_intended,
                is_in_deamination_window=in_window,
                predicted_efficiency_percent=eff_pct,
                is_bystander=(in_window and not is_intended),
                edit_classification=classification,
            ))

        total_bystander_eff = sum(bystander_effs)
        total_active_eff = on_target_eff + total_bystander_eff

        if total_active_eff > 0:
            purity = round(on_target_eff / total_active_eff, 3)
        else:
            purity = 1.0 if on_target_eff > 0 else 0.0

        # Check for Stop Codon introduction (TAG, TAA, TGA)
        stop_created = False
        edited_seq_str = "".join(preview_list).upper()
        for i in range(0, len(edited_seq_str) - 2, 3):
            codon = edited_seq_str[i:i+3]
            if codon in ["TAG", "TAA", "TGA"]:
                stop_created = True
                break

        # Overall suitability classification
        if on_target_eff >= 40.0 and bystander_in_window_count == 0:
            suitability = "HIGH_PRECISION"
            rec = "Optimal clean single-base edit with zero active bystanders in deamination window."
        elif on_target_eff >= 30.0 and bystander_in_window_count > 0 and purity >= 0.70:
            suitability = "MODERATE_BYSTANDER_RISK"
            rec = "Good target deamination; minor bystander activity present. Consider engineered narrow-window editor (e.g. eA3A or ABE8e-V106W)."
        elif on_target_eff > 0.0 and purity < 0.70:
            suitability = "POOR_OFF_TARGET_RISK"
            rec = "Significant bystander editing exceeds 30% product ratio. Shift gRNA spacer or switch to Cas12a/prime editing."
        else:
            suitability = "SUB_OPTIMAL_WINDOW"
            rec = "Target base is outside the optimal deamination window. Redesign spacer with alternative PAM position."

        return BaseEditorAnalysisResult(
            editor_name=editor_name,
            editor_type=ed_type,
            protospacer_sequence=seq,
            pam_sequence=pam_3nt.upper(),
            intended_position=intended_position,
            total_target_bases=len(target_indices),
            target_bases_in_window=target_in_window_count,
            bystander_count_in_window=bystander_in_window_count,
            predicted_on_target_efficiency_percent=round(on_target_eff, 1),
            predicted_purity_ratio=purity,
            base_edits=edits,
            stop_codon_created=stop_created,
            edited_sequence_preview="".join(preview_list),
            overall_suitability=suitability,
            clinical_recommendation=rec,
        )


# ==============================================================================
# CLI & BATCH PROCESSING
# ==============================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="crispr-base-editor-window-agent",
        description="CRISPR Base Editor Deamination Window & Bystander Mutation Predictor"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Eval
    p_eval = subparsers.add_parser("eval", help="Evaluate 20nt protospacer sequence")
    p_eval.add_argument("--spacer", "-s", required=True, help="20nt protospacer sequence (5' to 3')")
    p_eval.add_argument("--pam", default="NGG", help="PAM motif (default: NGG)")
    p_eval.add_argument("--editor", "-e", default="BE4MAX", choices=["BE4MAX", "BE3", "TARGET_AID", "ABE7.10", "ABE8E"])
    p_eval.add_argument("--pos", type=int, default=None, help="Intended target position (1-20)")
    p_eval.add_argument("--json", action="store_true", help="Output JSON format")

    # Chat
    p_chat = subparsers.add_parser("chat", help="Ask CRISPR base editing questions")
    p_chat.add_argument("query", nargs="+")

    # Batch
    p_batch = subparsers.add_parser("batch", help="Batch process CSV of gRNAs")
    p_batch.add_argument("-i", "--input", required=True)
    p_batch.add_argument("-o", "--output", default="base_editor_results.csv")

    args = parser.parse_args(argv)

    if args.command == "eval":
        res = CRISPRBaseEditorEngine.evaluate_protospacer(
            protospacer_20nt=args.spacer,
            pam_3nt=args.pam,
            editor_name=args.editor,
            intended_position=args.pos,
        )
        if args.json:
            print(res.to_json())
        else:
            print("=" * 80)
            print(f"  CRISPR BASE EDITOR WINDOW ANALYSIS — [{res.editor_name} ({res.editor_type})]")
            print(f"  Suitability: [{res.overall_suitability}] | Purity Ratio: {res.predicted_purity_ratio:.2f}")
            print("=" * 80)
            print(f"  Protospacer (5'->3'):  {res.protospacer_sequence} - PAM: {res.pam_sequence}")
            print(f"  Edited Preview:        {res.edited_sequence_preview}")
            print(f"  Target Bases in Window: {res.target_bases_in_window} (Bystanders: {res.bystander_count_in_window})")
            print(f"  On-Target Efficiency:   {res.predicted_on_target_efficiency_percent:.1f}%")
            print(f"  Stop Codon Created:     {res.stop_codon_created}")
            print("-" * 80)
            print("  Base Position Breakdown:")
            for b in res.base_edits:
                status_sym = "[TARGET]" if b.is_intended_target else ("[BYSTANDER]" if b.is_bystander else "[OUTSIDE]")
                print(f"    * Pos {b.position_1_indexed:02d}: {b.original_base}->{b.edited_base} | Eff: {b.predicted_efficiency_percent:4.1f}% | {status_sym} ({b.edit_classification})")
            print("-" * 80)
            print(f"  Recommendation: {res.clinical_recommendation}")
            print("=" * 80)
        return 0

    elif args.command == "chat":
        q = " ".join(args.query).lower()
        if "window" in q:
            print("BE4max editing window: positions 4-8 (peak 5-6). ABE8e window: positions 3-10 (peak 5-7).")
        elif "bystander" in q:
            print("Bystander edits occur when additional target bases (C for CBE, A for ABE) reside within the deamination window.")
        else:
            print("CRISPR Base Editor Engine active. Supports BE3, BE4max, Target-AID, ABE7.10, and ABE8e.")
        return 0

    elif args.command == "batch":
        # Validate input/output paths for security
        for path in [args.input, args.output]:
            if "\x00" in path:
                print(f"Error: Invalid path contains null bytes", file=sys.stderr)
                return 1
            if ".." in path.replace("\\", "/").split("/"):
                print(f"Error: Path traversal detected in '{path}'", file=sys.stderr)
                return 1

        with open(args.input, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        out_rows = []
        for r in rows:
            seq = r.get("spacer", r.get("protospacer", r.get("sequence", "ATGCGATCGATCGATCGATC")))
            ed = r.get("editor", "BE4MAX")
            pam = r.get("pam", "NGG")
            pos = int(r["pos"]) if "pos" in r and r["pos"] else None

            res_obj = CRISPRBaseEditorEngine.evaluate_protospacer(seq, pam, ed, pos)
            out_rows.append({
                **r,
                "editor": res_obj.editor_name,
                "on_target_efficiency": res_obj.predicted_on_target_efficiency_percent,
                "purity_ratio": res_obj.predicted_purity_ratio,
                "bystander_count": res_obj.bystander_count_in_window,
                "stop_codon_created": res_obj.stop_codon_created,
                "overall_suitability": res_obj.overall_suitability,
            })
        if out_rows:
            with open(args.output, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
                writer.writeheader()
                writer.writerows(out_rows)
        print(f"Batch processed {len(out_rows)} rows -> {args.output}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
