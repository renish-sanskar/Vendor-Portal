# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe


def check_blacklist_status(doc, method):
	"""Detect changes to custom_is_blacklisted and trigger downstream
	actions — flag relevant POs and notify Purchase Managers."""
	before = doc.get_doc_before_save()
	if not before:
		return

	was_blacklisted = before.get("custom_is_blacklisted")
	is_blacklisted = doc.get("custom_is_blacklisted")

	if was_blacklisted == is_blacklisted:
		return

	if is_blacklisted:
		_handle_blacklisted(doc)
	else:
		_handle_unblacklisted(doc)


def _handle_blacklisted(doc):
	"""Supplier was just blacklisted — flag open POs and notify managers."""
	reason = doc.get("custom_blacklist_reason") or "No reason provided"

	# Flag all open (Draft + Submitted + not cancelled) POs
	open_pos = frappe.db.get_all(
		"Purchase Order",
		filters={
			"supplier": doc.name,
			"docstatus": ["!=", 2],
			"status": ["!=", "Completed"],
		},
		pluck="name",
	)

	for po_name in open_pos:
		po_doc = frappe.get_doc("Purchase Order", po_name)
		po_doc.add_comment(
			"Info",
			f"Supplier {doc.supplier_name} has been blacklisted. "
			f"Reason: {reason}. Please review this Purchase Order.",
		)

	# Notify users with Purchase Manager role
	managers = _get_purchase_managers()
	if managers:
		subject = f"Supplier Blacklisted — {doc.supplier_name}"
		message = (
			f"Supplier <strong>{doc.supplier_name}</strong> has been "
			f"blacklisted.<br><br>"
			f"<strong>Reason:</strong> {reason}<br><br>"
			f"<strong>Affected POs:</strong> {len(open_pos)} open "
			f"Purchase Order(s) have been flagged.<br><br>"
			f"Please review and take necessary action."
		)

		frappe.sendmail(
			recipients=managers,
			subject=subject,
			message=message,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)

	frappe.logger().info(
		f"Supplier {doc.name} blacklisted. {len(open_pos)} POs flagged."
	)


def _handle_unblacklisted(doc):
	"""Supplier was removed from blacklist — notify managers."""
	managers = _get_purchase_managers()
	if not managers:
		return

	subject = f"Blacklist Removed — {doc.supplier_name}"
	message = (
		f"Supplier <strong>{doc.supplier_name}</strong> has been removed "
		f"from the blacklist and can resume normal operations."
	)

	frappe.sendmail(
		recipients=managers,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)

	frappe.logger().info(
		f"Supplier {doc.name} removed from blacklist."
	)


def _get_purchase_managers():
	"""Return list of email addresses for users with Purchase Manager role."""
	return frappe.db.get_all(
		"Has Role",
		filters={"role": "Purchase Manager", "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
