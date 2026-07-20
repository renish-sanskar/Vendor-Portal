# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}

	columns = _get_columns()
	conditions, po_clause, values = _build_conditions(filters)
	data = _get_data(conditions, po_clause, values)
	charts = _get_charts(data)

	return columns, data, None, charts


def _get_columns():
	return [
		{
			"fieldname": "supplier_name",
			"label": _("Supplier Name"),
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 180,
		},
		{
			"fieldname": "vendor_category",
			"label": _("Vendor Category"),
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"fieldname": "total_pos",
			"label": _("Total POs"),
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"fieldname": "total_po_value",
			"label": _("Total PO Value"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "scorecard_score",
			"label": _("Scorecard Score"),
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"fieldname": "scorecard_status",
			"label": _("Scorecard Status"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "avg_delivery_score",
			"label": _("Avg Delivery Score"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "avg_quality_score",
			"label": _("Avg Quality Score"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "avg_pricing_score",
			"label": _("Avg Pricing Score"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "overall_rating",
			"label": _("Custom Rating"),
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"fieldname": "total_receipts",
			"label": _("Total Receipts"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "on_time_delivery_pct",
			"label": _("On-Time Delivery %"),
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"fieldname": "short_delivery_count",
			"label": _("Short Delivery Count"),
			"fieldtype": "Int",
			"width": 150,
		},
	]


def _build_conditions(filters):
	conditions = []
	po_conditions = []
	values = {}

	if filters.get("vendor_category"):
		conditions.append("s.custom_vendor_category = %(vendor_category)s")
		values["vendor_category"] = filters["vendor_category"]

	if filters.get("supplier"):
		conditions.append("s.name = %(supplier)s")
		values["supplier"] = filters["supplier"]

	if filters.get("from_date"):
		po_conditions.append("po.transaction_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		po_conditions.append("po.transaction_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("minimum_rating"):
		values["min_rating"] = float(filters["minimum_rating"]) / 5.0
		conditions.append("s.custom_vendor_rating >= %(min_rating)s")

	where_clause = " AND ".join(conditions) if conditions else "1=1"
	po_clause = " AND " + " AND ".join(po_conditions) if po_conditions else ""
	return where_clause, po_clause, values


def _get_data(conditions, po_clause, values):
	sql = f"""
		SELECT
			s.name AS supplier_name,
			s.custom_vendor_category AS vendor_category,
			COALESCE(po_stats.total_pos, 0) AS total_pos,
			COALESCE(po_stats.total_po_value, 0) AS total_po_value,
			COALESCE(sc.supplier_score, 0) AS scorecard_score,
			COALESCE(sc.status, '') AS scorecard_status,
			COALESCE(rating_stats.avg_delivery, 0) AS avg_delivery_score,
			COALESCE(rating_stats.avg_quality, 0) AS avg_quality_score,
			COALESCE(rating_stats.avg_pricing, 0) AS avg_pricing_score,
			COALESCE(s.custom_vendor_rating * 5, 0) AS overall_rating,
			COALESCE(pr_stats.total_receipts, 0) AS total_receipts,
			CASE
				WHEN COALESCE(pr_stats.total_receipts, 0) > 0
				THEN ROUND(
					COALESCE(on_time_stats.on_time_count, 0) * 100.0
					/ pr_stats.total_receipts, 1
				)
				ELSE 0
			END AS on_time_delivery_pct,
			COALESCE(short_stats.short_count, 0) AS short_delivery_count
		FROM
			`tabSupplier` s
		LEFT JOIN `tabSupplier Scorecard` sc ON sc.supplier = s.name
		LEFT JOIN (
			SELECT po.supplier,
				COUNT(DISTINCT po.name) AS total_pos,
				SUM(po.base_grand_total) AS total_po_value
			FROM `tabPurchase Order` po
			WHERE po.docstatus = 1{po_clause}
			GROUP BY po.supplier
		) po_stats ON po_stats.supplier = s.name
		LEFT JOIN (
			SELECT supplier,
				COUNT(DISTINCT name) AS total_receipts
			FROM `tabPurchase Receipt`
			WHERE docstatus = 1
			GROUP BY supplier
		) pr_stats ON pr_stats.supplier = s.name
		LEFT JOIN (
			SELECT supplier,
				AVG(CASE WHEN rating_type = 'Delivery' THEN score END) AS avg_delivery,
				AVG(CASE WHEN rating_type = 'Quality' THEN score END) AS avg_quality,
				AVG(CASE WHEN rating_type = 'Pricing' THEN score END) AS avg_pricing
			FROM `tabVendor Rating Log`
			GROUP BY supplier
		) rating_stats ON rating_stats.supplier = s.name
		LEFT JOIN (
			SELECT vrl_del.supplier,
				COUNT(DISTINCT vrl_del.purchase_receipt) AS on_time_count
			FROM `tabVendor Rating Log` vrl_del
			WHERE vrl_del.rating_type = 'Delivery'
				AND vrl_del.score >= 4
			GROUP BY vrl_del.supplier
		) on_time_stats ON on_time_stats.supplier = s.name
		LEFT JOIN (
			SELECT pr.supplier, COUNT(DISTINCT pr.name) AS short_count
			FROM `tabPurchase Receipt` pr
			INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
			INNER JOIN `tabPurchase Order Item` poi ON poi.name = pri.purchase_order_item
			WHERE pr.docstatus = 1
				AND pri.purchase_order_item IS NOT NULL
				AND pri.qty < poi.qty * 0.9
			GROUP BY pr.supplier
		) short_stats ON short_stats.supplier = s.name
		WHERE {conditions}
		ORDER BY overall_rating DESC
	"""

	return frappe.db.sql(sql, values, as_dict=1)


def _get_charts(data):
	if not data:
		return None

	top_10 = sorted(data, key=lambda r: r["overall_rating"], reverse=True)[:10]

	labels = [r["supplier_name"] for r in top_10]
	values_list = [r["overall_rating"] for r in top_10]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "Overall Rating",
					"values": values_list,
				}
			],
		},
		"type": "bar",
		"title": _("Top 10 Suppliers by Overall Rating"),
		"fieldtype": "Float",
	}
