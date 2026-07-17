# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder


class CustomPurchaseOrder(PurchaseOrder):
	"""Extended PurchaseOrder controller for vendor portal validations.

	Pattern: All overridden methods call super() first to preserve
	ERPNext's original business logic."""

	def validate(self):
		"""Extend validate: blacklist check + rating threshold check."""
		# Always call super() first to preserve ERPNext's original validation
		super().validate()

		self._check_blacklist()
		self._check_rating_threshold()

		frappe.logger().info(
			f"PO {self.name} validated for supplier {self.supplier}"
		)

	def on_submit(self):
		"""Extend on_submit: auto-create a Pricing Vendor Rating Log entry."""
		super().on_submit()
		self._auto_rate_on_submit()

	def on_cancel(self):
		"""Extend on_cancel: clean up linked Vendor Rating Log entries."""
		super().on_cancel()
		self._delete_rating_logs()

	# ---------- helpers ----------

	def _check_blacklist(self):
		"""Block PO creation if the supplier is blacklisted."""
		if not self.supplier:
			return
		supplier = frappe.get_doc("Supplier", self.supplier)
		if supplier.get("custom_is_blacklisted"):
			reason = supplier.get("custom_blacklist_reason") or "No reason provided"
			frappe.throw(
				f"Cannot create Purchase Order for blacklisted supplier "
				f"{supplier.supplier_name}. Reason: {reason}"
			)

	def _check_rating_threshold(self):
		"""Block PO creation if supplier's vendor rating is below the
		minimum threshold defined in their Vendor Category."""
		if not self.supplier:
			return
		supplier = frappe.get_doc("Supplier", self.supplier)
		vendor_category = supplier.get("custom_vendor_category")
		if not vendor_category:
			return

		category = frappe.get_doc("Vendor Category", vendor_category)
		threshold = category.minimum_rating_threshold or 0
		rating = supplier.get("custom_vendor_rating") or 0
		rating = float(rating) * 5.0

		if threshold and rating < threshold:
			frappe.throw(
				f"Supplier {supplier.supplier_name} rating ({rating}) is below "
				f"the minimum threshold ({threshold}) for {vendor_category}."
			)

	def _auto_rate_on_submit(self):
		"""Auto-create a Vendor Rating Log with a Pricing score based on
		how the PO's grand_total compares to the supplier's historical average.

		Skips creation if a Pricing rating log already exists for this PO
		(e.g. after cancel & re-submit)."""
		if not self.supplier or not self.grand_total:
			return

		# Guard: already rated — handles cancel & re-submit cycles
		if frappe.db.exists(
			"Vendor Rating Log",
			{"purchase_order": self.name, "rating_type": "Pricing"},
		):
			return

		# Calculate average PO value for this supplier (exclude self)
		avg_result = frappe.db.get_list(
			"Purchase Order",
			filters={
				"supplier": self.supplier,
				"docstatus": 1,
				"name": ("!=", self.name),
			},
			pluck="grand_total",
		)
		if avg_result:
			avg_value = sum(avg_result) / len(avg_result)
			# Within 10% of average → score 4; cheaper → 5; more expensive → 3
			if self.grand_total <= avg_value * 0.9:
				score = 5
			elif self.grand_total <= avg_value * 1.1:
				score = 4
			else:
				score = 3
		else:
			# No historical data — default score
			score = 4

		rating_log = frappe.get_doc(
			{
				"doctype": "Vendor Rating Log",
				"supplier": self.supplier,
				"purchase_order": self.name,
				"rating_type": "Pricing",
				"score": score,
				"remarks": (
					f"Auto-rated on submission of PO {self.name}. "
					f"Grand Total: {self.grand_total}"
				),
			}
		)

		try:
			rating_log.insert(ignore_permissions=True, ignore_mandatory=True)
		except Exception as e:
			frappe.log_error(
				title="Vendor Rating Log Creation Failed",
				message=f"PO {self.name}: {e}",
			)

	def _delete_rating_logs(self):
		"""Delete only Pricing-type Vendor Rating Log entries linked to this
		PO. Delivery logs (linked via Purchase Receipt) are not touched."""
		logs = frappe.db.get_list(
			"Vendor Rating Log",
			filters={
				"purchase_order": self.name,
				"rating_type": "Pricing",
				"purchase_receipt": ("is", "not set"),
			},
			pluck="name",
		)
		for log_name in logs:
			frappe.delete_doc("Vendor Rating Log", log_name, force=True)
