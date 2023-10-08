from odoo import fields, models


class Product(models.Model):
    _inherit = "product.product"

    rate = fields.Float('Rate')  # TODO: fallback on company rate
