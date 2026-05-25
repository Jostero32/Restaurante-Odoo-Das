from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Asegura que los campos de cocina viajen al frontend del POS."""
        fields_list = super()._load_pos_data_fields(config_id)
        for fname in ("kitchen_preparable", "kitchen_default_note"):
            if fname not in fields_list:
                fields_list.append(fname)
        return fields_list
