"""Exceptions shared by the compatibility command-line entry points."""


class DempaSiteError(RuntimeError):
    """Base class for expected, user-facing archive tool errors."""


class PaperToolError(DempaSiteError):
    """An expected paper import, validation, or staging error."""


class LedgerError(DempaSiteError):
    """An expected migration-ledger error."""


class SiteSnapshotError(DempaSiteError):
    """An expected public-site baseline error."""

