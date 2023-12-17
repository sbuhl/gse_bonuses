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
                if move.move_type == 'out_refund':
                    # Special case for paid credit note: generate a negative bonus
                    for bonus in order.bonuses_ids:
                        # TODO: Don't revert the bonus if the vendor bill is not
                        # paid yet, just remove the bonus from there.
                        # Once done, add a test for it in `test_02_bonus` too
                        revert_bonus = bonus.copy({'amount': -bonus.amount})
                        revert_bonus.add_bonus_on_vendor_bill(credit_note=True)
                        move_ids = (bonus + revert_bonus).vendor_bill_move_ids
                        (bonus + revert_bonus).write({'vendor_bill_move_ids': move_ids.ids})
                else:
                    self.env['gse.bonus'].generate_bonuses(order)
        return res
