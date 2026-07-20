// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.query_reports["Vendor Performance Report"] = {
	filters: [
		{
			fieldname: "vendor_category",
			label: __("Vendor Category"),
			fieldtype: "Link",
			options: "Vendor Category",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
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
			fieldname: "minimum_rating",
			label: __("Minimum Rating"),
			fieldtype: "Float",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Colour-code the overall rating: green ≥ 4, amber ≥ 2.5, red below.
		if (column.fieldname === "overall_rating" && data && data.overall_rating) {
			const score = parseFloat(data.overall_rating);
			let color = "red";
			if (score >= 4) {
				color = "green";
			} else if (score >= 2.5) {
				color = "orange";
			}
			value = `<span style="color:${color}; font-weight:600;">${value}</span>`;
		}

		return value;
	},
};
