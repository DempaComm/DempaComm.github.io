"""Compatibility imports for the page-specific public HTML renderers."""

from dempa_site.site.pages.archive import rendered_archive_page
from dempa_site.site.pages.common import rendered_tag_index, rendered_year_groups
from dempa_site.site.pages.home import rendered_home_page
from dempa_site.site.pages.math import (
    rendered_math_index_item,
    rendered_math_page,
    rendered_math_section_page,
    representative_math_tags,
)
from dempa_site.site.pages.not_found import rendered_not_found_page
from dempa_site.site.pages.paper import rendered_paper_page
from dempa_site.site.pages.tags import rendered_tag_page, rendered_tag_page_paper

__all__ = (
    "rendered_archive_page",
    "rendered_home_page",
    "rendered_math_index_item",
    "rendered_math_page",
    "rendered_math_section_page",
    "rendered_not_found_page",
    "rendered_paper_page",
    "rendered_tag_index",
    "rendered_tag_page",
    "rendered_tag_page_paper",
    "rendered_year_groups",
    "representative_math_tags",
)
