import os

from odoo import models


class IrAttachment(models.Model):
    """Work-around for an Odoo 18 regression in ir.attachment._get_path.

    Odoo 18 raises UserError when the destination file already exists on disk,
    even though a matching SHA-1 checksum guarantees identical content.
    This happens when a DB+filestore backup is restored and a module that ships
    binary data in XML (e.g. spreadsheet_dashboard_account) is upgraded via the
    Odoo UI — the upgrade re-processes the XML, finds the file already present
    from the restored filestore, and crashes.

    This module depends only on 'base' so it is loaded into every fresh
    registry BEFORE any other addon (including spreadsheet_dashboard_account),
    ensuring the patch is active when the problematic write occurs.
    """

    _inherit = "ir.attachment"

    def _get_path(self, bin_value, checksum):
        fname = checksum[:2] + "/" + checksum
        full_path = self._full_path(fname)
        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
            # File is already on disk with the same content (checksum match).
            # Reuse it instead of raising UserError.
            return fname, full_path
        return super()._get_path(bin_value, checksum)
