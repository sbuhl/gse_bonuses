from odoo import fields, models


class Product(models.Model):
    _inherit = "product.template"

    rate = fields.Float('Bonus Rate')  # TODO: fallback on company rate
