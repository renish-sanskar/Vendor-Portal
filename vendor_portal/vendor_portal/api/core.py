# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


# ---------------------------------------------------------------------------
# Helpers (defined first so all endpoints can reference them)
# ---------------------------------------------------------------------------

def _mandatory(value, label):
	"""Throw a readable validation error if a required value is missing."""
	if not value or (isinstance(value, str) and not value.strip()):
		frappe.throw(f"'{label}' is required.")


def _get_weighted_rating(supplier: str) -> tuple[float, int]:
	"""Return (weighted_rating_0_to_1, total_count) for a supplier.

	Uses the weights configured in Vendor Portal Settings.  This is the single
	source of truth for the weighted average — both submit_vendor_rating and
	get_vendor_dashboard call this instead of duplicating the logic.
	"""
	data = frappe.db.sql(
		"""
		SELECT rating_type, AVG(score) AS avg_score
		FROM `tabVendor Rating Log`
		WHERE supplier = %s
		GROUP BY rating_type
		""",
		(supplier,),
		as_dict=True,
	)

	if not data:
		return 0.0, 0

	avg_by_type = {r.rating_type: r.avg_score for r in data}

	settings = frappe.get_cached_doc("Vendor Portal Settings")
	weights = {
		"Delivery":      flt(settings.rating_weight_delivery)      or 0.25,
		"Quality":       flt(settings.rating_weight_quality)       or 0.25,
		"Pricing":       flt(settings.rating_weight_pricing)       or 0.25,
		"Communication": flt(settings.rating_weight_communication) or 0.25,
	}

	total_weight  = 0.0
	weighted_score = 0.0
	for r_type, avg_s in avg_by_type.items():
		weight = weights.get(r_type, 0.0)
		weighted_score += avg_s * weight
		total_weight   += weight

	final_1_to_5 = (weighted_score / total_weight) if total_weight > 0 else 0.0
	final_0_to_1 = final_1_to_5 / 5.0

	total_count = frappe.db.count("Vendor Rating Log", {"supplier": supplier})
	return final_0_to_1, total_count


# ---------------------------------------------------------------------------
# 1. get_vendor_rating_history
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_vendor_rating_history(supplier):
	"""Return all Vendor Rating Log records for the given supplier,
	sorted by creation date descending.

	Args:
		supplier (str): Supplier name/link value.

	Returns:
		list[dict]: List of Vendor Rating Log dicts, or an empty list.
	"""
	# Let PermissionError and ValidationError propagate to the caller as-is;
	# only catch unexpected runtime exceptions and log them.
	try:
		_mandatory(supplier, "supplier")

		records = frappe.get_list(
			"Vendor Rating Log",
			filters={"supplier": supplier},
			fields=[
				"name",
				"rating_date",
				"rating_type",
				"score",
				"remarks",
				"creation",
			],
			order_by="creation desc",
		)

		return records

	except (frappe.ValidationError, frappe.PermissionError):
		raise
	except Exception:
		frappe.log_error(
			title="get_vendor_rating_history Error",
			message=frappe.get_traceback(),
		)
		frappe.throw("Failed to fetch vendor rating history. Please try again.")


# ---------------------------------------------------------------------------
# 2. submit_vendor_rating
# ---------------------------------------------------------------------------

@frappe.whitelist()
def submit_vendor_rating(
	supplier,
	rating_type,
	score,
	remarks=None,
	purchase_order=None,
	purchase_receipt=None,
):
	"""Create a new Vendor Rating Log and recalculate the supplier's weighted rating.

	Args:
		supplier (str): Link to Supplier.
		rating_type (str): One of Delivery / Quality / Pricing / Communication.
		score (float | int): Rating score (1–5).
		remarks (str | None): Optional remarks.
		purchase_order (str | None): Link to Purchase Order.
		purchase_receipt (str | None): Link to Purchase Receipt.

	Returns:
		dict: Created Vendor Rating Log document as a dict.
	"""
	try:
		# -- validation --
		_mandatory(supplier, "supplier")
		_mandatory(rating_type, "rating_type")

		VALID_TYPES = ("Delivery", "Quality", "Pricing", "Communication")
		if rating_type not in VALID_TYPES:
			frappe.throw(
				f"Invalid rating_type '{rating_type}'. "
				f"Must be one of: {', '.join(VALID_TYPES)}."
			)

		# Validate that score is actually numeric before coercing.
		try:
			score = float(score)
		except (TypeError, ValueError):
			frappe.throw("Score must be a number between 1 and 5.")

		score = flt(score)
		if score < 1 or score > 5:
			frappe.throw("Score must be between 1 and 5.")

		# -- insert rating log and update supplier score atomically --
		# Both operations are within the same DB transaction; if an exception
		# occurs after insert, the entire transaction rolls back so there is
		# no orphaned rating log left behind.
		doc = frappe.get_doc(
			{
				"doctype": "Vendor Rating Log",
				"supplier": supplier,
				"purchase_order": purchase_order,
				"purchase_receipt": purchase_receipt,
				"rating_type": rating_type,
				"score": score,
				"remarks": remarks or "",
			}
		)
		doc.insert()

		# Recalculate using the shared weighted-average helper.
		final_0_to_1, total_count = _get_weighted_rating(supplier)

		frappe.db.set_value(
			"Supplier",
			supplier,
			{
				"custom_vendor_rating":      final_0_to_1,
				"custom_total_rating_count": total_count,
			},
		)

		return doc.as_dict()

	except (frappe.ValidationError, frappe.PermissionError):
		raise
	except Exception:
		frappe.log_error(
			title="submit_vendor_rating Error",
			message=frappe.get_traceback(),
		)
		frappe.throw("Failed to submit vendor rating. Please try again.")


# ---------------------------------------------------------------------------
# 3. get_vendor_dashboard
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_vendor_dashboard(supplier):
	"""Return aggregated dashboard metrics for a supplier.

	Args:
		supplier (str): Supplier name/link value.

	Returns:
		dict: Dashboard metrics dict.
	"""
	try:
		_mandatory(supplier, "supplier")

		# Verify caller has at least read access to this Supplier.
		if not frappe.has_permission("Supplier", "read", supplier):
			frappe.throw(
				f"You do not have permission to view data for supplier '{supplier}'.",
				frappe.PermissionError,
			)

		po_data = frappe.db.sql(
			"""
			SELECT COUNT(name) AS total_pos, SUM(base_grand_total) AS total_po_value
			FROM `tabPurchase Order`
			WHERE supplier = %s AND docstatus = 1
			""",
			(supplier,),
			as_dict=True,
		)[0]

		pr_data = frappe.db.sql(
			"""
			SELECT COUNT(name) AS total_receipts
			FROM `tabPurchase Receipt`
			WHERE supplier = %s AND docstatus = 1
			""",
			(supplier,),
			as_dict=True,
		)[0]

		pending_data = frappe.db.sql(
			"""
			SELECT COUNT(name) AS pending_receipts
			FROM `tabPurchase Order`
			WHERE supplier = %s AND docstatus = 1 AND per_received < 100
			""",
			(supplier,),
			as_dict=True,
		)[0]

		inv_data = frappe.db.sql(
			"""
			SELECT
				SUM(base_grand_total)   AS total_invoiced,
				SUM(outstanding_amount) AS outstanding_amount
			FROM `tabPurchase Invoice`
			WHERE supplier = %s AND docstatus = 1
			""",
			(supplier,),
			as_dict=True,
		)[0]

		# Rating breakdown — per-type averages for display.
		rating_rows = frappe.db.sql(
			"""
			SELECT rating_type, AVG(score) AS avg_score
			FROM `tabVendor Rating Log`
			WHERE supplier = %s
			GROUP BY rating_type
			""",
			(supplier,),
			as_dict=True,
		)
		rating_breakdown = {r.rating_type: r.avg_score for r in rating_rows}

		# Use the same weighted average as the supplier record — read directly
		# from the stored value so the dashboard is always consistent with the
		# supplier card.
		supplier_rating_raw = frappe.db.get_value(
			"Supplier", supplier, "custom_vendor_rating"
		) or 0.0
		avg_rating = flt(supplier_rating_raw) * 5  # convert 0–1 → 1–5 scale

		recent_ratings = frappe.db.sql(
			"""
			SELECT name, rating_date, rating_type, score, remarks
			FROM `tabVendor Rating Log`
			WHERE supplier = %s
			ORDER BY creation DESC
			LIMIT 10
			""",
			(supplier,),
			as_dict=True,
		)

		return {
			"total_pos":           po_data.total_pos or 0,
			"total_po_value":      po_data.total_po_value or 0.0,
			"total_receipts":      pr_data.total_receipts or 0,
			"pending_receipts":    pending_data.pending_receipts or 0,
			"avg_rating":          avg_rating,
			"rating_breakdown":    rating_breakdown,
			"recent_ratings":      recent_ratings,
			"total_invoiced":      inv_data.total_invoiced or 0.0,
			"outstanding_amount":  inv_data.outstanding_amount or 0.0,
		}

	except (frappe.ValidationError, frappe.PermissionError):
		raise
	except Exception:
		frappe.log_error(
			title="get_vendor_dashboard Error",
			message=frappe.get_traceback(),
		)
		frappe.throw("Failed to fetch vendor dashboard. Please try again.")


# ---------------------------------------------------------------------------
# 4. get_onboarding_status_summary
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_onboarding_status_summary():
	"""Return a summary of Vendor Onboarding records by status."""
	try:
		counts = frappe.db.sql(
			"""
			SELECT onboarding_status, COUNT(name) AS count
			FROM `tabVendor Onboarding`
			GROUP BY onboarding_status
			""",
			as_dict=True,
		)

		status_map = {row.onboarding_status: row.count for row in counts}

		total_pending  = status_map.get("Under Review", 0) + status_map.get("Draft", 0)
		total_approved = status_map.get("Approved", 0)
		total_rejected = status_map.get("Rejected", 0)

		recent_submissions = frappe.db.sql(
			"""
			SELECT name, supplier_name, company_name, onboarding_status, creation
			FROM `tabVendor Onboarding`
			ORDER BY creation DESC
			LIMIT 10
			""",
			as_dict=True,
		)

		return {
			"total_pending":       total_pending,
			"total_approved":      total_approved,
			"total_rejected":      total_rejected,
			"recent_submissions":  recent_submissions,
		}

	except (frappe.ValidationError, frappe.PermissionError):
		raise
	except Exception:
		frappe.log_error(
			title="get_onboarding_status_summary Error",
			message=frappe.get_traceback(),
		)
		frappe.throw("Failed to fetch onboarding summary. Please try again.")
