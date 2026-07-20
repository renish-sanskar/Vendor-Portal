# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute():
	"""Recalculate custom_vendor_rating and custom_total_rating_count for all
	suppliers using the weighted-average formula from tasks.py.

	Uses default weights (Delivery=0.3, Quality=0.3, Pricing=0.2,
	Communication=0.2) if Vendor Portal Settings are not available.
	"""
	weight_map = _get_weights()
	suppliers = frappe.db.get_all(
		"Supplier",
		filters={"disabled": 0},
		fields=["name", "supplier_name"],
	)

	if not suppliers:
		frappe.logger().info("Patch v1_0/recalculate_vendor_ratings: no suppliers found")
		return

	updated = 0
	for s in suppliers:
		try:
			_recalculate(s.name, weight_map)
			updated += 1
		except Exception:
			frappe.log_error(
				f"Patch v1_0/recalculate_vendor_ratings: error for supplier {s.name}",
				frappe.get_traceback(),
			)

	frappe.logger().info(
		f"Patch v1_0/recalculate_vendor_ratings: {updated}/{len(suppliers)} suppliers updated"
	)


def _get_weights():
	"""Load rating weights from Vendor Portal Settings or use defaults."""
	try:
		settings = frappe.get_single("Vendor Portal Settings")
		return {
			"Delivery":      flt(settings.rating_weight_delivery)      or 0.30,
			"Quality":       flt(settings.rating_weight_quality)       or 0.30,
			"Pricing":       flt(settings.rating_weight_pricing)       or 0.20,
			"Communication": flt(settings.rating_weight_communication) or 0.20,
		}
	except Exception:
		return {
			"Delivery": 0.30,
			"Quality":  0.30,
			"Pricing":  0.20,
			"Communication": 0.20,
		}


def _recalculate(supplier_id, weight_map):
	"""Fetch all Vendor Rating Log entries for a supplier and update their
	custom_vendor_rating and custom_total_rating_count."""
	logs = frappe.db.get_all(
		"Vendor Rating Log",
		filters={"supplier": supplier_id},
		fields=["rating_type", "score"],
	)

	if not logs:
		return  # No logs — leave the supplier untouched

	# Accumulate scores per rating type
	type_scores = {}
	for log in logs:
		rtype = log.get("rating_type") or "Delivery"
		score = flt(log.get("score") or 0)
		type_scores.setdefault(rtype, []).append(score)

	weighted_sum = 0.0
	effective_weight = 0.0

	for rtype, weight in weight_map.items():
		if rtype in type_scores:
			avg = sum(type_scores[rtype]) / len(type_scores[rtype])
			weighted_sum += avg * weight
			effective_weight += weight

	if effective_weight == 0:
		return

	final_rating_1to5 = round(weighted_sum / effective_weight, 2)

	# custom_vendor_rating is a Rating fieldtype — store as 0–1
	final_rating_0to1 = final_rating_1to5 / 5.0

	frappe.db.set_value(
		"Supplier",
		supplier_id,
		{
			"custom_vendor_rating": final_rating_0to1,
			"custom_total_rating_count": len(logs),
		},
		update_modified=False,
	)
