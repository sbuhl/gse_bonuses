import ast
import logging

from odoo import api, fields, models, Command
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

logger = logging.getLogger(__name__)


class Bonus(models.Model):
    _name = 'gse.bonus'
    _description = 'Bonus'
    _order = 'id desc'

    timesheet_id = fields.Many2one('account.analytic.line', required=1, copy=True)
    so_line = fields.Many2one(related='timesheet_id.so_line')
    employee_id = fields.Many2one(related='timesheet_id.employee_id', store=True, required=1, copy=True)
    order_id = fields.Many2one(related='so_line.order_id', store=True, required=1, copy=True)
    company_id = fields.Many2one(related='order_id.company_id')
    currency_id = fields.Many2one(related='order_id.currency_id')

    # move_bonus_from = fields.Many2one('account.move')  # source_move_id
    # currency_id = fields.Many2one(related='move_bonus_from.currency_id')
    # TODO: Maybe need to convert amount into company amount, see `_compute_amount_company`
    amount = fields.Monetary(string='Amount', required=1)

    vendor_bill_move_ids = fields.Many2many(
        'account.move', compute='_compute_vendor_bill_move_ids',
        help="Vendor bill but also Vendor bill credit note")
    vendor_bill_move_count = fields.Integer(string='# Invoices', compute='_compute_vendor_bill_move_count', groups="account.group_account_manager")
    vendor_bill_move_line_ids = fields.Many2many('account.move.line', ondelete='restrict')

    @api.depends('vendor_bill_move_ids')
    def _compute_vendor_bill_move_count(self):
        for bonus in self:
            bonus.vendor_bill_move_count = len(bonus.vendor_bill_move_ids)

    @api.depends('vendor_bill_move_line_ids')
    def _compute_vendor_bill_move_ids(self):
        for bonus in self:
            bonus.vendor_bill_move_ids = bonus.vendor_bill_move_line_ids.move_id

    def action_view_invoices(self):
        action = self.env['ir.actions.act_window']._for_xml_id('gse_bonuses.action_view_invoices')
        # action['display_name'] = self.name
        action['domain'] = [('id', 'in', self.vendor_bill_move_ids.ids)]
        context = action['context'].replace('active_id', str(self.id))
        action['context'] = ast.literal_eval(context)
        return action

    def generate_bonuses(self, order):
        if not order:
            return

        if not (order.date_order > fields.Datetime.from_string('2023-05-31 23:59:59')):
            # This should not but a `raise UserError()` because you still want
            # to validate SO after that date but just not generating bonuses.
            logger.info("Impossible de générer un bonus pour une SO validée avant le 1er juin 2023 (SO %s %s).", order.id, order.date_order)
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

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        if not order.order_line.filtered(
            lambda line:
            not (line.is_downpayment or line.display_type or (line.product_id.type == 'service' and line.product_id.service_tracking == 'no'))
            and float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) >= 0
        ):
            # Not all deliverable products have been delivered
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
                bonus.add_bonus_on_vendor_bill()

            # Safety check
            assert task_total_hours == total_timesheet_unit_amount, "Total hours spent on task does not match timesheet sum."

    def add_bonus_on_vendor_bill(self, credit_note=False):
        """ Create or update vendor bill with new bonus. """
        Move = self.env['account.move'].with_context(skip_invoice_sync=False)

        self.ensure_one()

        journal = self.order_id.company_id.bonus_journal_id
        if not journal:
            raise UserError("Aucun journal pour les bonus n'est sélectionné")
        if not journal.default_account_id:
            raise UserError("Le journal sélectionné %r pour les bonus n'a pas de `default_account_id`" % journal.name)

        partner_id = self.employee_id.address_home_id.id
        if not partner_id:
            raise UserError("L'employé n'a pas d'adresse enregistrée.")

        move_type = 'in_refund' if credit_note else 'in_invoice'

        move = Move.search([
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', move_type),
            ('partner_id', '=', partner_id),
            ('journal_id', '=', journal.id),
            ('state', '=', 'draft'),
        ], limit=1)
        if not move:
            vals = {
                'company_id': self.company_id.id,
                'move_type': move_type,
                'partner_id': partner_id,
                'invoice_date': self.write_date,
                'date': self.write_date,
                'ref': 'Commission for SO %s' % self.order_id.name,
            }
            if not credit_note:
                # if credit note, let journal be found
                vals['journal_id'] = journal.id
            move = Move.create(vals)
        move_line = self.env['account.move.line'].with_context(skip_invoice_sync=False).create({
            'move_id': move.id,
            'product_id': self.company_id.bonus_product_id.id,
            'name': 'Commission for SO %s (SOL: %s)' % (self.order_id.name, self.so_line.name),
            # bonus amount is negative if bonus from credit note, but in
            # credit note itself the line need to be positive
            'price_unit': -self.amount if credit_note else self.amount,
            'tax_ids': None,
        })
        self.vendor_bill_move_line_ids = [Command.link(move_line.id)]

    def revert(self):
        """ Revert a bonus:
        - If it's already paid, it should generate a vendor bill credit note
          with the same amount
        - If it's not yet paid, it should simply remove the bonus itself """
        self.ensure_one()  # TODO: Make it multi

        # TODO: Don't revert the bonus if the vendor bill is not
        # paid yet, just remove the bonus from there.
        # Once done, add a test for it in `test_02_bonus` too
        bonus = self
        revert_bonus = bonus.copy({'amount': -bonus.amount})
        revert_bonus.add_bonus_on_vendor_bill(credit_note=True)
        move_ids = (bonus + revert_bonus).vendor_bill_move_ids
        (bonus + revert_bonus).write({'vendor_bill_move_ids': move_ids.ids})
