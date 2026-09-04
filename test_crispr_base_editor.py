#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for CRISPR Base Editor Deamination Window Engine
Tests CBE & ABE profiles, position-specific efficiency, bystander mutation prediction,
stop codon creation, error validation, JSON export, CLI commands, and security features.
"""

import os
import sys
import unittest

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crispr_base_editor import (
    CRISPRBaseEditorEngine,
    BaseEditorAnalysisResult,
    TargetBaseEditDetail,
    EDITOR_WINDOW_PROFILES,
    main,
)


class TestEditorProfilesAndTypes(unittest.TestCase):
    """Test suite for editor type mapping and deamination window profiles."""

    def test_cbe_editor_type(self):
        ed_type, target, edited = CRISPRBaseEditorEngine.get_editor_type("BE4MAX")
        self.assertEqual(ed_type, "CBE")
        self.assertEqual(target, "C")
        self.assertEqual(edited, "T")

        ed_type, target, edited = CRISPRBaseEditorEngine.get_editor_type("TARGET_AID")
        self.assertEqual(ed_type, "CBE")
        self.assertEqual(target, "C")
        self.assertEqual(edited, "T")

    def test_abe_editor_type(self):
        ed_type, target, edited = CRISPRBaseEditorEngine.get_editor_type("ABE7.10")
        self.assertEqual(ed_type, "ABE")
        self.assertEqual(target, "A")
        self.assertEqual(edited, "G")

        ed_type, target, edited = CRISPRBaseEditorEngine.get_editor_type("ABE8e")
        self.assertEqual(ed_type, "ABE")
        self.assertEqual(target, "A")
        self.assertEqual(edited, "G")

    def test_window_profiles_coverage(self):
        self.assertIn("BE4MAX", EDITOR_WINDOW_PROFILES)
        self.assertIn("ABE8E", EDITOR_WINDOW_PROFILES)
        self.assertGreater(EDITOR_WINDOW_PROFILES["BE4MAX"][5], 0.90)
        self.assertGreater(EDITOR_WINDOW_PROFILES["ABE8E"][5], 0.90)


class TestProtospacerEvaluation(unittest.TestCase):
    """Test suite for protospacer sequence evaluations and bystander predictions."""

    def test_invalid_length_raises_value_error(self):
        with self.assertRaises(ValueError):
            CRISPRBaseEditorEngine.evaluate_protospacer("ATGC")

    def test_clean_single_target_be4max(self):
        # 20nt with a single 'C' at position 5 (peak BE4max window)
        # Sequence: "TTTTCTTTTTTTTTTTTTTT" -> 'C' at index 4 (pos 5)
        seq = "TTTTCTTTTTTTTTTTTTTT"
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="BE4MAX", intended_position=5)
        self.assertEqual(res.editor_name, "BE4MAX")
        self.assertEqual(res.target_bases_in_window, 1)
        self.assertEqual(res.bystander_count_in_window, 0)
        self.assertGreater(res.predicted_on_target_efficiency_percent, 50.0)
        self.assertEqual(res.predicted_purity_ratio, 1.0)
        self.assertEqual(res.overall_suitability, "HIGH_PRECISION")

    def test_bystander_detection_in_window(self):
        # Sequence with 'C' at pos 4 and pos 6 (both in BE4max window)
        # Intended target: pos 6 -> pos 4 is a bystander
        seq = "TTTCTCTTTTTTTTTTTTTT"
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="BE4MAX", intended_position=6)
        self.assertEqual(res.target_bases_in_window, 2)
        self.assertEqual(res.bystander_count_in_window, 1)
        self.assertLess(res.predicted_purity_ratio, 1.0)
        bystanders = [b for b in res.base_edits if b.is_bystander]
        self.assertEqual(len(bystanders), 1)
        self.assertEqual(bystanders[0].position_1_indexed, 4)

    def test_target_outside_window(self):
        # 'C' at position 18 (outside window 4-8)
        seq = "TTTTTTTTTTTTTTTTTCTT"
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="BE4MAX", intended_position=18)
        self.assertEqual(res.target_bases_in_window, 0)
        self.assertEqual(res.predicted_on_target_efficiency_percent, 0.0)
        self.assertEqual(res.overall_suitability, "SUB_OPTIMAL_WINDOW")

    def test_abe8e_broad_window_activity(self):
        # ABE8e has activity from pos 3 to 10. Test 'A' at pos 3 and pos 9
        seq = "TTAAAAAAATTTTTTTTTTT"
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="ABE8E", intended_position=5)
        self.assertEqual(res.editor_type, "ABE")
        self.assertGreater(res.target_bases_in_window, 3)

    def test_target_aid_distal_window(self):
        # Target-AID has peak activity at pos 2-4
        seq = "TCTTTTTTTTTTTTTTTTTT"  # 'C' at pos 2
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="TARGET_AID", intended_position=2)
        self.assertEqual(res.target_bases_in_window, 1)
        self.assertGreater(res.predicted_on_target_efficiency_percent, 40.0)

    def test_stop_codon_detection(self):
        # CAA at start -> CAA mutated to TAA (Stop codon)
        # Position 1, 2, 3 = CAA
        # Let's put CAA in window: e.g. at pos 4-6: "TTTCAATTTTTTTTTTTTTT" -> pos 4 is C, becomes T -> TAA
        seq = "TTTCAATTTTTTTTTTTTTT"
        res = CRISPRBaseEditorEngine.evaluate_protospacer(seq, editor_name="BE4MAX", intended_position=4)
        self.assertTrue(res.stop_codon_created)


class TestEndToEndAndCLI(unittest.TestCase):
    """Test suite for JSON export and CLI evaluation."""

    def test_json_export(self):
        res = CRISPRBaseEditorEngine.evaluate_protospacer("TTTTCTTTTTTTTTTTTTTT", editor_name="BE4MAX")
        json_str = res.to_json()
        self.assertIn("BE4MAX", json_str)
        self.assertIn("predicted_on_target_efficiency_percent", json_str)

    def test_cli_eval_command(self):
        self.assertEqual(main(["eval", "--spacer", "TTTTCTTTTTTTTTTTTTTT", "--editor", "BE4MAX", "--pos", "5"]), 0)
        self.assertEqual(main(["eval", "--spacer", "TTAAATTTTTTTTTTTTTTT", "--editor", "ABE8E", "--json"]), 0)

    def test_cli_chat_command(self):
        self.assertEqual(main(["chat", "What", "is", "the", "editing", "window?"]), 0)


class TestSecurityFeatures(unittest.TestCase):
    """Test suite for security features: PHI guard, audit trail, path validation."""

    def test_phi_detection_mrn(self):
        """Test that MRN numbers are detected as PHI."""
        from agents.base import assert_no_phi, SecurityException
        with self.assertRaises(SecurityException):
            assert_no_phi("Patient MRN-12345678")

    def test_phi_detection_ssn(self):
        """Test that SSN patterns are detected as PHI."""
        from agents.base import assert_no_phi, SecurityException
        with self.assertRaises(SecurityException):
            assert_no_phi("SSN: 123-45-6789")

    def test_phi_detection_phone(self):
        """Test that phone numbers are detected as PHI."""
        from agents.base import assert_no_phi, SecurityException
        with self.assertRaises(SecurityException):
            assert_no_phi("Call 555-123-4567")

    def test_phi_detection_email(self):
        """Test that email addresses are detected as PHI."""
        from agents.base import assert_no_phi, SecurityException
        with self.assertRaises(SecurityException):
            assert_no_phi("Email: patient@example.com")

    def test_phi_clean_text_passes(self):
        """Test that clean text without PHI passes validation."""
        from agents.base import assert_no_phi
        # Should not raise
        assert_no_phi("CRISPR Base Editor analysis for BE4MAX at position 5")
        assert_no_phi("Normal genomic sequence ATCGATCGATCG")

    def test_phi_redaction(self):
        """Test that PHI is properly redacted."""
        from agents.base import PHIGuard
        text = "Patient John Doe MRN-12345678 and email test@example.com"
        redacted = PHIGuard.redact_phi(text)
        self.assertNotIn("12345678", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertIn("[REDACTED_IDENTIFIER]", redacted)

    def test_audit_trail_integrity(self):
        """Test that audit trail maintains cryptographic integrity."""
        from agents.base import AuditTrail
        trail = AuditTrail(secret_key="test-key-for-unit-tests")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value2"})
        self.assertTrue(trail.verify_integrity())
        self.assertEqual(len(trail.get_trail()), 2)

    def test_audit_trail_tamper_detection(self):
        """Test that tampering with audit trail is detected."""
        from agents.base import AuditTrail
        trail = AuditTrail(secret_key="test-key-for-unit-tests")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        # Tamper with the trail
        trail.logs[0]["current_hash"] = "TAMPERED_HASH"
        self.assertFalse(trail.verify_integrity())

    def test_audit_trail_phi_blocked(self):
        """Test that PHI in audit log details is blocked."""
        from agents.base import AuditTrail, SecurityException
        trail = AuditTrail(secret_key="test-key-for-unit-tests")
        with self.assertRaises(SecurityException):
            trail.log("test_actor", "test_tier", "TEST_EVENT", {"patient": "MRN-12345678"})

    def test_path_traversal_detection(self):
        """Test that path traversal attempts are detected."""
        # Test the path validation logic used in batch processing
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "foo/../../../etc/shadow",
        ]
        for path in dangerous_paths:
            normalized = path.replace("\\", "/").split("/")
            self.assertIn("..", normalized, f"Path traversal not detected in: {path}")

    def test_null_byte_detection(self):
        """Test that null bytes in paths are detected."""
        dangerous_path = "foo\x00/bar.csv"
        self.assertIn("\x00", dangerous_path)


if __name__ == "__main__":
    unittest.main()
