# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

import frappe


SUPPLIER_GROUP_MAP = {
	"Raw Material":              "Raw Materials",
	"Raw Materials":             "Raw Materials",
	"Service":                   "IT Services",
	"Services":                  "IT Services",
	"Consulting":                "IT Services",
	"IT Services":               "IT Services",
	"Logistics":                 "Logistics",
	"Transport":                 "Logistics",
	"Transportation":            "Logistics",
	"Packaging":                 "Packaging",
	"Packaging Material":        "Packaging",
	"Stationery":                "Office Supplies",
	"Office Supplies":           "Office Supplies",
	"Hardware":                  "Hardware & Equipment",
	"Equipment":                 "Hardware & Equipment",
	"Machinery":                 "Hardware & Equipment",
	"Electrical":                "Electrical & Electronics",
	"Electronics":               "Electrical & Electronics",
	"Chemicals":                 "Chemicals",
	"Pharmaceuticals":           "Pharmaceuticals",
	"Food & Beverage":           "Food & Beverage",
	"Food":                      "Food & Beverage",
	"Beverage":                  "Food & Beverage",
	"Agricultural":              "Agriculture",
	"Farming":                   "Agriculture",
	"Construction":              "Construction",
	"Maintenance":               "Maintenance Services",
	"Security":                  "Security Services",
	"Cleaning":                  "Cleaning Services",
	"Marketing":                 "Marketing & Advertising",
	"Advertising":               "Marketing & Advertising",
	"Printing":                  "Printing & Publishing",
	"Publishing":                "Printing & Publishing",
	"Subcontractor":             "Subcontractor",
	"Distributor":               "Distributor",
	"Wholesale":                 "Distributor",
	"Retail":                    "Retail",
	"Trading":                   "Trading",
}


def execute():
	"""Map supplier_group to custom_vendor_category for suppliers that have one
	but not the other.  Logs unmapped groups so the operator can intervene."""
	suppliers = frappe.db.get_all(
		"Supplier",
		filters={
			"supplier_group": ["is", "set"],
			"custom_vendor_category": ["is", "not set"],
		},
		fields=["name", "supplier_name", "supplier_group"],
	)

	if not suppliers:
		frappe.logger().info("Patch v1_0/populate_vendor_category: no suppliers to process")
		return

	mapped = 0
	unmapped = []

	for s in suppliers:
		group = s.supplier_group
		category = _map_group(group)

		if category:
			frappe.db.set_value("Supplier", s.name, "custom_vendor_category", category)
			mapped += 1
		else:
			unmapped.append(s)

	if unmapped:
		group_list = ", ".join(
			f"{s.name} ({s.supplier_group})" for s in unmapped
		)
		frappe.logger().warning(
			f"Patch v1_0/populate_vendor_category: {len(unmapped)} supplier(s) "
			f"could not be mapped — {group_list}"
		)

	frappe.logger().info(
		f"Patch v1_0/populate_vendor_category: {mapped} mapped, "
		f"{len(unmapped)} unmapped (logged)"
	)


def _map_group(group):
	"""Return the custom_vendor_category name for a supplier_group, or None."""
	return SUPPLIER_GROUP_MAP.get(group)
