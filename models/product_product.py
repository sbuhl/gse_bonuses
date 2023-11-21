from odoo import models


class Product(models.Model):
    _inherit = 'product.product'

    def get_bonus_rate(self):
        self.ensure_one()
        return self.bonus_rate or self.env.company.bonus_rate
