from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    bonuses_ids = fields.Many2many('gse.bonus', compute='_compute_bonuses_ids')

    def _compute_bonuses_ids(self):
        for move in self:
            move.bonuses_ids = move.line_ids.sale_line_ids.order_id.bonuses_ids

    def _invoice_paid_hook(self):
        res = super()._invoice_paid_hook()
        # TODO: Maybe could use `get_recursively_not_directly_related` from
        #       https://github.com/sbuhl/gse_custo/pull/17
        for move in self:
            sale_orders = move.line_ids.sale_line_ids.order_id
            for order in sale_orders:
                if move.move_type == 'out_refund':
                    # Special case for paid credit note: generate a negative bonus
                    for bonus in order.bonuses_ids:
                        bonus.revert()
                else:
                    self.env['gse.bonus'].generate_bonuses(order)
        return res

    def write(self, vals):
        # In case of cancel or draft of invoices which is coming from the
        # "posted" state -> "Cancel" the bonuses
        if 'state' in vals and vals['state'] != 'posted':
            for move in self.filtered(lambda m: m.state == 'posted'):
                for bonus in move.bonuses_ids:
                    bonus.revert()
        res = super().write(vals)
        return res
