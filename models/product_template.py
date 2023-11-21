from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    bonus_rate = fields.Float('Bonus Rate')
