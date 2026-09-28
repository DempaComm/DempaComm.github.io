"""Bind existing CLI commands to an explicit repository context."""
from functools import partial
from . import catalog, checks, conversion, editing, importing, maintenance
from .context import CommandContext


def build_commands(context: CommandContext):
    return {
        "verify": partial(checks.command_verify, context=context),
        "audit": partial(checks.command_audit, context=context),
        "catalog": partial(catalog.command_catalog, context=context),
        "build-roots": partial(checks.command_build_roots, context=context),
        "stage": partial(checks.command_stage, context=context),
        "check-links": partial(checks.command_check_links, context=context),
        "check-all": partial(checks.command_check_all, context=context),
        "check-paper": partial(checks.command_check_paper, context=context),
        "add-correction": partial(editing.command_add_note, context=context),
        "add-addendum": partial(editing.command_add_note, context=context),
        "pagefind-index": partial(checks.command_pagefind_index, context=context),
        "latexml-trial": partial(conversion.command_latexml_trial, context=context),
        "typst-trial": partial(conversion.command_typst_trial, context=context),
        "publish-latexml": partial(conversion.command_publish_latexml, context=context),
        "latexml-batch": partial(conversion.command_latexml_batch, context=context),
        "inspect-file": partial(maintenance.command_inspect_file, context=context),
        "clean-local": partial(maintenance.command_clean_local, context=context),
        "import": partial(importing.command_import, context=context),
        "import-tex": partial(importing.command_import_tex, context=context),
        "import-pdf": partial(importing.command_import_pdf, context=context),
        "approve": partial(editing.command_approve, context=context),
        "review-change": partial(editing.command_review_change, context=context),
        "finish-change": partial(editing.command_finish_change, context=context),
        "local-admin": partial(maintenance.command_local_admin, context=context),
    }
