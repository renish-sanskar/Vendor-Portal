import frappe


_COLOR_MAP = {
	"Red": "#ef4444",
	"Yellow": "#eab308",
	"Green": "#22c55e",
	"Blue": "#3b82f6",
}


def stars(rating_raw, max_stars=5):
	"""Convert a numeric rating (0–1 or 1–5) into star symbols.

	Accepts rating as a float or int.
	- If rating is ≤ 1, it's treated as a 0–1 scale (Rating fieldtype).
	- If rating is > 1, it's treated as already on a 1–5 scale.
	"""
	if rating_raw is None:
		return "☆☆☆☆☆"

	rating = float(rating_raw)

	# Convert 0–1 scale to 1–5 scale if needed
	if rating <= 1:
		rating = rating * max_stars

	full = int(round(rating))
	full = max(0, min(full, max_stars))
	empty = max_stars - full

	return "★" * full + "☆" * empty


def scorecard_badge(scorecard):
	"""Render an inline HTML badge for a Supplier Scorecard record.

	Accepts a dict (or DocType row) with keys:
	    supplier_score, status, indicator_color

	Returns an empty string if scorecard is None or falsy.
	"""
	if not scorecard:
		return ""

	score = scorecard.get("supplier_score") or "---"
	status = scorecard.get("status") or ""
	color = _COLOR_MAP.get(scorecard.get("indicator_color"), "#94a3b8")

	return (
		f'Scorecard: '
		f'<span style="display: inline-block; padding: 2px 10px; '
		f'border-radius: 10px; font-size: 8pt; font-weight: 700; '
		f'color: #fff; background-color: {color};">'
		f'{frappe.utils.escape_html(status)}'
		f'</span> '
		f'<strong>{frappe.utils.escape_html(str(score))}</strong>'
	)

