# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.utils import flt

RATING_KEYWORDS = {
	# Positive
	"excellent":     5.0,
	"outstanding":   5.0,
	"perfect":       5.0,
	"great":         4.5,
	"very good":     4.5,
	"good":          4.0,
	"reliable":      4.0,
	"consistent":    4.0,
	"satisfactory":  3.5,
	# Neutral
	"average":       3.0,
	"okay":          3.0,
	"fair":          3.0,
	# Negative — quality
	"poor quality":  2.0,
	"quality issue": 2.0,
	"defective":     1.5,
	"bad":           1.5,
	"terrible":      1.0,
	"unreliable":    2.0,
	# Negative — delivery
	"late delivery": 2.0,
	"delayed":       2.5,
	"very late":     1.5,
}


def execute():
	"""Scan Supplier comments for rating keywords and create Vendor Rating Log
	entries with estimated scores where none already exist."""
	suppliers = frappe.db.get_all(
		"Supplier",
		fields=["name", "supplier_name"],
	)

	if not suppliers:
		return

	created = 0
	for s in suppliers:
		try:
			created += _process_supplier_comments(s.name)
		except Exception:
			frappe.log_error(
				f"Patch v1_0/migrate_supplier_notes: error for supplier {s.name}",
				frappe.get_traceback(),
			)

	frappe.logger().info(
		f"Patch v1_0/migrate_supplier_notes: created {created} Vendor Rating Log(s)"
	)


def _process_supplier_comments(supplier_id):
	"""Look up Comment entries referencing this supplier, extract rating
	keywords, and create a best-effort Vendor Rating Log.  Returns the
	number of rating logs created."""
	comments = frappe.db.get_all(
		"Comment",
		filters={
			"reference_doctype": "Supplier",
			"reference_name": supplier_id,
		},
		fields=["name", "content", "owner", "creation"],
	)

	if not comments:
		return 0

	created = 0
	for comment in comments:
		text = (comment.get("content") or "").strip().lower()
		if not text:
			continue

		score, rating_type = _estimate_score(text)

		if score is None:
			continue

		# Guard: skip if a rating log already covers this period
		cutoff = frappe.utils.get_datetime(comment.creation).date()
		if frappe.db.exists(
			"Vendor Rating Log",
			{
				"supplier": supplier_id,
				"rating_type": rating_type,
				"rating_date": [">=", cutoff],
				"creation": ["<=", comment.creation + frappe.utils.timedelta(hours=1)],
			},
		):
			continue

		log = frappe.get_doc(
			{
				"doctype": "Vendor Rating Log",
				"supplier": supplier_id,
				"rating_type": rating_type,
				"score": score,
				"remarks": f"Migrated from comment {comment.name}: {comment.content[:200]}",
				"rating_date": cutoff,
			}
		)
		log.insert(ignore_permissions=True, ignore_mandatory=True)
		created += 1

	return created


def _estimate_score(text):
	"""Analyse comment text and return (score, rating_type) or (None, None)."""
	# Prefer the longest matching keyword for precision
	matches = []
	for keyword, score in RATING_KEYWORDS.items():
		idx = text.find(keyword)
		if idx != -1:
			matches.append((len(keyword), idx, keyword, score))

	if not matches:
		return None, None

	# Pick the first keyword match (highest up in the text, then longest)
	matches.sort(key=lambda m: (m[1], -m[0]))
	keyword = matches[0][2]
	score = matches[0][3]

	# Determine rating_type from keyword context
	delivery_keywords = {"late delivery", "delayed", "very late", "on-time", "on time"}
	quality_keywords  = {"defective", "quality issue", "poor quality"}

	if keyword in delivery_keywords:
		rating_type = "Delivery"
	elif keyword in quality_keywords:
		rating_type = "Quality"
	else:
		# General sentiment — default to Delivery for delivery-related
		# keywords, otherwise Communication as a catch-all
		if any(dk in text for dk in {"deliver", "shipment", "received", "dispatch"}):
			rating_type = "Delivery"
		else:
			rating_type = "Communication"

	return score, rating_type
