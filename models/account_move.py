from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _invoice_paid_hook(self):
        res = super()._invoice_paid_hook()
        # TODO: Maybe could use `get_recursively_not_directly_related` from
        #       https://github.com/sbuhl/gse_custo/pull/17
        for move in self:
            sale_orders = move.line_ids.sale_line_ids.order_id
            for order in sale_orders:
                self.env['gse.bonus'].generate_bonuses(order)
        return res
