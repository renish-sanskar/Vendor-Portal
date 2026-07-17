# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def validate(doc, method):
	"""Check for short delivery — received qty < 90% of ordered qty per item.
	Sets doc.flags.has_short_delivery = True if any item falls short
	and adds a comment to the document."""
	if not doc.items:
		return

	# Skip short delivery checks for Purchase Returns
	if getattr(doc, "is_return", 0):
		return

	short_delivery = False
	for item in doc.items:
		if not item.purchase_order_item:
			continue

		# Get ordered qty from the linked PO item
		po_qty = frappe.db.get_value(
			"Purchase Order Item", item.purchase_order_item, "qty"
		)
		if not po_qty or po_qty <= 0:
			continue

		received_pct = (item.qty / po_qty) * 100
		if received_pct < 90:
			short_delivery = True
			doc.add_comment(
				"Info",
				f"Short delivery detected for {item.item_code}: "
				f"received {item.qty} of {int(po_qty)} ordered "
				f"({received_pct:.1f}%).",
			)

	if short_delivery:
		doc.flags.has_short_delivery = True


def on_submit(doc, method):
	"""Auto-create a Vendor Rating Log with rating_type = Delivery.
	Score logic:
	- 5: on-time AND full qty
	- 4: on-time BUT short delivery
	- 3: late (>2 days past expected delivery)
	- 2: late AND short delivery

	Skips creation if a Delivery rating log already exists for this PR
	(e.g. after cancel & re-submit).
	"""
	if not doc.items or not doc.supplier:
		return

	# Skip Delivery rating logic for Purchase Returns
	if getattr(doc, "is_return", 0):
		return

	# Guard: already rated — handles cancel & re-submit cycles
	if frappe.db.exists(
		"Vendor Rating Log",
		{"purchase_receipt": doc.name, "rating_type": "Delivery"},
	):
		return

	short_delivery = doc.flags.get("has_short_delivery", False)
	late = _is_late_delivery(doc)

	if late and short_delivery:
		score = 2
	elif late:
		score = 3
	elif short_delivery:
		score = 4
	else:
		score = 5

	# Resolve PO reference — use the most common PO across items if
	# items span multiple purchase orders.
	po_names = [item.purchase_order for item in doc.items if item.purchase_order]
	purchase_order = max(set(po_names), key=po_names.count) if po_names else None

	rating_log = frappe.get_doc(
		{
			"doctype": "Vendor Rating Log",
			"supplier": doc.supplier,
			"purchase_order": purchase_order,
			"purchase_receipt": doc.name,
			"rating_type": "Delivery",
			"score": score,
			"remarks": (
				f"Auto-rated on submission of PR {doc.name}. "
				f"Short delivery: {'Yes' if short_delivery else 'No'}, "
				f"Late: {'Yes' if late else 'No'}"
			),
		}
	)

	try:
		rating_log.insert(ignore_permissions=True, ignore_mandatory=True)
	except Exception as e:
		frappe.log_error(
			title="Vendor Rating Log Creation Failed",
			message=f"PR {doc.name}: {e}",
		)


def _is_late_delivery(doc):
	"""Check if the delivery was late by comparing PR posting_date
	against each item's expected_delivery_date from the linked PO.
	Returns True if any item is more than 2 days past its expected date."""
	posting_date = getdate(doc.posting_date)

	for item in doc.items:
		if not item.purchase_order_item:
			continue

		expected_date = frappe.db.get_value(
			"Purchase Order Item", item.purchase_order_item, "expected_delivery_date"
		)
		if not expected_date:
			continue

		expected_date = getdate(expected_date)
		# More than 2 days past expected → late
		if (posting_date - expected_date).days > 2:
			return True

	return False
