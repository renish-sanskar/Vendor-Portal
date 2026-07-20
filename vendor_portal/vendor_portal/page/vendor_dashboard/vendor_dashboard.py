# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_rating_distribution():
	"""Returns histogram data: count of suppliers in each scorecard bucket."""
	buckets = [
		{"min": 0, "max": 20, "label": "0-20 (Critical)"},
		{"min": 20, "max": 40, "label": "20-40 (Very Poor)"},
		{"min": 40, "max": 60, "label": "40-60 (Poor)"},
		{"min": 60, "max": 80, "label": "60-80 (Average)"},
		{"min": 80, "max": 101, "label": "80-100 (Excellent)"},
	]

	rows = frappe.db.sql(
		"""
		SELECT sc.supplier_score
		FROM `tabSupplier Scorecard` sc
		JOIN `tabSupplier` s ON s.name = sc.supplier
		WHERE s.disabled = 0
	""",
		as_dict=1,
	)

	scores = [flt(r.supplier_score) for r in rows if r.supplier_score is not None]

	labels = []
	counts = []
	for b in buckets:
		c = sum(1 for s in scores if b["min"] <= s < b["max"])
		labels.append(b["label"])
		counts.append(c)

	return {"labels": labels, "datasets": [{"name": "Suppliers", "values": counts}]}


@frappe.whitelist()
def get_onboarding_pipeline():
	"""Returns count of Vendor Onboardings grouped by status."""
	rows = frappe.db.sql(
		"""
		SELECT onboarding_status, COUNT(*) AS count
		FROM `tabVendor Onboarding`
		GROUP BY onboarding_status
		ORDER BY FIELD(onboarding_status, 'Draft', 'Under Review', 'Approved', 'Rejected')
	""",
		as_dict=1,
	)

	labels = [r.onboarding_status for r in rows]
	counts = [r.count for r in rows]

	return {"labels": labels, "datasets": [{"name": "Onboardings", "values": counts}]}


@frappe.whitelist()
def get_po_volume_by_category():
	"""Returns total PO value per Vendor Category."""
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(s.custom_vendor_category, 'Uncategorized') AS category,
			SUM(po.base_grand_total) AS total_value
		FROM `tabPurchase Order` po
		JOIN `tabSupplier` s ON s.name = po.supplier
		WHERE po.docstatus = 1
		GROUP BY s.custom_vendor_category
		ORDER BY total_value DESC
	""",
		as_dict=1,
	)

	labels = [r.category for r in rows]
	values = [flt(r.total_value) for r in rows]

	return {"labels": labels, "datasets": [{"name": "PO Value", "values": values}]}


@frappe.whitelist()
def get_delivery_trend():
	"""Returns monthly average Supplier Scorecard Period score for the last 12 months."""
	rows = frappe.db.sql(
		"""
		SELECT
			DATE_FORMAT(scp.end_date, '%Y-%m') AS month,
			AVG(scp.total_score) AS avg_score
		FROM `tabSupplier Scorecard Period` scp
		WHERE scp.docstatus = 1
			AND scp.end_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
		GROUP BY month
		ORDER BY month ASC
	""",
		as_dict=1,
	)

	labels = [r.month for r in rows]
	scores = [flt(r.avg_score) for r in rows]

	return {"labels": labels, "datasets": [{"name": "Avg Score", "values": scores}]}
