# -*- coding: utf-8 -*-

import ast

from odoo import api, fields, models, Command
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    bonuses_ids = fields.One2many('gse.bonus', 'order_id')
    bonuses_count = fields.Integer(string='# Bonuses', compute='_compute_bonuses_count', groups="account.group_account_manager")

    @api.depends('bonuses_ids')
    def _compute_bonuses_count(self):
        for order in self:
            order.bonuses_count = len(order.bonuses_ids)

    def action_view_bonuses(self):
        action = self.env['ir.actions.act_window']._for_xml_id('gse_bonuses.action_gse_bonus')
        action['display_name'] = self.name
        action['domain'] = [('order_id', '=', self.id)]
        context = action['context'].replace('active_id', str(self.id))
        action['context'] = ast.literal_eval(context)
        return action

    def action_cancel(self):
        if any(m.payment_state == 'posted' for m in self.bonuses_ids.vendor_bill_move_ids):
            raise UserError('Cette vente est liée à une commission qui a déjà été payée.')

        self.bonuses_ids.unlink()

        return super().action_cancel()
