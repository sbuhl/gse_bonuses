from odoo import fields, models


class Bonus(models.Model):
    _name = 'gse.bonus'
    _description = 'Bonus'
    _order = 'id desc'

    state = fields.Selection([
        ('draft', 'New'),
        ('done', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], 'Status', default='draft')

    timesheet_id = fields.Many2one('account.analytic.line', required=1)
    so_line = fields.Many2one(related='timesheet_id.so_line')
    user_id = fields.Many2one(related='timesheet_id.user_id', store=True, required=1)
    order_id = fields.Many2one(related='so_line.order_id', store=True, required=1)
    company_id = fields.Many2one(related='order_id.company_id')
    currency_id = fields.Many2one(related='order_id.currency_id')

    # move_bonus_from = fields.Many2one('account.move')  # source_move_id
    # currency_id = fields.Many2one(related='move_bonus_from.currency_id')
    amount = fields.Monetary(string='Amount', required=1)

    move_bonus_vendeur = fields.Many2one('account.move', ondelete='set null')  # move_id

    def generate_bonuses(self, order):
        if not order:
            return

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
        for labor_order_line in order.order_line.filtered(lambda line: line.product_id.service_tracking != 'no' and line.task_id and line.product_id.rate):
            labor_task = labor_order_line.task_id

            # eg 2.25 for 2h15min
            task_total_hours = labor_task.total_hours_spent
            # eg 300$ / 10% = 30$
            reward_to_distribute = labor_order_line.price_total / labor_order_line.product_id.rate
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
                bonus_amount = timesheet.unit_amount * one_hour_reward  # TODO: check if `unit_amount` in minutes?
                total_timesheet_unit_amount += timesheet.unit_amount
                # TODO: create multi for perfs
                self.create({
                    'timesheet_id': timesheet.id,
                    'amount': bonus_amount,
                })

            # Safety check
            assert task_total_hours == total_timesheet_unit_amount, "Total hours spent on task does not match timesheet sum."

            # TODO:
            # - Finish this method to create all commissions
            # - Create the vendor bill
            # - Idea: no bonus model? just add boolean on vendor bill / technician invoice to mark it as a bonus invoice
            #         and bind each move line to a labor SOL (and bind the labor SOL to that move line too)
            #         too see how many fields we should add on SOL, maybe not good idea
