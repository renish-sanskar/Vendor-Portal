# Copyright (c) 2026, renish and contributors
# For license information, please see license.txt

"""Vendor Portal API package.

Re-exports all whitelisted endpoints at the package level so that both the
historical dotted paths (e.g. ``vendor_portal.vendor_portal.api.submit_vendor_rating``)
and the submodule paths (e.g. ``...api.supplier_comparison.get_supplier_comparison``)
resolve correctly.

This package previously shadowed a sibling ``api.py`` module — its contents now
live in ``api/core.py`` and are re-exported here.
"""

from vendor_portal.vendor_portal.api.core import (  # noqa: F401
	get_onboarding_status_summary,
	get_vendor_dashboard,
	get_vendor_rating_history,
	submit_vendor_rating,
)
from vendor_portal.vendor_portal.api.supplier_comparison import (  # noqa: F401
	get_supplier_comparison,
)
