from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Asegura que los campos de cocina viajen al frontend del POS.

        Implementacion defensiva: la firma de este metodo cambia entre
        sub-versiones de Odoo 18 (algunas usan `config_id`, otras `data`).
        Si la API cambia, igual exponemos los campos de cocina.
        """
        extra_fields = ["kitchen_preparable", "kitchen_default_note"]
        parent = getattr(super(), "_load_pos_data_fields", None)
        if parent is None:
            return extra_fields

        try:
            fields_list = parent(config_id) or []
        except TypeError:
            # La firma del padre cambio: intentamos sin argumentos.
            try:
                fields_list = parent() or []
            except Exception:
                return extra_fields

        for fname in extra_fields:
            if fname not in fields_list:
                fields_list.append(fname)
        return fields_list
