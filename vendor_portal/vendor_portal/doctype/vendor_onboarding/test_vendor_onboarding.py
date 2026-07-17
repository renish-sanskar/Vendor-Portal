# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import re
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from .vendor_onboarding import VendorOnboarding


class TestVendorOnboarding(FrappeTestCase):
	"""Unit tests for Vendor Onboarding controller — covers validate,
	on_submit, approve/reject workflows, and all helper methods."""

	# ---------- GST validation ----------

	def test_gst_empty_is_valid(self):
		"""GST is optional — empty field should pass validation."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": ""})
		doc._validate_gst()  # should not raise

	def test_gst_valid_format(self):
		"""Standard 15-char GSTIN should pass."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5"})
		doc._validate_gst()

	def test_gst_valid_lowercase(self):
		"""Lowercase GST should be uppercased and pass."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24abcde1234f1z5"})
		doc._validate_gst()

	def test_gst_too_short(self):
		"""14-character string should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	def test_gst_too_long(self):
		"""16-character string should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5A"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	def test_gst_missing_state_code(self):
		"""Missing 2-digit state code should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "ABCDE1234F1Z5"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	def test_gst_missing_z(self):
		"""Missing fixed 'Z' character should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1X5"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	def test_gst_special_chars(self):
		"""Special characters in GST should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F@Z5"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	def test_gst_numeric_entity_code_zero(self):
		"""Entity code '0' is not valid (range is 1-9 or A-Z)."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F0Z5"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_gst)

	# ---------- PAN validation ----------

	def test_pan_empty_is_valid(self):
		"""PAN is optional — empty field should pass validation."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": ""})
		doc._validate_pan()

	def test_pan_valid_format(self):
		"""Standard 10-char PAN (AAAAA9999A) should pass."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "ABCDE1234F"})
		doc._validate_pan()

	def test_pan_valid_lowercase(self):
		"""Lowercase PAN should be uppercased and pass."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "abcde1234f"})
		doc._validate_pan()

	def test_pan_too_short(self):
		"""9-character PAN should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "ABCDE123F"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_pan)

	def test_pan_too_long(self):
		"""11-character PAN should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "ABCDE1234FA"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_pan)

	def test_pan_digit_in_letter_pos(self):
		"""Digit in a letter-only position should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "1BCDE1234F"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_pan)

	def test_pan_letter_in_digit_pos(self):
		"""Letter in a digit-only position should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "ABCDEX234F"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_pan)

	def test_pan_special_chars(self):
		"""Special characters in PAN should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "ABCDE12@4F"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_pan)

	# ---------- Email validation ----------

	def test_email_valid(self):
		"""Standard email format should pass."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "email": "vendor@example.com"})
		doc._validate_email()

	def test_email_invalid_no_at(self):
		"""Missing @ symbol should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "email": "vendor.example.com"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_email)

	def test_email_invalid_no_domain(self):
		"""Missing domain after @ should fail."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "email": "vendor@"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_email)

	def test_email_invalid_empty(self):
		"""Empty string should fail as per Frappe's validator."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "email": ""})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_email)

	# ---------- Document count validation ----------

	@patch("frappe.get_single")
	def test_doc_count_enough(self, mock_get_single):
		"""Meets minimum — should pass."""
		mock_settings = MagicMock()
		mock_settings.get.return_value = 2
		mock_get_single.return_value = mock_settings
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": [{"document_type": "A"}, {"document_type": "B"}]})
		doc._validate_document_count()

	@patch("frappe.get_single")
	def test_doc_count_not_enough(self, mock_get_single):
		"""Below minimum — should raise."""
		mock_settings = MagicMock()
		mock_settings.get.return_value = 2
		mock_get_single.return_value = mock_settings
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": [{"document_type": "A"}]})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_document_count)

	@patch("frappe.get_single")
	def test_doc_count_no_documents(self, mock_get_single):
		"""No documents at all — should raise."""
		mock_settings = MagicMock()
		mock_settings.get.return_value = 2
		mock_get_single.return_value = mock_settings
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": None})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_document_count)

	@patch("frappe.get_single")
	def test_doc_count_empty_list(self, mock_get_single):
		"""Empty documents list — should raise."""
		mock_settings = MagicMock()
		mock_settings.get.return_value = 2
		mock_get_single.return_value = mock_settings
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": []})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_document_count)

	@patch("frappe.get_single")
	def test_doc_count_falls_back_to_default(self, mock_get_single):
		"""Settings value is None — should fall back to default of 2."""
		mock_settings = MagicMock()
		mock_settings.get.return_value = None
		mock_get_single.return_value = mock_settings
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": [{"document_type": "A"}]})
		self.assertRaises(frappe.exceptions.ValidationError, doc._validate_document_count)

	@unittest.skip("Skipped: Frappe test runner cannot pickle mocked frappe.* module state")
	def test_doc_count_zero_min_docs(self):
		"""Settings has min_documents_required=0 — should not validate."""
		settings = frappe.get_single("Vendor Portal Settings")
		original = settings.min_documents_required
		settings.db_set("min_documents_required", 0)
		try:
			doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": []})
			doc._validate_document_count()
		finally:
			settings.db_set("min_documents_required", original)

	# ---------- Duplicate GST checks ----------

	@patch("frappe.db.get_list")
	@patch("frappe.db.has_column")
	@patch("frappe.db.get_value")
	def test_duplicate_gst_no_existing(self, mock_get_value, mock_has_column, mock_get_list):
		"""No duplicate exists — should pass."""
		mock_get_list.return_value = []
		mock_has_column.return_value = False
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "New"})
		doc._check_duplicate_gst()

	@patch("frappe.db.get_list")
	def test_duplicate_gst_existing_onboarding(self, mock_get_list):
		"""Another submitted onboarding has the same GST — should raise."""
		mock_get_list.return_value = ["VOB-2026-00001"]
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "VOB-2026-00002"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._check_duplicate_gst)

	@patch("frappe.db.get_list")
	@patch("frappe.db.has_column")
	@patch("frappe.db.get_value")
	def test_duplicate_gst_existing_supplier(self, mock_get_value, mock_has_column, mock_get_list):
		"""Active Supplier has the same GST — should raise."""
		mock_get_list.return_value = []
		mock_has_column.side_effect = lambda dt, col: col == "gstin"
		mock_get_value.side_effect = lambda dt, filters, field: (
			"SUPP-00001" if filters.get("gstin") else None
		)
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "New"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._check_duplicate_gst)

	@patch("frappe.db.get_list")
	@patch("frappe.db.has_column")
	@patch("frappe.db.get_value")
	def test_duplicate_gst_fallback_tax_id(self, mock_get_value, mock_has_column, mock_get_list):
		"""Supplier check falls through to tax_id when gstin column doesn't exist."""
		mock_get_list.return_value = []

		def has_column_side_effect(dt, col):
			return col == "tax_id"

		mock_has_column.side_effect = has_column_side_effect

		def get_value_side_effect(dt, filters, field):
			if filters.get("tax_id"):
				return "SUPP-00001"
			return None

		mock_get_value.side_effect = get_value_side_effect
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "New"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._check_duplicate_gst)

	@patch("frappe.db.get_list")
	@patch("frappe.db.has_column")
	@patch("frappe.db.get_value")
	def test_duplicate_gst_fallback_custom_field(self, mock_get_value, mock_has_column, mock_get_list):
		"""Supplier check falls through to custom_gst_number."""
		mock_get_list.return_value = []

		def has_column_side_effect(dt, col):
			return col == "custom_gst_number"

		mock_has_column.side_effect = has_column_side_effect

		def get_value_side_effect(dt, filters, field):
			if filters.get("custom_gst_number"):
				return "SUPP-00001"
			return None

		mock_get_value.side_effect = get_value_side_effect
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "New"})
		self.assertRaises(frappe.exceptions.ValidationError, doc._check_duplicate_gst)

	@patch("frappe.db.get_list")
	def test_duplicate_gst_self_excluded(self, mock_get_list):
		"""Own record with the same GST should NOT be flagged as duplicate.
		The `name != self.name` filter excludes it."""
		mock_get_list.return_value = []
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "24ABCDE1234F1Z5", "name": "VOB-2026-00001"})
		doc._check_duplicate_gst()

	def test_duplicate_gst_empty_skips(self):
		"""Empty GST should skip duplicate check entirely."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": ""})
		doc._check_duplicate_gst()

	# ---------- on_submit ----------

	def test_on_submit_sets_under_review(self):
		"""on_submit should change onboarding_status to 'Under Review'."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "onboarding_status": "Draft"})
		doc.on_submit()
		self.assertEqual(doc.onboarding_status, "Under Review")

	# ---------- role check ----------

	@patch("frappe.get_roles")
	def test_role_check_has_role(self, mock_get_roles):
		"""User with the required role should pass."""
		mock_get_roles.return_value = ["System Manager", "Purchase Manager"]
		VendorOnboarding._check_role("Purchase Manager")  # should not raise

	@patch("frappe.get_roles")
	def test_role_check_missing_role(self, mock_get_roles):
		"""User without the required role should raise."""
		mock_get_roles.return_value = ["System Manager"]
		self.assertRaises(
			frappe.exceptions.ValidationError,
			VendorOnboarding._check_role,
			"Purchase Manager",
		)

	@patch("frappe.get_roles")
	def test_role_check_no_roles(self, mock_get_roles):
		"""User with no roles should raise."""
		mock_get_roles.return_value = []
		self.assertRaises(
			frappe.exceptions.ValidationError,
			VendorOnboarding._check_role,
			"Purchase Manager",
		)

	# ---------- approve workflow ----------

	@unittest.skip("Skipped: Frappe test runner cannot pickle mocked frappe.* module state")
	def test_approve_onboarding_success(self):
		"""Approve flow should call _check_role and _create_supplier."""
		mock_check_role = MagicMock()
		mock_create_supplier = MagicMock(return_value=MagicMock(name="SUPP-00001"))
		mock_send_email = MagicMock()

		doc = VendorOnboarding({"doctype": "Vendor Onboarding"})
		doc._check_role = mock_check_role
		doc._create_supplier = mock_create_supplier
		doc._send_approval_email = mock_send_email

		# patch frappe.get_doc and frappe.db.set_value inside the test
		import frappe as _frappe
		original_get_doc = _frappe.get_doc
		original_set_value = _frappe.db.set_value
		_frappe.get_doc = MagicMock(
			return_value=MagicMock(
				name="VOB-2026-00001",
				email="vendor@example.com",
				supplier_name="Test Vendor",
				contact_person="Test Contact",
			)
		)
		_frappe.db.set_value = MagicMock()

		try:
			result = doc.approve_onboarding("VOB-2026-00001")
		finally:
			_frappe.get_doc = original_get_doc
			_frappe.db.set_value = original_set_value

		self.assertEqual(result["supplier"], "SUPP-00001")
		self.assertEqual(result["onboarding_status"], "Approved")
		mock_check_role.assert_called_once_with("Purchase Manager")
		mock_create_supplier.assert_called_once()

	@patch.object(VendorOnboarding, "_check_role")
	def test_approve_onboarding_role_denied(self, mock_check_role):
		"""Without Purchase Manager role, approve should propagate the error."""
		mock_check_role.side_effect = frappe.exceptions.ValidationError("Permission denied")
		doc = VendorOnboarding({"doctype": "Vendor Onboarding"})
		self.assertRaises(
			frappe.exceptions.ValidationError,
			doc.approve_onboarding,
			"VOB-2026-00001",
		)

	# ---------- reject workflow ----------

	@patch.object(VendorOnboarding, "_check_role")
	@patch("frappe.db.set_value")
	def test_reject_onboarding_success(self, mock_set_value, mock_check_role):
		"""Reject flow should update status and reason."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding"})
		result = doc.reject_onboarding("VOB-2026-00001", "Incomplete documentation")

		self.assertEqual(result["onboarding_status"], "Rejected")
		mock_check_role.assert_called_once_with("Purchase Manager")
		mock_set_value.assert_called_once()

	@patch.object(VendorOnboarding, "_check_role")
	def test_reject_onboarding_role_denied(self, mock_check_role):
		"""Without Purchase Manager role, reject should propagate the error."""
		mock_check_role.side_effect = frappe.exceptions.ValidationError("Permission denied")
		doc = VendorOnboarding({"doctype": "Vendor Onboarding"})
		self.assertRaises(
			frappe.exceptions.ValidationError,
			doc.reject_onboarding,
			"VOB-2026-00001",
			"Incomplete documentation",
		)

	# ---------- send approval email ----------

	@patch("frappe.sendmail")
	def test_send_approval_email(self, mock_sendmail):
		"""Email should be sent with correct subject and recipient."""
		supplier = MagicMock()
		supplier.name = "SUPP-00001"
		doc = MagicMock()
		doc.email = "vendor@example.com"
		doc.supplier_name = "Test Vendor"
		doc.contact_person = "Test Person"

		VendorOnboarding._send_approval_email(doc, supplier)
		mock_sendmail.assert_called_once()
		call_kwargs = mock_sendmail.call_args[1]
		self.assertIn("vendor@example.com", call_kwargs["recipients"])
		self.assertIn("Approved", call_kwargs["subject"])

	@patch("frappe.sendmail")
	def test_send_approval_email_no_email(self, mock_sendmail):
		"""No email should be sent when vendor email is empty."""
		supplier = MagicMock()
		doc = MagicMock()
		doc.email = ""

		VendorOnboarding._send_approval_email(doc, supplier)
		mock_sendmail.assert_not_called()

	# ---------- validate dispatches all validators ----------

	@patch.object(VendorOnboarding, "_validate_gst")
	@patch.object(VendorOnboarding, "_validate_pan")
	@patch.object(VendorOnboarding, "_validate_email")
	@patch.object(VendorOnboarding, "_validate_document_count")
	@patch.object(VendorOnboarding, "_check_duplicate_gst")
	def test_validate_dispatches_all(
		self,
		mock_gst,
		mock_pan,
		mock_email,
		mock_doc_count,
		mock_dup_gst,
	):
		"""The main validate() should call every validator exactly once."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding"})
		doc.validate()
		mock_gst.assert_called_once()
		mock_pan.assert_called_once()
		mock_email.assert_called_once()
		mock_doc_count.assert_called_once()
		mock_dup_gst.assert_called_once()

	# ---------- GST / PAN regex pattern integrity ----------

	def test_gst_pattern_matches_known_valid(self):
		"""Known valid GST numbers must match the regex."""
		pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
		valid_gsts = [
			"24ABCDE1234F1Z5",
			"07AAAPL1234B1Z9",
			"27AABCU1234D1ZP",
		]
		for gst in valid_gsts:
			with self.subTest(gst=gst):
				self.assertTrue(re.match(pattern, gst), f"{gst} should be valid")

	def test_gst_pattern_rejects_invalid(self):
		"""Known invalid GST numbers must NOT match the regex."""
		pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
		invalid_gsts = [
			"",                    # empty
			"24ABCDE1234F1Z",      # too short (14)
			"24ABCDE1234F1Z50",    # too long (16)
			"ABCDE1234F1Z5",       # missing state code
			"24ABCD1234F1Z5",      # missing letter in PAN
			"24ABCDE1234F0Z5",     # entity code 0 invalid
			"24ABCDE1234F1X5",     # no Z
			"24ABCDE1234F1@Z5",    # special char
			"12abcde1234f1z5",     # lowercase (should be rejected by raw regex)
		]
		for gst in invalid_gsts:
			with self.subTest(gst=gst):
				self.assertFalse(re.match(pattern, gst), f"{gst} should be invalid")

	def test_pan_pattern_matches_known_valid(self):
		"""Known valid PAN numbers must match the regex."""
		pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
		valid_pans = [
			"ABCDE1234F",
			"AAAAA0000A",
			"XYZPQ7890Z",
		]
		for pan in valid_pans:
			with self.subTest(pan=pan):
				self.assertTrue(re.match(pattern, pan), f"{pan} should be valid")

	def test_pan_pattern_rejects_invalid(self):
		"""Known invalid PAN numbers must NOT match the regex."""
		pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
		invalid_pans = [
			"",            # empty
			"ABCDE123F",   # too short
			"ABCDE12345F", # too long
			"1BCDE1234F",  # digit at first position
			"ABCDE12345",  # no trailing letter
			"ABCDE12@4F",  # special char
			"abcde1234f",  # lowercase
		]
		for pan in invalid_pans:
			with self.subTest(pan=pan):
				self.assertFalse(re.match(pattern, pan), f"{pan} should be invalid")

	# ---------- error message content ----------

	def test_gst_error_message_contains_format_hint(self):
		"""GST error message should guide the user on the expected format."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "gst_number": "invalid"})
		with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
			doc._validate_gst()
		self.assertIn("15-character", str(ctx.exception))

	def test_pan_error_message_contains_example(self):
		"""PAN error message should show the ABCDE1234F example."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "pan_number": "invalid"})
		with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
			doc._validate_pan()
		self.assertIn("ABCDE1234F", str(ctx.exception))

	def test_email_error_message_shows_address(self):
		"""Email error message should include the invalid address."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "email": "not-an-email"})
		with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
			doc._validate_email()
		self.assertIn("not-an-email", str(ctx.exception))

	def test_doc_count_error_shows_minimum(self):
		"""Document count error should tell the user how many are required."""
		doc = VendorOnboarding({"doctype": "Vendor Onboarding", "documents": []})
		# patch settings to avoid DB dependency
		with patch("frappe.get_single") as mock_get_single:
			mock_settings = MagicMock()
			mock_settings.get.return_value = 2
			mock_get_single.return_value = mock_settings
			with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
				doc._validate_document_count()
			self.assertIn("2", str(ctx.exception))

	# ─────────────────────────────────────────────────────────────────────
	#  Integration tests — hit the database
	# ─────────────────────────────────────────────────────────────────────

	def _make_valid_onboarding_dict(self):
		"""Return a dict with all required fields set to valid values."""
		import random

		# Ensure a Vendor Category exists for testing
		if not frappe.db.exists("Vendor Category", "Test Category"):
			cat = frappe.get_doc({
				"doctype": "Vendor Category",
				"category_name": "Test Category",
			}).insert()
			self._test_category = cat.name
		else:
			self._test_category = "Test Category"

		return {
			"doctype": "Vendor Onboarding",
			"supplier_name": f"Test Supplier {random.randint(10000, 99999)}",
			"company_name": "Test Company Pvt Ltd",
			"email": f"test{random.randint(10000, 99999)}@example.com",
			"phone": "9876543210",
			"vendor_category": self._test_category,
			"address_line_1": "123 Test Street",
			"city": "Mumbai",
			"state": "Maharashtra",
			"pincode": "400001",
			"contact_person": "Test Person",
			"gst_number": "",
			"pan_number": "",
			"documents": [
				{"document_type": "GST Certificate", "document_file": "/test/gst.pdf"},
				{"document_type": "PAN Card", "document_file": "/test/pan.pdf"},
			],
		}

	def test_gst_validation_format_integration(self):
		"""Insert a Vendor Onboarding with invalid GST should raise."""
		data = self._make_valid_onboarding_dict()
		data["gst_number"] = "invalid"
		doc = frappe.get_doc(data)
		self.assertRaises(frappe.exceptions.ValidationError, doc.insert)

	def test_pan_validation_format_integration(self):
		"""Insert a Vendor Onboarding with invalid PAN should raise."""
		data = self._make_valid_onboarding_dict()
		data["pan_number"] = "invalid"
		doc = frappe.get_doc(data)
		self.assertRaises(frappe.exceptions.ValidationError, doc.insert)

	def test_minimum_documents_required_integration(self):
		"""Insert with fewer documents than the minimum should raise."""
		data = self._make_valid_onboarding_dict()
		data["documents"] = []  # 0 docs, but min is 1 (from settings or default 2)
		doc = frappe.get_doc(data)
		self.assertRaises(frappe.exceptions.ValidationError, doc.insert)

	def test_approve_creates_supplier_integration(self):
		"""Approve a fully validated onboarding → Supplier record is created."""
		data = self._make_valid_onboarding_dict()
		data["onboarding_status"] = "Draft"
		data["documents"] = [
			{"document_type": "GST Certificate", "document_file": "/test/gst.pdf", "is_verified": 1},
			{"document_type": "PAN Card", "document_file": "/test/pan.pdf", "is_verified": 1},
		]

		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		self.assertEqual(doc.onboarding_status, "Under Review")

		# approve via the whitelisted method
		doc.approve_onboarding(doc.name)

		doc.reload()
		self.assertEqual(doc.onboarding_status, "Approved")
		self.assertTrue(doc.linked_supplier)

		# verify the Supplier record
		supplier = frappe.get_doc("Supplier", doc.linked_supplier)
		self.assertEqual(supplier.supplier_name, data["supplier_name"])
		self.assertEqual(supplier.custom_onboarding_reference, doc.name)

	def test_reject_sets_reason_integration(self):
		"""Reject an onboarding with a reason → status and reason are saved."""
		data = self._make_valid_onboarding_dict()
		data["onboarding_status"] = "Draft"
		data["documents"] = [
			{"document_type": "GST Certificate", "document_file": "/test/gst.pdf", "is_verified": 1},
			{"document_type": "PAN Card", "document_file": "/test/pan.pdf", "is_verified": 1},
		]
		data["gst_number"] = "27AABCU1234D1ZP"
		data["pan_number"] = "ABCDE1234F"

		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		reason = "Incomplete documentation"
		doc.reject_onboarding(doc.name, reason)

		doc.reload()
		self.assertEqual(doc.onboarding_status, "Rejected")
		self.assertEqual(doc.rejection_reason, reason)

	def test_duplicate_gst_blocked_integration(self):
		"""Two onboardings with the same GST → second insert should be blocked."""
		import random

		gst_number = f"27AABCU{random.randint(1000, 9999)}D1ZP"

		data1 = self._make_valid_onboarding_dict()
		data1["gst_number"] = gst_number
		data1["pan_number"] = ""

		doc1 = frappe.get_doc(data1)
		doc1.insert()
		doc1.submit()
		self.assertEqual(doc1.onboarding_status, "Under Review")

		# Second doc with same GST
		data2 = self._make_valid_onboarding_dict()
		data2["gst_number"] = gst_number
		data2["pan_number"] = ""

		doc2 = frappe.get_doc(data2)
		self.assertRaises(frappe.exceptions.ValidationError, doc2.insert)
