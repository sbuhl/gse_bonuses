# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bonuses_ids = fields.One2many('gse.bonus', 'so_line')

    def write(self, vals):
        res = super().write(vals)
        if 'qty_delivered' in vals:
            for order_line in self.filtered(lambda sol: sol.task_id):
                self.env['gse.bonus'].generate_bonuses(order_line.order_id)
        return res
