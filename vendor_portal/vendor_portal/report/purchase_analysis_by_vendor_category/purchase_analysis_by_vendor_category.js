// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Analysis by Vendor Category"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "vendor_category",
			label: __("Vendor Category"),
			fieldtype: "Link",
			options: "Vendor Category",
		},
	],
};
