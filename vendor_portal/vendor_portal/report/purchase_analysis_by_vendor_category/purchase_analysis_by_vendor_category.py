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
			"fieldname": "vendor_category",
			"label": _("Vendor Category"),
			"fieldtype": "Link",
			"options": "Vendor Category",
			"width": 160,
		},
		{
			"fieldname": "total_suppliers",
			"label": _("Total Suppliers"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "active_suppliers",
			"label": _("Active Suppliers"),
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"fieldname": "total_po_value",
			"label": _("Total PO Value"),
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"fieldname": "avg_po_value",
			"label": _("Avg PO Value"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "total_items_purchased",
			"label": _("Total Items Purchased"),
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"fieldname": "avg_scorecard_score",
			"label": _("Avg Scorecard Score"),
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"fieldname": "best_scorecard_supplier",
			"label": _("Best Scorecard Supplier"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "avg_vendor_rating",
			"label": _("Avg Custom Rating"),
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"fieldname": "lowest_rating_supplier",
			"label": _("Lowest Rating Supplier"),
			"fieldtype": "Data",
			"width": 180,
		},
	]


def _build_conditions(filters):
	conditions = []
	po_conditions = []
	values = {}

	if filters.get("vendor_category"):
		conditions.append("vc.category_name = %(vendor_category)s")
		values["vendor_category"] = filters["vendor_category"]

	if filters.get("from_date"):
		po_conditions.append("po.transaction_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		po_conditions.append("po.transaction_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	where_clause = " AND ".join(conditions) if conditions else "1=1"
	po_clause = " AND " + " AND ".join(po_conditions) if po_conditions else ""
	return where_clause, po_clause, values


def _get_data(conditions, po_clause, values):
	sql = f"""
		SELECT
			vc.category_name AS vendor_category,
			COALESCE(sup_stats.total_suppliers, 0) AS total_suppliers,
			COALESCE(sup_stats.active_suppliers, 0) AS active_suppliers,
			COALESCE(po_stats.total_po_value, 0) AS total_po_value,
			CASE
				WHEN COALESCE(po_stats.po_count, 0) > 0
				THEN COALESCE(po_stats.total_po_value, 0) / po_stats.po_count
				ELSE 0
			END AS avg_po_value,
			COALESCE(po_stats.total_items, 0) AS total_items_purchased,
			COALESCE(sc_stats.avg_scorecard, 0) AS avg_scorecard_score,
			COALESCE(sc_stats.best_supplier, '') AS best_scorecard_supplier,
			COALESCE(sup_stats.avg_rating, 0) AS avg_vendor_rating,
			sup_stats.lowest_rating_supplier
		FROM
			`tabVendor Category` vc
		LEFT JOIN (
			SELECT
				s_sc.custom_vendor_category,
				AVG(sc_sub.supplier_score) AS avg_scorecard,
				(
					SELECT s2.supplier_name
					FROM `tabSupplier Scorecard` sc2
					JOIN `tabSupplier` s2 ON s2.name = sc2.supplier
					WHERE s2.custom_vendor_category = s_sc.custom_vendor_category
						AND sc2.supplier_score = (
							SELECT MAX(sc3.supplier_score)
							FROM `tabSupplier Scorecard` sc3
							JOIN `tabSupplier` s3 ON s3.name = sc3.supplier
							WHERE s3.custom_vendor_category = s_sc.custom_vendor_category
						)
					LIMIT 1
				) AS best_supplier
			FROM `tabSupplier` s_sc
			JOIN `tabSupplier Scorecard` sc_sub ON sc_sub.supplier = s_sc.name
			GROUP BY s_sc.custom_vendor_category
		) sc_stats ON sc_stats.custom_vendor_category = vc.category_name
		LEFT JOIN (
			SELECT
				s_in.custom_vendor_category,
				COUNT(DISTINCT s_in.name) AS total_suppliers,
				COUNT(DISTINCT CASE WHEN s_in.disabled = 0 THEN s_in.name END) AS active_suppliers,
				AVG(s_in.custom_vendor_rating * 5) AS avg_rating,
				(
					SELECT s_sub.supplier_name
					FROM `tabSupplier` s_sub
					WHERE s_sub.custom_vendor_category = s_in.custom_vendor_category
						AND s_sub.custom_vendor_rating = (
							SELECT MIN(s_min.custom_vendor_rating)
							FROM `tabSupplier` s_min
							WHERE s_min.custom_vendor_category = s_in.custom_vendor_category
								AND s_min.custom_vendor_rating > 0
						)
						AND s_sub.custom_vendor_rating > 0
					LIMIT 1
				) AS lowest_rating_supplier
			FROM `tabSupplier` s_in
			GROUP BY s_in.custom_vendor_category
		) sup_stats ON sup_stats.custom_vendor_category = vc.category_name
		LEFT JOIN (
			SELECT
				s_out.custom_vendor_category,
				SUM(po.base_grand_total) AS total_po_value,
				COUNT(DISTINCT po.name) AS po_count,
				SUM(poi.qty) AS total_items
			FROM `tabPurchase Order` po
			INNER JOIN `tabSupplier` s_out ON po.supplier = s_out.name
			LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
			WHERE po.docstatus = 1{po_clause}
			GROUP BY s_out.custom_vendor_category
		) po_stats ON po_stats.custom_vendor_category = vc.category_name
		WHERE {conditions}
		ORDER BY total_po_value DESC
	"""

	return frappe.db.sql(sql, values, as_dict=1)


def _get_charts(data):
	if not data:
		return None

	filtered = [r for r in data if r["total_po_value"] > 0]
	if not filtered:
		return None

	labels = [r["vendor_category"] for r in filtered]
	values_list = [r["total_po_value"] for r in filtered]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "PO Value",
					"values": values_list,
				}
			],
		},
		"type": "pie",
		"title": _("PO Value Distribution by Vendor Category"),
	}
