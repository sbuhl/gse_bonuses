from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bonus_journal_id = fields.Many2one(related='company_id.bonus_journal_id', readonly=False)
    bonus_product_id = fields.Many2one(related='company_id.bonus_product_id', readonly=False)
    bonus_rate = fields.Float(related='company_id.bonus_rate', readonly=False)
