# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt
#
# vendor_portal/www/vendor-register.py
#
# Controller for the public /vendor-register web page.
# No authentication required — this page is intentionally guest-accessible so
# prospective vendors can submit onboarding applications without a Desk login.
#
# Frappe auto-discovers this file because it lives in the `www/` directory and
# pairs with vendor-register.html in the same folder.
#
# Context variables injected into the Jinja template:
#   categories (list[dict])  — active Vendor Category records {name, category_name}
#   success     (bool)       — True after a successful submission (redirect param)
#   error       (str)        — Error message to surface in the form (redirect param)

import frappe

# Mark the page as publicly accessible (no login wall).
no_cache = 1
no_sitemap = 1


def get_context(context):
    """Inject template context for the vendor registration page."""

    # ── Vendor Categories ──────────────────────────────────────────────────
    # frappe.get_all() honours role-based permissions and returns [] for guests
    # because Vendor Category has no Guest read permission in its DocType JSON.
    #
    # Fix: temporarily elevate to Administrator only for this one read,
    # then restore the original session user.  This is safe because:
    #   • We only read category_name / name (non-sensitive labels).
    #   • The elevation lasts only for the duration of this call.
    _original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        context.categories = frappe.get_all(
            "Vendor Category",
            filters={"is_active": 1},
            fields=["name", "category_name"],
            order_by="category_name asc",
            ignore_permissions=True,
        )
    except Exception:
        frappe.log_error(
            title="vendor-register: failed to fetch categories",
            message=frappe.get_traceback(),
        )
        context.categories = []
    finally:
        frappe.set_user(_original_user)

    # ── Flash messages from redirect params ────────────────────────────────
    context.success = frappe.form_dict.get("success") == "1"
    context.error = frappe.form_dict.get("error") or ""

    # ── Page meta ──────────────────────────────────────────────────────────
    context.title = "Vendor Registration – Apply to Become a Supplier"
    context.no_breadcrumbs = True
