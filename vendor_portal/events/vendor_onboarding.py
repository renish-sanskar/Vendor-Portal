# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe


def send_welcome_email(doc, method):
	"""Send an acknowledgement email when a Vendor Onboarding application is
	submitted. Uses the onboarding's email field as the recipient and renders
	the welcome template with doc context."""
	if not doc.email:
		frappe.log_error(
			title="Vendor Onboarding — Missing Email",
			message=f"Cannot send welcome email for {doc.name}: no email address set.",
		)
		return

	context = {
		"doc": doc,
		"company": frappe.defaults.get_global_default("company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or "Company",
	}

	subject = f"Application Received — {doc.company_name or doc.supplier_name}"

	try:
		frappe.sendmail(
			recipients=[doc.email],
			subject=subject,
			message=frappe.render_template(
				"vendor_portal/templates/emails/vendor_onboarding_welcome.html",
				context,
			),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	except Exception as e:
		frappe.log_error(
			title="Vendor Onboarding — Welcome Email Failed",
			message=f"Failed to send welcome email for {doc.name}: {e}",
		)
