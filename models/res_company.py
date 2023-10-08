from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bonus_journal_id = fields.Many2one('account.journal', string='Bonus Journal')
    bonus_product_id = fields.Many2one('product.product', 'Bonus Product')
    bonus_rate = fields.Float('Product Default Bonus Rate')
