# -*- coding: utf-8 -*-

from odoo import api, fields, models

import ast


class SaleOrder(models.Model):
    _inherit = "sale.order"

    bonuses_ids = fields.One2many('gse.bonus', 'order_id')
    bonuses_count = fields.Integer(string='# Bonuses', compute='_compute_bonuses_ids', groups="account.group_account_manager")

    @api.depends('bonuses_ids')
    def _compute_bonuses_ids(self):
        for order in self:
            order.bonuses_count = len(order.bonuses_ids)

    def action_view_bonuses(self):
        action = self.env['ir.actions.act_window']._for_xml_id('gse_bonuses.action_gse_bonus')
        action['display_name'] = self.name
        action['domain'] = [('order_id', '=', self.id)]
        context = action['context'].replace('active_id', str(self.id))
        action['context'] = ast.literal_eval(context)
        return action
