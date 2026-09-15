from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = "product.product"

    power = fields.Float(string="Power")
    min_voltage = fields.Float(string="Min Voltage")
    max_voltage = fields.Float(string="Max Voltage")
    min_current  = fields.Float(string="Min Current")
    max_current  = fields.Float(string="Max Current")
    dimming  = fields.Char(string="Dimming")
    operation_type  = fields.Char(string="Operation type")
    protection  = fields.Char(string="Protection")

    protection_numeric = fields.Float(
        string="Protection Numeric",
        compute="_compute_protection_numeric",
        store=True,
        index=True,
    )

    @api.depends("protection")
    def _compute_protection_numeric(self):
        for record in self:
            record.protection_numeric = False

            if not record.protection:
                continue

            value = record.protection.strip()

            try:
                record.protection_numeric = float(value)
            except (ValueError, TypeError):
                pass


    @api.model
    def get_filter_values(self, field_name):

        allowed_fields = {
            "dimming",
            "operation_type",
            "protection",
        }

        if field_name not in allowed_fields:
            return []

        groups = self.read_group(
            [(field_name, "!=", False)],
            [field_name],
            [field_name],
            orderby=f"{field_name} asc",
        )
        ret = [
            {
                "value": group[field_name],
                "label": group[field_name],
            }
            for group in groups
            if group.get(field_name)
        ]
        return ret



    # @api.model
    # def get_filter_range_maxes(self):
    #     result = {}

    #     for field_name in ["min_current", "max_current"]:
    #         groups = self.read_group(
    #             [(field_name, "!=", False)],
    #             [f"{field_name}:max"],
    #             [],
    #         )

    #         if groups:
    #             result[field_name] = groups[0].get(field_name) or 0
    #         else:
    #             result[field_name] = 0

    #     return result

    @api.model
    def get_filter_range_maxes(self):
        result = {
            "min_current": 0,
            "max_current": 0,
            "min_voltage": 0,
            "max_voltage": 0,
        }

        for field_name in [
            "min_current",
            "max_current",
            "min_voltage",
            "max_voltage",
        ]:
            data = self._read_group(
                [(field_name, "!=", False)],
                [],
                [f"{field_name}:max"],
            )

            if data:
                result[field_name] = data[0][0] or 0

        return result
