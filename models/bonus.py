from odoo import fields, models
from odoo.exceptions import UserError


class Bonus(models.Model):
    _name = 'gse.bonus'
    _description = 'Bonus'
    _order = 'id desc'

    timesheet_id = fields.Many2one('account.analytic.line', required=1)
    so_line = fields.Many2one(related='timesheet_id.so_line')
    employee_id = fields.Many2one(related='timesheet_id.employee_id', store=True, required=1)
    order_id = fields.Many2one(related='so_line.order_id', store=True, required=1)
    company_id = fields.Many2one(related='order_id.company_id')
    currency_id = fields.Many2one(related='order_id.currency_id')

    # move_bonus_from = fields.Many2one('account.move')  # source_move_id
    # currency_id = fields.Many2one(related='move_bonus_from.currency_id')
    # TODO: Maybe need to convert amount into company amount, see `_compute_amount_company`
    amount = fields.Monetary(string='Amount', required=1)

    vendor_bill_move_id = fields.Many2one(related='vendor_bill_move_line_id.move_id', ondelete='restrict')
    vendor_bill_move_line_id = fields.Many2one('account.move.line', ondelete='restrict')

    def generate_bonuses(self, order):
        Move = self.env['account.move']

        if not order:
            return

        journal = order.company_id.bonus_journal_id
        if not journal or not journal.default_account_id:
            raise UserError("Le journal pour les bonus n'est pas configuré")

        order.ensure_one()

        # Check if bonuses can be created: the SO must:
        # - be fully paid
        # - be fully delivered
        # - have its related labor service tasks done (related SOL will be
        #   marked as delivered, so it should be covered by previous point)
        if any([move_state != 'paid' for move_state in order.invoice_ids.mapped('payment_state')]):
            # Not all invoices are fully paid
            return
        if any(line for line in order.order_line if line.product_uom_qty != line.qty_invoiced):
            # Not all products have been invoiced
            return
        if any(line for line in order.order_line if line.product_uom_qty != line.qty_delivered):
            # Not all products have been delivered
            return

        # 1. Get every SOL related to a labor task
        for labor_order_line in order.order_line.filtered(
            lambda line: line.product_id.service_tracking != 'no' and line.task_id and line.product_id.get_bonus_rate()
        ):
            labor_task = labor_order_line.task_id

            # eg 2.25 for 2h15min
            task_total_hours = labor_task.total_hours_spent
            # eg 300$ / 10% = 30$
            reward_to_distribute = (labor_order_line.price_total * labor_order_line.product_id.get_bonus_rate()) / 100

            if not task_total_hours or not reward_to_distribute:
                # There might be no timesheet encoded, or 0% set on product AND
                # company rate
                continue

            # eg 30$ / 2.25 = 13,33$ for one hour
            one_hour_reward = reward_to_distribute / task_total_hours

            # {
            #     user_1: {
            #         timesheet_3: 40
            #         timesheet_5: 10
            #     }
            #     user_2: {
            #         timesheet_4: 30
            #     }
            # }
            total_timesheet_unit_amount = 0
            for timesheet in labor_task.timesheet_ids.filtered('unit_amount'):
                total_timesheet_unit_amount += timesheet.unit_amount

                if timesheet.bonuses_ids:
                    # This timesheet is already linked to a bonus
                    continue

                # Create bonus
                bonus_amount = timesheet.unit_amount * one_hour_reward  # TODO: check if `unit_amount` in minutes?
                bonus = self.create({  # TODO: create multi for perfs
                    'timesheet_id': timesheet.id,
                    'amount': bonus_amount,
                    'order_id': timesheet.order_id.id,
                    'employee_id': timesheet.employee_id.id,
                })
                # Create or update vendor bill with new bonus
                partner_id = bonus.employee_id.address_home_id.id
                if not partner_id:
                    raise UserError("L'employé n'a pas d'adresse enregistrée.")
                move = Move.search([
                    ('company_id', '=', bonus.company_id.id),
                    ('move_type', '=', 'in_invoice'),
                    ('partner_id', '=', partner_id),
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'draft'),
                ], limit=1)
                if not move:
                    move = Move.create({
                        'company_id': bonus.company_id.id,
                        'move_type': 'in_invoice',
                        'partner_id': partner_id,
                        'journal_id': journal.id,
                        'invoice_date': bonus.write_date,
                        'date': bonus.write_date,
                        'ref': 'Commission for SO %s' % bonus.order_id.name,
                    })
                move_line = self.env['account.move.line'].create({
                    'move_id': move.id,
                    'product_id': bonus.company_id.bonus_product_id.id,
                    'name': 'Commission for SO %s (SOL: %s)' % (bonus.order_id.name, bonus.so_line.name),
                    'price_unit': bonus.amount,
                    'tax_ids': None,
                })
                bonus.write({
                    'vendor_bill_move_line_id': move_line.id,
                })

            # Safety check
            assert task_total_hours == total_timesheet_unit_amount, "Total hours spent on task does not match timesheet sum."
