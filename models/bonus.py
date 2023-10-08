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
    user_id = fields.Many2one('res.users', required=1)
    move_bonus_from = fields.Many2one('account.move')  # source_move_id
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.company)
    amount = fields.Monetary(string='Amount')
    move_bonus_vendeur = fields.Many2one('account.move', ondelete='set null')  # move_id
    currency_id = fields.Many2one(related='move_bonus_from.currency_id')

    def generate_bonuses(self, order):
        if not order:
            return

        self.ensure_one()

        # Check if bonuses can be created: the SO must:
        # - be fully paid
        # - be fully delivered
        # - have its related labor service tasks done (related SOL will be
        #   marked as delivered, so it should be covered by previous point)
        if any([state != 'paid' for state in self.invoice_ids.mapped('payment_state')]):
            # Not all invoices are fully paid
            return
        if self.product_uom_qty != self.qty_invoiced:
            # Not all products have been invoiced
            return
        if self.product_uom_qty != self.qty_delivered:
            # Not all products have been delivered
            return

        # 1. Get every SOL related to a labor task
        for labor_order_line in self.order_line.mapped(lambda line: line.service_tracking and line.task_id):
            labor_task = labor_order_line.task_id
            task_total_hours = labor_task.total_hours_spent

            employees = []
            for timesheet in labor_task.timesheet_ids:
                employees[timesheet.user_id] = employees.get(timesheet.user_id, 0) + timesheet.unit_amount  # is this minutes?

            assert task_total_hours == sum(employees.values()), "Total hours spent on task does not match timesheet sum."

            # TODO:
            # - Finish this method to create all commissions
            # - Create the vendor bill
            # - Idea: no bonus model? just add boolean on vendor bill / technician invoice to mark it as a bonus invoice
            #         and bind each move line to a labor SOL (and bind the labor SOL to that move line too)
            #         too see how many fields we should add on SOL, maybe not good idea
