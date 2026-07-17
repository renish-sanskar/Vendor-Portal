// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Onboarding", {
	refresh(frm) {
		frm.toggle_display("naming_series", false);

		// Override the default docstatus indicator with onboarding_status
		if (frm.doc.onboarding_status) {
			let color = {
				"Draft": "grey",
				"Under Review": "orange",
				"Approved": "green",
				"Rejected": "red"
			}[frm.doc.onboarding_status] || "grey";
			frm.page.set_indicator(frm.doc.onboarding_status, color);
		}

		if (frm.doc.onboarding_status === "Under Review" && frappe.user.has_role("Purchase Manager")) {
			frm.add_custom_button(__("Approve"), function() {
				// Ensure all documents are verified before approval
				if (!frm.doc.documents || frm.doc.documents.length === 0) {
					frappe.msgprint(__("No documents found. The vendor must upload documents before approval."));
					return;
				}
				
				let unverified = frm.doc.documents.filter(d => d.is_verified != 1);
				if (unverified.length > 0) {
					frappe.msgprint(__("You must verify all uploaded documents before approving the vendor."));
					return;
				}

				frappe.confirm(__("Are you sure you want to approve this vendor?"), function() {
					frm.call({
						doc: frm.doc,
						method: "approve_onboarding",
						args: {
							onboarding_name: frm.doc.name
						},
						freeze: true,
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __("Vendor Approved Successfully"), indicator: 'green'});
								frm.reload_doc();
							}
						}
					});
				});
			});

			frm.add_custom_button(__("Reject"), function() {
				frappe.prompt([
					{
						label: 'Rejection Reason',
						fieldname: 'reason',
						fieldtype: 'Small Text',
						reqd: 1
					}
				], function(values){
					frm.call({
						doc: frm.doc,
						method: "reject_onboarding",
						args: {
							onboarding_name: frm.doc.name,
							reason: values.reason
						},
						freeze: true,
						callback: function(r) {
							if (!r.exc) {
								frappe.show_alert({message: __("Vendor Rejected"), indicator: 'red'});
								frm.reload_doc();
							}
						}
					});
				}, __('Reject Onboarding'), __('Reject'));
			});
		}

		frm.trigger("update_document_progress");
		if (frm.doc.vendor_category) {
			frm.trigger("vendor_category");
		}
	},

	vendor_category(frm) {
		if (frm.doc.vendor_category) {
			frappe.db.get_value("Vendor Category", frm.doc.vendor_category, "minimum_rating_threshold", (r) => {
				if (r && r.minimum_rating_threshold) {
					frm.set_intro(__("Minimum Rating Threshold for this category is {0}", [r.minimum_rating_threshold]), "blue");
				}
			});
		} else {
			frm.set_intro("");
		}
	},

	validate(frm) {
		if (frm.doc.gst_number) {
			let gst_pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
			if (!gst_pattern.test(frm.doc.gst_number.toUpperCase())) {
				frappe.msgprint(__("GST Number is not valid. It must be a 15-character alphanumeric string in the format: 2-digit state code + 10-character PAN + 1 entity code + Z + 1 check digit."));
				frappe.validated = false;
			}
		}
	},

	update_document_progress(frm) {
		let total = frm.doc.documents ? frm.doc.documents.length : 0;
		if (total > 0) {
			// In Frappe, Check fields are 0 or 1. d.is_verified can sometimes be "0" which is truthy.
			let verified = frm.doc.documents.filter(d => d.is_verified == 1).length;
			let percent = (verified / total) * 100;
			let bar_color = percent === 100 ? "var(--green-500, #28a745)" : "var(--blue-500, #007bff)";
			
			let progress_html = `
				<div style="padding: 0 0 15px 0;">
					<div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
						<span style="font-weight: 600; font-size: 13px;">Document Verification Progress</span>
						<span class="text-muted" style="font-size: 12px;">${__("{0} of {1} documents verified", [verified, total])}</span>
					</div>
					<div class="progress" style="height: 8px; border-radius: 4px; margin: 0; background-color: var(--gray-200, #e9ecef);">
						<div class="progress-bar" style="width: ${percent}%; background-color: ${bar_color}; transition: width 0.3s ease;"></div>
					</div>
				</div>
			`;
			
			let wrapper = frm.fields_dict.documents.$wrapper.find('.custom-progress-wrapper');
			if (wrapper.length === 0) {
				wrapper = $('<div class="custom-progress-wrapper"></div>').prependTo(frm.fields_dict.documents.$wrapper);
			}
			wrapper.html(progress_html);
			wrapper.show();
		} else {
			let wrapper = frm.fields_dict.documents.$wrapper.find('.custom-progress-wrapper');
			if (wrapper.length > 0) {
				wrapper.hide();
			}
		}
	},

	documents_add(frm, cdt, cdn) {
		frm.trigger("update_document_progress");
	},
	documents_remove(frm, cdt, cdn) {
		frm.trigger("update_document_progress");
	}
});

frappe.ui.form.on("Vendor Document", {
	is_verified(frm, cdt, cdn) {
		frm.trigger("update_document_progress");
	}
});
