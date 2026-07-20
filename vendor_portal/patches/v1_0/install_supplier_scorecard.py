# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

# Criteria definitions matching the custom rating dimensions
SCORECARD_CRITERIA = [
    {
        "criteria_name": "Delivery Timeliness",
        "max_score": 100,
        "weight": 40,
        "formula": "({on_time_shipment_num} / {total_shipments} if {total_shipments} > 0 else 1) * 100",
    },
    {
        "criteria_name": "Quality (Acceptance Rate)",
        "max_score": 100,
        "weight": 30,
        "formula": "({total_accepted_items} / {total_received_items} if {total_received_items} > 0 else 1) * 100",
    },
    {
        "criteria_name": "Pricing (Cost Efficiency)",
        "max_score": 100,
        "weight": 30,
        "formula": "({cost_of_on_time_shipments} / {tot_cost_shipments} if {tot_cost_shipments} > 0 else 1) * 100",
    },
]

# Standing thresholds map to old custom rating scale:
#   Old 1-5 scale: 3.0/5 = 60%. Excellent=80-100, Average=60-80, Poor=40-60, Very Poor=0-40
SCORECARD_STANDINGS = [
    {
        "standing_name": "Excellent",
        "min_grade": 80.0,
        "max_grade": 100.0,
        "standing_color": "Blue",
        "warn_rfqs": 0,
        "warn_pos": 0,
        "prevent_rfqs": 0,
        "prevent_pos": 0,
        "notify_supplier": 0,
        "notify_employee": 0,
    },
    {
        "standing_name": "Average",
        "min_grade": 60.0,
        "max_grade": 80.0,
        "standing_color": "Green",
        "warn_rfqs": 0,
        "warn_pos": 0,
        "prevent_rfqs": 0,
        "prevent_pos": 0,
        "notify_supplier": 0,
        "notify_employee": 0,
    },
    {
        "standing_name": "Poor",
        "min_grade": 40.0,
        "max_grade": 60.0,
        "standing_color": "Yellow",
        "warn_rfqs": 1,
        "warn_pos": 1,
        "prevent_rfqs": 0,
        "prevent_pos": 0,
        "notify_supplier": 0,
        "notify_employee": 0,
    },
    {
        "standing_name": "Very Poor",
        "min_grade": 0.0,
        "max_grade": 40.0,
        "standing_color": "Red",
        "warn_rfqs": 0,
        "warn_pos": 0,
        "prevent_rfqs": 1,
        "prevent_pos": 1,
        "notify_supplier": 0,
        "notify_employee": 0,
    },
]


def execute():
    """Install Supplier Scorecard infrastructure for all suppliers.

    1. Install default scorecard variables and standings (from ERPNext)
    2. Create vendor-portal-specific criteria
    3. Create a Supplier Scorecard for each Supplier that has purchase history
    4. Generate initial scorecard periods
    """
    _install_defaults()
    _create_criteria()
    _create_standings_if_missing()
    _create_scorecards_for_existing_suppliers()


def _install_defaults():
    """Call ERPNext's built-in installer to seed default variables and standings."""
    try:
        from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import (
            make_default_records,
        )

        make_default_records()
        frappe.logger().info(
            "Patch install_supplier_scorecard: default variables and standings installed"
        )
    except ImportError:
        frappe.logger().warning(
            "Patch install_supplier_scorecard: could not import make_default_records"
        )


def _create_criteria():
    """Create the 3 custom Supplier Scorecard Criteria if they don't exist."""
    for crit in SCORECARD_CRITERIA:
        if frappe.db.exists("Supplier Scorecard Criteria", crit["criteria_name"]):
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Supplier Scorecard Criteria",
                "criteria_name": crit["criteria_name"],
                "max_score": crit["max_score"],
                "formula": crit["formula"],
                "weight": crit["weight"],
            }
        )
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert()
        frappe.logger().info(
            f"Patch install_supplier_scorecard: created criteria '{crit['criteria_name']}'"
        )


def _create_standings_if_missing():
    """Create custom standings with vendor-portal thresholds if they don't exist."""
    for st in SCORECARD_STANDINGS:
        if frappe.db.exists("Supplier Scorecard Standing", st["standing_name"]):
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Supplier Scorecard Standing",
                **st,
            }
        )
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert()
        frappe.logger().info(
            f"Patch install_supplier_scorecard: created standing '{st['standing_name']}'"
        )


def _create_scorecards_for_existing_suppliers():
    """Create a Supplier Scorecard for every Supplier that has purchase history
    or a custom_vendor_category set.  Generates initial scorecard periods."""
    suppliers = frappe.get_all(
        "Supplier",
        filters={"disabled": 0},
        fields=["name", "custom_vendor_rating", "creation"],
        order_by="creation asc",
    )

    if not suppliers:
        frappe.logger().info(
            "Patch install_supplier_scorecard: no suppliers found — skipping scorecard creation"
        )
        return

    created = 0
    for s in suppliers:
        if frappe.db.exists("Supplier Scorecard", {"supplier": s.name}):
            continue

        # Only create scorecards for suppliers with purchase history
        has_pos = frappe.db.count(
            "Purchase Order",
            {"supplier": s.name, "docstatus": 1},
        )
        if not has_pos:
            # Check if they have a vendor category (implies intent to rate)
            has_category = frappe.db.get_value(
                "Supplier", s.name, "custom_vendor_category"
            )
            if not has_category:
                continue

        try:
            _create_single_scorecard(s)
            created += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"install_supplier_scorecard: failed for supplier {s.name}",
            )

    frappe.logger().info(
        f"Patch install_supplier_scorecard: created {created} supplier scorecard(s)"
    )


def _create_single_scorecard(supplier):
    """Create a Supplier Scorecard document for a single supplier and
    generate initial periods."""
    # Convert old custom_vendor_rating (0-1) to initial score (0-100)
    old_rating = flt(supplier.get("custom_vendor_rating") or 0)
    initial_score = old_rating * 100  # 0.75 → 75

    scorecard = frappe.get_doc(
        {
            "doctype": "Supplier Scorecard",
            "supplier": supplier["name"],
            "period": "Per Month",
            "weighting_function": "{total_score} * max(0, min(1, (12 - {period_number}) / 12))",
            "criteria": [
                {
                    "criteria_name": "Delivery Timeliness",
                    "weight": 40,
                },
                {
                    "criteria_name": "Quality (Acceptance Rate)",
                    "weight": 30,
                },
                {
                    "criteria_name": "Pricing (Cost Efficiency)",
                    "weight": 30,
                },
            ],
            "standings": SCORECARD_STANDINGS,
            "supplier_score": initial_score if initial_score > 0 else 100,
        }
    )
    scorecard.flags.ignore_permissions = True
    scorecard.flags.ignore_mandatory = True
    scorecard.insert()

    # Set the initial standing based on the old rating
    scorecard.update_standing()
    scorecard.save()

    # Generate Supplier Scorecard Periods from existing transaction data
    # Use a shorter timeout since this may take time
    try:
        from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import (
            make_all_scorecards,
        )

        frappe.enqueue(
            make_all_scorecards,
            docname=scorecard.name,
            queue="long",
            timeout=300,
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"install_supplier_scorecard: could not enqueue period generation for {supplier['name']}",
        )

    frappe.logger().info(
        f"  → Scorecard created for {supplier['name']} (initial score: {initial_score})"
    )
