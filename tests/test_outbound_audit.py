import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("audit", Path(__file__).resolve().parents[1] / "scripts/audit_outbound_orders.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class OutboundAuditTests(unittest.TestCase):
    def test_reviewed_physical_product(self):
        self.assertEqual(audit.classify('123', 'PADS', 'PADS TO MATCH ALL CUSHIONS', 2, True), 'candidate_outbound')

    def test_reviewed_service_case_normalization(self):
        self.assertEqual(audit.classify('123', 'm', 'Manual', 2, True), 'nonmerchandise_excluded')

    def test_reviewed_ambiguous_fulfillment(self):
        self.assertEqual(audit.classify('123', 'gift_0001_20', 'Voucher', 2, True), 'fulfillment_mode_review')

    def test_known_product_does_not_override_admin_description(self):
        self.assertEqual(audit.classify('123', 'DCGSSBOY', 'update', 2, True), 'administrative_description_review')

    def test_cancellation_even_with_positive_quantity(self):
        self.assertEqual(audit.classify("C123", "12345", "item", 2), "cancellation")

    def test_return_only(self):
        self.assertEqual(audit.classify("123", "12345", "item", -2), "nonpositive_quantity")

    def test_mixed_invoice_keeps_only_positive_line(self):
        reasons = [audit.classify("123", "12345", "item", q) for q in (2, -1)]
        self.assertEqual(reasons, ["candidate_outbound", "nonpositive_quantity"])

    def test_missing_invoice(self):
        self.assertEqual(audit.classify(None, "12345", "item", 2), "missing_invoice")

    def test_postage_requires_review(self):
        self.assertEqual(audit.classify("123", "POST", "POSTAGE", 1), "nonstandard_code_review")

    def test_blank_description_requires_review(self):
        self.assertEqual(audit.classify("123", "12345", None, 1), "missing_description_review")

    def test_product_suffix_is_allowed(self):
        self.assertEqual(audit.classify("123", "12345A", "item", 1), "candidate_outbound")


if __name__ == "__main__":
    unittest.main()
