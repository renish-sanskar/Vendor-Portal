# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address


class VendorOnboarding(Document):
	def validate(self):
		"""Main validation hook — runs all field validators before save."""
		self._validate_gst()
		self._validate_pan()
		self._validate_email()
		self._validate_document_count()
		self._check_duplicate_gst()

		# Ensure documents are verified before transitioning to Approved
		if self.onboarding_status == "Approved" or getattr(self, "workflow_state", "") == "Approved":
			if not self.documents:
				frappe.throw("No documents found. The vendor must upload documents before approval.")
			unverified = [d.name for d in self.documents if not getattr(d, "is_verified", 0)]
			if unverified:
				frappe.throw("You must verify all uploaded documents before approving the vendor.")

	def on_submit(self):
		"""On submit (docstatus 0→1), move the onboarding into 'Under Review'
		so a Purchase Manager can action it. Approval/rejection then transition
		it further via the whitelisted methods."""
		if self.onboarding_status in ("Draft", None, ""):
			self.onboarding_status = "Under Review"
			# Reflect the change in the DB when called on a persisted doc.
			if not self.flags.get("in_insert") and self.name:
				self.db_set("onboarding_status", "Under Review")

	def on_update(self):
		"""When the onboarding is approved (via workflow action), auto-create the
		Supplier record and send the approval email. Guarded by linked_supplier
		to prevent duplicate creation."""
		if (
			self.onboarding_status == "Approved"
			and not self.linked_supplier
			and not self.flags.get("supplier_created")
		):
			self.flags["supplier_created"] = True
			supplier = self._create_supplier(self)
			frappe.db.set_value(
				"Vendor Onboarding",
				self.name,
				{
					"linked_supplier": supplier.name,
					"reviewed_by": self.reviewed_by or frappe.session.user,
					"review_date": self.review_date or frappe.utils.now_datetime(),
				},
			)
			self._send_approval_email(self, supplier)

	# ---------- validators ----------

	def _validate_gst(self):
		"""Validate GST number against the standard 15-character Indian GSTIN format.
		Pattern: 2-digit state code + 10-char PAN + 1 entity code + Z + 1 check digit.
		Skips validation if the field is empty (optional)."""
		if not self.gst_number:
			return
		gst_pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
		if not re.match(gst_pattern, self.gst_number.upper()):
			frappe.throw(
				"GST Number is not valid. "
				"It must be a 15-character alphanumeric string in the format: "
				"2-digit state code + 10-character PAN + 1 entity code + Z + 1 check digit."
			)

	def _validate_pan(self):
		"""Validate PAN number against the standard 10-character Indian PAN format.
		Pattern: 5 uppercase letters + 4 digits + 1 uppercase letter (XXXXX9999X).
		Skips validation if the field is empty (optional)."""
		if not self.pan_number:
			return
		pan_pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
		if not re.match(pan_pattern, self.pan_number.upper()):
			frappe.throw(
				"PAN Number is not valid. "
				"It must be a 10-character alphanumeric string in the format: ABCDE1234F."
			)

	def _validate_email(self):
		"""Validate email address using Frappe's built-in email validator.
		Throws if the email format is invalid."""
		if not validate_email_address(self.email):
			frappe.throw(f"The email address '{self.email}' is not valid.")

	def _validate_document_count(self):
		"""Check that the documents child table has at least the minimum
		required number of rows configured in Vendor Portal Settings.
		Falls back to a default of 2 if the setting is not configured."""
		settings = frappe.get_single("Vendor Portal Settings")
		min_docs = settings.get("min_documents_required") or 2
		if len(self.documents or []) < min_docs:
			frappe.throw(
				f"At least {min_docs} document(s) are required in the Documents table. "
				f"Please upload the necessary documents before submitting."
			)

	def _check_duplicate_gst(self):
		"""Prevent duplicate GST numbers by checking:
		1. No other submitted Vendor Onboarding has the same GST.
		2. No active Supplier is already registered with the same GST
		   (checked across gstin, tax_id, and custom_gst_number columns).
		Skips validation if the field is empty (optional)."""
		if not self.gst_number:
			return
		existing = frappe.db.get_list(
			"Vendor Onboarding",
			filters={
				"gst_number": self.gst_number,
				"docstatus": 1,
				"name": ("!=", self.name or "New"),
			},
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.throw(
				f"An approved Vendor Onboarding ({existing[0]}) already exists "
				f"with the same GST Number '{self.gst_number}'."
			)

		# also check the Supplier doctype
		supplier = None
		if frappe.db.has_column("Supplier", "gstin"):
			supplier = frappe.db.get_value(
				"Supplier",
				{"gstin": self.gst_number, "disabled": 0},
				"name",
			)
		if not supplier and frappe.db.has_column("Supplier", "tax_id"):
			supplier = frappe.db.get_value(
				"Supplier",
				{"tax_id": self.gst_number, "disabled": 0},
				"name",
			)
		if not supplier and frappe.db.has_column("Supplier", "custom_gst_number"):
			supplier = frappe.db.get_value(
				"Supplier",
				{"custom_gst_number": self.gst_number, "disabled": 0},
				"name",
			)
		if supplier:
			frappe.throw(
				f"An active Supplier ({supplier}) is already registered "
				f"with the same GST Number '{self.gst_number}'."
			)

	# ---------- whitelisted API methods ----------

	@frappe.whitelist()
	def approve_onboarding(self, onboarding_name):
		"""Approve a vendor onboarding request.
		- Validates that the current user has the Purchase Manager role.
		- Sets the status to Approved and creates the linked Supplier.
		Works whether the document is still a Draft or already submitted
		(submitted documents reach this method in the 'Under Review' state).
		Returns a dict with the updated status."""
		self._check_role("Purchase Manager")

		doc = frappe.get_doc("Vendor Onboarding", onboarding_name)

		# Already approved — nothing to do (idempotent).
		if doc.onboarding_status == "Approved" and doc.linked_supplier:
			return {"supplier": doc.linked_supplier, "onboarding_status": "Approved"}

		reviewer = frappe.session.user
		review_dt = frappe.utils.now_datetime()

		if doc.docstatus == 1:
			# Submitted document: regular fields are immutable via save(), so
			# persist the status change with db_set and run approval actions
			# directly (on_update does not fire for db_set writes).
			doc.db_set("onboarding_status", "Approved")
			if frappe.db.has_column("Vendor Onboarding", "workflow_state"):
				doc.db_set("workflow_state", "Approved")
			doc.db_set("reviewed_by", reviewer)
			doc.db_set("review_date", review_dt)
			doc.reload()

			if not doc.linked_supplier and not doc.flags.get("supplier_created"):
				doc.flags["supplier_created"] = True
				supplier = self._create_supplier(doc)
				frappe.db.set_value(
					"Vendor Onboarding",
					doc.name,
					{
						"linked_supplier": supplier.name,
						"reviewed_by": reviewer,
						"review_date": review_dt,
					},
				)
				self._send_approval_email(doc, supplier)
				doc.reload()

			return {"supplier": doc.linked_supplier, "onboarding_status": "Approved"}

		# Draft document: set Approved then submit (on_update creates Supplier).
		doc.onboarding_status = "Approved"
		if frappe.db.has_column("Vendor Onboarding", "workflow_state"):
			doc.workflow_state = "Approved"

		doc.reviewed_by = reviewer
		doc.review_date = review_dt

		# Saving it as Approved will trigger validation checks.
		doc.save()
		# Submitting it finalizes the state and fires on_update.
		doc.submit()

		return {"supplier": doc.linked_supplier, "onboarding_status": "Approved"}

	@frappe.whitelist()
	def reject_onboarding(self, onboarding_name, reason):
		"""Reject a vendor onboarding request with a reason.
		- Validates that the current user has the Purchase Manager role.
		- Sets onboarding status to Rejected and records the rejection reason.
		Returns a dict with the updated status."""
		self._check_role("Purchase Manager")

		update_dict = {
			"onboarding_status": "Rejected",
			"rejection_reason": reason,
			"reviewed_by": frappe.session.user,
			"review_date": frappe.utils.now_datetime(),
		}
		if frappe.db.has_column("Vendor Onboarding", "workflow_state"):
			update_dict["workflow_state"] = "Rejected"

		frappe.db.set_value(
			"Vendor Onboarding",
			onboarding_name,
			update_dict,
		)

		return {"onboarding_status": "Rejected"}

	# ---------- helpers ----------

	@staticmethod
	def _check_role(role):
		"""Check that the current logged-in user has the specified role.
		Throws a permission error if the role is not found."""
		if role not in frappe.get_roles():
			frappe.throw(
				f"You do not have the '{role}' role required to perform this action."
			)

	@staticmethod
	def _create_supplier(doc):
		"""Create an ERPNext Supplier record from the onboarding data.
		Also creates linked Address, Contact, and optionally a Bank Account.
		Returns the created Supplier document."""
		default_group = frappe.db.get_single_value(
			"Vendor Portal Settings", "default_supplier_group"
		)
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": doc.supplier_name,
				"supplier_group": default_group or "All Supplier Groups",
				"gstin": doc.gst_number,
				"pan": doc.pan_number,
				"custom_vendor_category": doc.vendor_category,
				"custom_onboarding_reference": doc.name,
			}
		)
		supplier.insert()
		supplier.reload()  # ensure default fields are populated
		supplier_name = supplier.name

		# ---------- Address ----------
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": doc.supplier_name,
				"address_type": "Billing",
				"address_line1": doc.address_line_1,
				"city": doc.city,
				"state": doc.state,
				"pincode": doc.pincode,
				"country": "India",
				"is_primary_address": 1,
				"is_shipping_address": 1,
				"links": [{"link_doctype": "Supplier", "link_name": supplier_name}],
			}
		)
		address.insert()

		# ---------- Contact ----------
		contact_person = doc.contact_person or doc.supplier_name
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": contact_person,
				"email_id": doc.email,
				"phone": doc.phone,
				"is_primary_contact": 1,
				"links": [{"link_doctype": "Supplier", "link_name": supplier_name}],
			}
		)
		contact.insert()

		# ---------- Bank Account ----------
		if doc.bank_name and doc.bank_account_number:
			bank = frappe.db.get_value("Bank", {"bank_name": doc.bank_name}, "name")
			if not bank:
				bank_doc = frappe.get_doc({"doctype": "Bank", "bank_name": doc.bank_name})
				bank_doc.insert()
				bank = bank_doc.name
			bank_account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": doc.bank_name,
					"bank": bank,
					"account_number": doc.bank_account_number,
					"ifsc_code": doc.ifsc_code,
					"is_company_account": 0,
					"party_type": "Supplier",
					"party": supplier_name,
				}
			)
			bank_account.insert()

		return supplier

	@staticmethod
	def _send_approval_email(doc, supplier):
		"""Send an approval notification email to the vendor's email address
		using the vendor_onboarding_approved.html template.
		Silently returns if no email is configured on the onboarding record."""
		if not doc.email:
			return
		subject = f"Vendor Onboarding Approved – {doc.supplier_name}"
		company = frappe.db.get_single_value("Global Defaults", "default_company") or "India"
		message = frappe.render_template(
			"vendor_portal/templates/emails/vendor_onboarding_approved.html",
			{"doc": doc, "supplier": supplier, "company": company},
		)
		frappe.sendmail(recipients=doc.email, subject=subject, message=message)
