# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_supplier_comparison(item_code: str, qty: int = 1):
    """Return a side‑by‑side comparison of all suppliers for *item_code*.

    Returns a list of dicts sorted by scorecard score (descending), one per
    supplier that has supplied this item.  Each dict contains:

      supplier, supplier_name, vendor_category,
      avg_rate, last_rate, rate_history (list of {date, rate, po}),
      total_supplied_qty, total_po_count,
      delivery_score, quality_score,
      scorecard_score, scorecard_status, scorecard_color,
      on_time_pct, short_delivery_count
    """
    if not item_code or not item_code.strip():
        frappe.throw(_("Item code is required."))

    suppliers = frappe.db.sql(
        """
        SELECT
            s.name                                      AS supplier,
            s.supplier_name                             AS supplier_name,
            s.custom_vendor_category                    AS vendor_category,
            s.custom_vendor_rating                      AS custom_rating,
            sc.supplier_score                           AS scorecard_score,
            sc.status                                   AS scorecard_status,
            sc.indicator_color                          AS scorecard_color,
            COALESCE(receipt_stats.total_receipts, 0)  AS total_pos,
            COALESCE(receipt_stats.total_value, 0)     AS total_po_value,
            COALESCE(receipt_stats.total_supplied_qty, 0) AS total_supplied_qty,
            receipt_stats.avg_rate,
            receipt_stats.last_rate,
            dlv.avg_delivery_score                      AS delivery_score,
            qlt.avg_quality_score                       AS quality_score,
            dlv.on_time_pct,
            dlv.short_delivery_count
        FROM `tabSupplier` s
        JOIN (
            SELECT
                pr.supplier,
                COUNT(DISTINCT pr.name)          AS total_receipts,
                SUM(pr.base_grand_total)         AS total_value,
                SUM(pri.qty)                     AS total_supplied_qty,
                AVG(pri.rate)                    AS avg_rate,
                (
                    SELECT pri2.rate
                    FROM `tabPurchase Receipt Item` pri2
                    JOIN `tabPurchase Receipt` pr2 ON pri2.parent = pr2.name
                    WHERE pri2.item_code = %(item)s
                      AND pr2.supplier = pr.supplier
                      AND pr2.docstatus = 1
                    ORDER BY pr2.posting_date DESC, pr2.creation DESC
                    LIMIT 1
                )                                AS last_rate
            FROM `tabPurchase Receipt` pr
            JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
            WHERE pri.item_code = %(item)s
              AND pr.docstatus = 1
            GROUP BY pr.supplier
        ) receipt_stats ON receipt_stats.supplier = s.name
        LEFT JOIN `tabSupplier Scorecard` sc ON sc.supplier = s.name
        LEFT JOIN (
            SELECT
                supplier,
                AVG(CASE WHEN rating_type = 'Delivery' THEN score END) AS avg_delivery_score,
                COUNT(CASE WHEN rating_type = 'Delivery' AND score >= 3 THEN 1 END) * 100.0
                    / NULLIF(COUNT(CASE WHEN rating_type = 'Delivery' THEN 1 END), 0) AS on_time_pct,
                SUM(CASE WHEN rating_type = 'Delivery' AND score < 3 THEN 1 ELSE 0 END) AS short_delivery_count
            FROM `tabVendor Rating Log`
            GROUP BY supplier
        ) dlv ON dlv.supplier = s.name
        LEFT JOIN (
            SELECT
                supplier,
                AVG(CASE WHEN rating_type = 'Quality' THEN score END) AS avg_quality_score
            FROM `tabVendor Rating Log`
            GROUP BY supplier
        ) qlt ON qlt.supplier = s.name
        ORDER BY COALESCE(sc.supplier_score, 0) DESC
        """,
        {"item": item_code},
        as_dict=1,
    )

    # Enrich each supplier with price history
    for row in suppliers:
        row["rate_history"] = _get_rate_history(item_code, row.supplier)
        row["custom_rating"] = flt(row.get("custom_rating", 0)) * 5

    return suppliers


def _get_rate_history(item_code: str, supplier: str) -> list[dict]:
    """Return the last 5 PO rates (with date) for *item_code* from *supplier*."""
    rows = frappe.db.sql(
        """
        SELECT pri.rate, pr.transaction_date AS date, pr.name AS po
        FROM `tabPurchase Order Item` pri
        JOIN `tabPurchase Order` pr ON pri.parent = pr.name
        WHERE pri.item_code = %(item)s
          AND pr.supplier = %(supplier)s
          AND pr.docstatus = 1
        ORDER BY pr.transaction_date DESC, pr.creation DESC
        LIMIT 5
        """,
        {"item": item_code, "supplier": supplier},
        as_dict=1,
    )

    return rows
