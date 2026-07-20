# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import csv
import io

import frappe
from frappe import _
from frappe.utils.background_jobs import enqueue


# ── Column definitions ───────────────────────────────────────────────────────
# Maps CSV column name → Vendor Onboarding fieldname
# (required fields are noted so the validator can check them)

CSV_COLUMNS = [
    ("supplier_name", True),
    ("company_name", True),
    ("email", True),
    ("phone", True),
    ("vendor_category", True),
    ("address_line_1", True),
    ("city", True),
    ("state", True),
    ("pincode", False),
    ("gst_number", False),
    ("pan_number", False),
    ("contact_person", False),
    ("bank_name", False),
    ("bank_account_number", False),
    ("ifsc_code", False),
]

REQUIRED_COLUMNS = [col for col, reqd in CSV_COLUMNS if reqd]


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def queue_bulk_vendor_import(csv_data: str):
    """Accept a CSV string, validate the header, and enqueue processing.

    *csv_data* — raw CSV text with a header row matching the expected columns.
    Returns ``{"job_name": "…", "total_rows": N}`` so the caller can poll
    progress via :meth:`get_import_progress`.
    """
    if not csv_data or not csv_data.strip():
        frappe.throw(_("CSV data is empty."))

    reader = csv.DictReader(io.StringIO(csv_data))
    if not reader.fieldnames:
        frappe.throw(_("CSV must have a header row."))

    header = [h.strip().lower() for h in reader.fieldnames]
    missing = [col for col in REQUIRED_COLUMNS if col not in header]
    if missing:
        frappe.throw(
            _("CSV header is missing required column(s): {0}").format(
                ", ".join(missing)
            )
        )

    rows = list(reader)
    if not rows:
        frappe.throw(_("CSV has a header but no data rows."))

    total_rows = len(rows)
    job_name = f"bulk_vendor_import__{frappe.generate_hash(length=8)}"

    # Store initial state in cache so get_import_progress can read it
    _set_progress(job_name, {
        "status": "queued",
        "total": total_rows,
        "processed": 0,
        "success": 0,
        "errors": [],
    })

    enqueue(
        method="vendor_portal.vendor_portal.vendor_portal.api.bulk_vendor_import._process_csv",
        queue="long",
        job_name=job_name,
        timeout=600,
        csv_data=csv_data,
        job_name_param=job_name,
    )

    frappe.response["job_name"] = job_name
    frappe.response["total_rows"] = total_rows
    frappe.response["message"] = _("Import queued with {0} rows.").format(total_rows)


@frappe.whitelist()
def get_import_progress(job_name: str):
    """Return the current progress for a queued bulk import."""
    progress = _get_progress(job_name)
    if not progress:
        frappe.throw(_("No import job found with name: {0}").format(job_name))
    return progress


# ─────────────────────────────────────────────────────────────────────────────
#  Background worker
# ─────────────────────────────────────────────────────────────────────────────


def _process_csv(csv_data: str, job_name_param: str):
    """Parse CSV rows and create Vendor Onboarding records.

    Runs inside a background worker (``frappe.enqueue``).
    Publishes realtime progress events to ``{job_name_param}:progress``.
    """
    _set_progress(job_name_param, {"status": "processing"})
    frappe.publish_realtime(f"{job_name_param}:progress", _get_progress(job_name_param))

    reader = csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)

    success = 0
    errors = []

    for idx, row in enumerate(rows):
        try:
            _validate_row(row)
            _create_onboarding(row)
            success += 1
        except Exception as e:
            errors.append({
                "row": idx + 2,  # 1‑based, skip header
                "supplier": row.get("supplier_name", ""),
                "error": str(e),
            })
            frappe.log_error(
                title=_("Bulk import row {0} failed").format(idx + 2),
                message=frappe.get_traceback(),
            )

        # Publish progress every 5 rows (or on last row)
        if (idx + 1) % 5 == 0 or idx == len(rows) - 1:
            _set_progress(job_name_param, {
                "processed": idx + 1,
                "success": success,
                "errors": errors,
            })
            frappe.publish_realtime(
                f"{job_name_param}:progress", _get_progress(job_name_param)
            )

    _set_progress(job_name_param, {
        "status": "completed",
        "processed": len(rows),
        "success": success,
        "errors": errors,
    })
    frappe.publish_realtime(f"{job_name_param}:progress", _get_progress(job_name_param))


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _validate_row(row: dict):
    """Check that all required fields are present and non‑empty."""
    missing = []
    for col in REQUIRED_COLUMNS:
        val = row.get(col, "").strip()
        if not val:
            missing.append(col)

    if not missing:
        return

    # Re-raise with a clean message (Frappe shows this in the error list)
    raise frappe.ValidationError(
        _("Row is missing required field(s): {0}").format(", ".join(missing))
    )


def _create_onboarding(row: dict):
    """Insert a single Vendor Onboarding document."""

    # Validate Vendor Category link exists
    vcat = row.get("vendor_category", "").strip()
    if vcat and not frappe.db.exists("Vendor Category", vcat):
        raise frappe.ValidationError(
            _("Vendor Category '{0}' does not exist.").format(vcat)
        )

    doc = frappe.get_doc({
        "doctype": "Vendor Onboarding",
        "supplier_name": row.get("supplier_name", "").strip(),
        "company_name": row.get("company_name", "").strip(),
        "email": row.get("email", "").strip(),
        "phone": row.get("phone", "").strip(),
        "vendor_category": vcat,
        "address_line_1": row.get("address_line_1", "").strip(),
        "city": row.get("city", "").strip(),
        "state": row.get("state", "").strip(),
        "pincode": row.get("pincode", "").strip(),
        "gst_number": row.get("gst_number", "").strip(),
        "pan_number": row.get("pan_number", "").strip(),
        "contact_person": row.get("contact_person", "").strip(),
        "bank_name": row.get("bank_name", "").strip(),
        "bank_account_number": row.get("bank_account_number", "").strip(),
        "ifsc_code": row.get("ifsc_code", "").strip(),
        "onboarding_status": "Draft",
    })

    doc.insert(ignore_permissions=True)
    doc.submit()


# ─────────────────────────────────────────────────────────────────────────────
#  Cache helpers (store progress so it survives across worker processes)
# ─────────────────────────────────────────────────────────────────────────────


def _cache_key(job_name: str) -> str:
    return f"bulk_vendor_import|{job_name}"


def _set_progress(job_name: str, data: dict):
    frappe.cache().set_value(_cache_key(job_name), data, expires_in_sec=3600)


def _get_progress(job_name: str):
    return frappe.cache().get_value(_cache_key(job_name))
