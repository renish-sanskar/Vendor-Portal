# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt
#
# vendor_portal/www/vendor-status.py
#
# Controller for the public /vendor-status web page.
# Allows vendors to look up their application status without logging in.

import frappe

no_cache = 1
no_sitemap = 1


def get_context(context):
    """Inject template context for the vendor status look-up page."""
    context.title = "Check Vendor Application Status | Vendor Portal"
    context.no_breadcrumbs = True

    # Values re-populated if the user submitted the look-up form
    context.lookup_email = frappe.form_dict.get("email", "")
    context.lookup_ref = frappe.form_dict.get("ref", "")
    context.result = None
    context.error = ""

    if context.lookup_email and context.lookup_ref:
        try:
            context.result = _fetch_status(context.lookup_email, context.lookup_ref)
        except frappe.ValidationError as e:
            context.error = str(e)
        except Exception:
            frappe.log_error(
                title="Vendor Status Lookup Error",
                message=frappe.get_traceback(),
            )
            context.error = "An unexpected error occurred. Please try again."


def _fetch_status(email: str, ref: str) -> dict | None:
    """Return a sanitised status dict for the given email + reference ID pair."""
    doc = frappe.db.get_value(
        "Vendor Onboarding",
        {"name": ref.strip(), "email": email.strip()},
        [
            "name",
            "supplier_name",
            "company_name",
            "email",
            "vendor_category",
            "onboarding_status",
            "creation",
            "review_date",
            "rejection_reason",
            "linked_supplier",
        ],
        as_dict=True,
    )
    if not doc:
        frappe.throw(
            "No application found for the provided Reference ID and Email. "
            "Please double-check and try again."
        )
    return doc
