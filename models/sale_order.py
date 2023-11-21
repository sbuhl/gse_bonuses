# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command
from odoo.exceptions import UserError

import ast


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    def action_cancel(self):
        for order in self:
            for bonus in order.bonuses_ids:
                # Don't let bonus be deleted if already paid
                vendor_bill = bonus.vendor_bill_move_id
                if vendor_bill.state == 'posted':
                    raise UserError('Cette vente est liée à une commission qui a déjà été payée.')

                # Remove move line and bonus
                vendor_bill_line = bonus.vendor_bill_move_line_id.id
                bonus.unlink()
                vendor_bill.invoice_line_ids = [Command.unlink(vendor_bill_line)]
                # Unlink the vendor bill if nothing in it anymore
                if not vendor_bill.invoice_line_ids:
                    vendor_bill.write({'state': 'draft'})
                    vendor_bill.unlink()

        return super().action_cancel()
