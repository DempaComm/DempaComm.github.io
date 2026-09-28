"""Compatibility imports for the local administration interface."""
from dempa_site.admin.service import LocalAdmin, LocalFile, ReviewResult
from dempa_site.admin.server import make_handler, serve_local_admin, _require_csrf
from dempa_site.admin.views import _csrf_field, _dashboard, _paper_page, _review_result_card
