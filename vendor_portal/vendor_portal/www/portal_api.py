# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt
#
# vendor_portal/vendor_portal/www/portal_api.py
#
# Whitelisted guest API endpoints consumed by the self-service web pages:
#   • /vendor-register  → submit_vendor_application
#
# All methods are decorated with allow_guest=True so that unauthenticated
# visitors (prospective vendors) can call them without a session cookie.

import frappe
from frappe.utils import validate_email_address
import re
import json
from frappe.utils.file_manager import save_file


@frappe.whitelist(allow_guest=True)
def get_vendor_categories():
    """Return active Vendor Category records for the public registration form.

    Runs as Administrator so that guest users (no session) can fetch the list
    without needing a Guest read permission on the Vendor Category DocType.
    """
    try:
        frappe.set_user("Administrator")
        cats = frappe.get_all(
            "Vendor Category",
            filters={"is_active": 1},
            fields=["name", "category_name"],
            order_by="category_name asc",
            ignore_permissions=True,
        )
    finally:
        frappe.set_user("Guest")
    return cats


@frappe.whitelist(allow_guest=True)
def submit_vendor_application(
    supplier_name,
    company_name,
    email,
    phone,
    vendor_category,
    address_line_1,
    city,
    state,
    pincode=None,
    gst_number=None,
    pan_number=None,
    contact_person=None,
    bank_name=None,
    bank_account_number=None,
    ifsc_code=None,
    documents=None,
):
    """
    Create a new Vendor Onboarding record from the public self-service portal.

    Validates all inputs on the server side (mirrors client-side checks so the
    API cannot be bypassed via direct calls).

    Returns:
        dict: { "application_id": "<VOB-YYYY-NNNNN>" }

    Raises frappe.ValidationError on any bad input — the JSON error message is
    surfaced directly to the vendor in the registration form.
    """
    # ── 1. Mandatory field checks ─────────────────────────────────────────
    _require(supplier_name, "Supplier Name")
    _require(company_name, "Company Name")
    _require(email, "Email")
    _require(phone, "Phone")
    _require(vendor_category, "Vendor Category")
    _require(address_line_1, "Address Line 1")
    _require(city, "City")
    _require(state, "State")

    # ── 2. Email format ───────────────────────────────────────────────────
    if not validate_email_address(email):
        frappe.throw(f"'{email}' is not a valid email address.")

    # ── 3. GST format (optional) ──────────────────────────────────────────
    gst_number = (gst_number or "").strip().upper() or None
    if gst_number:
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(pattern, gst_number):
            frappe.throw(
                "GST Number is not valid. "
                "Expected format: 2-digit state code + 10-char PAN + 1 entity code + Z + 1 check digit "
                "(e.g. 27AAAPL1234C1Z5)."
            )

    # ── 4. PAN format (optional) ──────────────────────────────────────────
    pan_number = (pan_number or "").strip().upper() or None
    if pan_number:
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan_number):
            frappe.throw(
                "PAN Number is not valid. "
                "Expected format: 5 letters + 4 digits + 1 letter (e.g. AAAPL1234C)."
            )

    # ── 5. Vendor Category exists ─────────────────────────────────────────
    if not frappe.db.exists("Vendor Category", vendor_category):
        frappe.throw(f"Vendor Category '{vendor_category}' does not exist.")

    # ── 6. Duplicate email guard ──────────────────────────────────────────
    existing_by_email = frappe.db.get_value(
        "Vendor Onboarding",
        {"email": email, "docstatus": ("!=", 2)},
        "name",
    )
    if existing_by_email:
        frappe.throw(
            f"An application with email '{email}' already exists "
            f"(Ref: {existing_by_email}). "
            "Please use /vendor-status to track it."
        )

    # ── 7. Duplicate GST guard ────────────────────────────────────────────
    if gst_number:
        dup_gst = frappe.db.get_value(
            "Vendor Onboarding",
            {"gst_number": gst_number, "docstatus": ("!=", 2)},
            "name",
        )
        if dup_gst:
            frappe.throw(
                f"An application with GST Number '{gst_number}' already exists "
                f"(Ref: {dup_gst})."
            )

    # ── 8. Create Vendor Onboarding record ────────────────────────────────
    doc = frappe.get_doc(
        {
            "doctype": "Vendor Onboarding",
            "supplier_name": supplier_name.strip(),
            "company_name": company_name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
            "vendor_category": vendor_category,
            "address_line_1": address_line_1.strip(),
            "city": city.strip(),
            "state": state.strip(),
            "pincode": (pincode or "").strip() or None,
            "gst_number": gst_number,
            "pan_number": pan_number,
            "contact_person": (contact_person or "").strip() or None,
            "bank_name": (bank_name or "").strip() or None,
            "bank_account_number": (bank_account_number or "").strip() or None,
            "ifsc_code": (ifsc_code or "").strip() or None,
            "onboarding_status": "Draft",
        }
    )
    # Insert without permissions check — this is the intentional guest-submit path.
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = True
    doc.insert(ignore_permissions=True)
    doc.flags.ignore_validate = False
    
    # ── 9. Attach Documents ───────────────────────────────────────────────
    if documents:
        try:
            docs = json.loads(documents)
            for d in docs:
                filename = d.get("filename")
                data = d.get("data")
                if filename and data:
                    # Save the base64 file to the filesystem, linked to this onboarding record
                    file_doc = save_file(
                        fname=filename,
                        content=data,
                        dt="Vendor Onboarding",
                        dn=doc.name,
                        decode=True,
                        is_private=1
                    )
                    
                    # Append to the child table
                    doc.append("documents", {
                        "document_type": d.get("document_type", "Other"),
                        "document_file": file_doc.file_url,
                        "is_verified": 0
                    })
                    
        except Exception as e:
            frappe.log_error(title="Failed to attach documents", message=str(e))
            # Don't throw here, the record is created. Let purchase managers deal with it.

    # ── 10. Final Save to trigger validation ──────────────────────────────
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"application_id": doc.name}


# ── Private helpers ───────────────────────────────────────────────────────────

def _require(value, label):
    """Raise a readable error if a mandatory field is blank."""
    if not value or (isinstance(value, str) and not value.strip()):
        frappe.throw(f"'{label}' is required.")
