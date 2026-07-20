import frappe


def vendor_rating_log_has_permission(doc, ptype="read", user=None):
	"""has_permission hook for Vendor Rating Log.

	Write/create/delete access rules:
	- Vendor Manager: may act on any rating       → return True (allow)
	- Owner / rated_by user: may act on their own → return True (allow)
	- Everyone else: explicitly denied            → return False

	Read / all other ptypes: allowed at the controller level (return True),
	leaving the final say to standard role-based permissions.

	NOTE: Frappe's has_controller_permissions treats a falsy return (including
	None) as a denial. A controller hook can only *deny* — it must return True
	to let role-based permissions decide. Therefore we return True (not None)
	for every case we don't want to explicitly block.
	"""
	if not user:
		user = frappe.session.user

	if ptype in ("write", "create", "delete"):
		if "Vendor Manager" in frappe.get_roles(user):
			# Vendor Manager may act on any rating; defer to role perms.
			return True
		if doc.get("rated_by") == user or doc.get("owner") == user:
			# Owner of the rating may always act on it.
			return True
		# Deny everyone else.
		return False

	# read, print, report, email — no controller-level objection.
	return True


def vendor_onboarding_query_conditions(user):
	"""permission_query_conditions hook for Vendor Onboarding list view.

	- Vendor Manager: sees all records → return empty string (no restriction)
	- Purchase Team / Purchase User / Purchase Manager: sees only own submissions
	- Everyone else: no additional rows exposed (empty string, rely on docperms)

	Uses frappe.db.escape() instead of f-string interpolation to prevent SQL injection.
	"""
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if "Vendor Manager" in roles:
		return ""

	restricted_roles = {"Purchase Team", "Purchase User", "Purchase Manager"}
	if restricted_roles & set(roles):
		escaped = frappe.db.escape(user)
		return f"`tabVendor Onboarding`.`owner` = {escaped}"

	return ""
