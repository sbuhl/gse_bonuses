# coding: utf-8

from freezegun import freeze_time
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import common


class TestBonus(common.TransactionCase):
    def setUp(self):
        super().setUp()

        self.analytic_plan = self.env['account.analytic.plan'].create({
            'name': 'Plan Test',
            'company_id': False,
        })
        self.analytic_account_sale = self.env['account.analytic.account'].create({
            'name': 'Project for selling timesheet - AA',
            'plan_id': self.analytic_plan.id,
            'code': 'AA-2030'
        })
        self.project_global = self.env['project.project'].create({
            'name': 'Global Project',
            'analytic_account_id': self.analytic_account_sale.id,
            'allow_billable': True,
        })
        uom_hour = self.env.ref('uom.product_uom_hour')
        self.product_order_task_labor_generator = self.env['product.product'].create({
            'name': "labor generator",
            'standard_price': 300,
            'list_price': 300,
            'bonus_rate': 10,
            'type': 'service',
            'invoice_policy': 'order',
            'uom_id': uom_hour.id,
            'uom_po_id': uom_hour.id,
            'default_code': 'SERV-ORDERED',
            'service_tracking': 'task_global_project',
            'project_id': self.project_global.id,
            'taxes_id': None,
        })
        self.product_order_task_labor_installation = self.env['product.product'].create({
            'name': "labor installation",
            'standard_price': 100,
            'list_price': 100,
            'bonus_rate': 50,
            'type': 'service',
            'invoice_policy': 'order',
            'uom_id': uom_hour.id,
            'uom_po_id': uom_hour.id,
            'default_code': 'SERV-ORDERED2',
            'service_tracking': 'task_global_project',
            'project_id': self.project_global.id,
            'taxes_id': None,
        })
        self.partner = self.env['res.partner'].create({'name': "Test Bonus Partner 1"})
        self.partner2 = self.env['res.partner'].create({'name': "Test Bonus Partner 2"})
        self.employee1 = self.env['hr.employee'].create({
            'name': 'Employee 1',
            'address_home_id': self.partner.id,
        })
        self.employee2 = self.env['hr.employee'].create({
            'name': 'Employee 2',
            'address_home_id': self.partner2.id,
        })

    def get_vendor_bill(self, bonuses):
        """ Given some bonuses, return the DRAFT vendor bill for the partner
        of the first given bonuses.
        """
        return self.env['account.move'].search([
            ('company_id', '=', bonuses[0].company_id.id),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', bonuses[0].employee_id.address_home_id.id),
            ('journal_id', '=', bonuses[0].company_id.bonus_journal_id.id),
            ('state', '=', 'draft'),
        ])

    def simulate_bonus_flow(self, add_timesheets=True, pay_invoice=True):
        """ Simulate the full complete flow related to bonuses:
        - Create a SO with 2 labor lines
        - Validate the SO, which generates 2 tasks
        - Add some timesheet on each task
        - Generate and pay the invoice
        - Mark task as done and delivered
        """
        AccountAnalyticLine = self.env['account.analytic.line']
        SaleOrder = self.env['sale.order'].with_context(tracking_disable=True)
        SaleOrderLine = self.env['sale.order.line'].with_context(tracking_disable=True)

        sale_order = SaleOrder.create({
            'partner_id': self.partner.id,
            'partner_invoice_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
        })
        so_line_order_task_labor_generator = SaleOrderLine.create({
            'product_id': self.product_order_task_labor_generator.id,
            'product_uom_qty': 1,
            'order_id': sale_order.id,
        })
        so_line_order_task_labor_installation = SaleOrderLine.create({
            'product_id': self.product_order_task_labor_installation.id,
            'product_uom_qty': 1,
            'order_id': sale_order.id,
        })
        sale_order.action_confirm()

        # Generate some timesheet for the service task
        task_labor_generator = self.env['project.task'].search([('sale_line_id', '=', so_line_order_task_labor_generator.id)])
        task_labor_installation = self.env['project.task'].search([('sale_line_id', '=', so_line_order_task_labor_installation.id)])

        timesheet1 = timesheet2 = timesheet3 = AccountAnalyticLine
        if add_timesheets:
            timesheet1 = AccountAnalyticLine.create({
                'name': 'Tech 1 = 10h on labor generator',
                'project_id': task_labor_generator.project_id.id,
                'task_id': task_labor_generator.id,
                'unit_amount': 10,
                'employee_id': self.employee1.id,
            })
            timesheet2 = AccountAnalyticLine.create({
                'name': 'Tech 2 = 20h on labor Installation',
                'project_id': task_labor_installation.project_id.id,
                'task_id': task_labor_installation.id,
                'unit_amount': 20,
                'employee_id': self.employee2.id,
            })
            timesheet3 = AccountAnalyticLine.create({
                'name': 'Tech 1 = 30h on labor Installation',
                'project_id': task_labor_installation.project_id.id,
                'task_id': task_labor_installation.id,
                'unit_amount': 30,
                'employee_id': self.employee1.id,
            })

        if pay_invoice:
            # Generate invoice
            invoice1 = sale_order._create_invoices()[0]
            invoice1.action_post()

            # Pay invoice
            journal = self.env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', sale_order.company_id.id)], limit=1)
            register_payments = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=invoice1.id).create({
                'journal_id': journal.id,
            })
            register_payments._create_payments()

        # Mark task as done and delivered
        task_labor_generator.stage_id = 3  # Done
        task_labor_installation.stage_id = 3  # Done
        so_line_order_task_labor_generator.qty_delivered = so_line_order_task_labor_generator.product_uom_qty
        so_line_order_task_labor_installation.qty_delivered = so_line_order_task_labor_installation.product_uom_qty

        return sale_order, timesheet1, timesheet2, timesheet3

    def test_01_bonus(self):
        existing_bonuses = self.env['gse.bonus'].search([])
        # Create SO + SOL

        sale_order, timesheet1, timesheet2, timesheet3 = self.simulate_bonus_flow()

        # Ensure bonuses are created as expected, replicating the example in
        # `__manifest__.py`
        bonuses_flow1 = self.env['gse.bonus'].search([]) - existing_bonuses
        self.assertEqual(len(bonuses_flow1), 3)
        self.assertTrue(all(bonus.order_id == sale_order for bonus in bonuses_flow1))
        # Bonus 1
        self.assertEqual(bonuses_flow1[0].amount, 30)
        self.assertEqual(bonuses_flow1[0].employee_id, self.employee1)
        self.assertEqual(bonuses_flow1[0].timesheet_id, timesheet3)
        # Bonus 2
        self.assertEqual(bonuses_flow1[1].amount, 20)
        self.assertEqual(bonuses_flow1[1].employee_id, self.employee2)
        self.assertEqual(bonuses_flow1[1].timesheet_id, timesheet2)
        # Bonus 3
        self.assertEqual(bonuses_flow1[2].amount, 30)
        self.assertEqual(bonuses_flow1[2].employee_id, self.employee1)
        self.assertEqual(bonuses_flow1[2].timesheet_id, timesheet1)

        vendor_bill_employee1 = self.get_vendor_bill(bonuses_flow1[0])
        vendor_bill_employee2 = self.get_vendor_bill(bonuses_flow1[1])
        self.assertEqual(len(vendor_bill_employee1.invoice_line_ids), 2)
        self.assertEqual(len(vendor_bill_employee2.invoice_line_ids), 1)
        self.assertTrue(vendor_bill_employee1.amount_total == vendor_bill_employee1.amount_untaxed == 60)
        self.assertTrue(vendor_bill_employee2.amount_total == vendor_bill_employee2.amount_untaxed == 20)

        # Run a second time the flow to ensure it's using the same vendor bill
        self.simulate_bonus_flow()
        self.assertEqual(len(vendor_bill_employee1.invoice_line_ids), 4)
        self.assertEqual(len(vendor_bill_employee2.invoice_line_ids), 2)
        self.assertTrue(vendor_bill_employee1.amount_total == vendor_bill_employee1.amount_untaxed == 120)
        self.assertTrue(vendor_bill_employee2.amount_total == vendor_bill_employee2.amount_untaxed == 40)

        # Pay vendor bill of employee 1
        vendor_bill_employee1.action_post()
        journal = self.env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', sale_order.company_id.id)], limit=1)
        register_payments = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=vendor_bill_employee1.id).create({
            'journal_id': journal.id,
        })
        register_payments._create_payments()

        # Now check that running the flow again will create a new vendor bill
        # for employee 1 (as the existing one got paid) but not for employee 2
        sale_order_bonus_not_paid, _, _, _ = self.simulate_bonus_flow()
        self.assertEqual(len(vendor_bill_employee1.invoice_line_ids), 4)
        self.assertEqual(len(vendor_bill_employee2.invoice_line_ids), 3)
        self.assertTrue(vendor_bill_employee1.amount_total == vendor_bill_employee1.amount_untaxed == 120)
        self.assertTrue(vendor_bill_employee2.amount_total == vendor_bill_employee2.amount_untaxed == 60)
        new_vendor_bill_employee1 = self.env['account.move'].search([], order='id desc', limit=1)
        self.assertEqual(len(new_vendor_bill_employee1.invoice_line_ids), 2)
        self.assertTrue(new_vendor_bill_employee1.amount_total == new_vendor_bill_employee1.amount_untaxed == 60)

        # TEST 2: If `generate_bonuses` is somehow called again, it should not
        # generate bonuses for timesheet which already received a bonus
        before_bonuses = self.env['gse.bonus'].search([])
        before_moves = self.env['account.move'].search([])
        self.env['gse.bonus'].generate_bonuses(sale_order)
        self.assertEqual(before_bonuses, self.env['gse.bonus'].search([]))
        self.assertEqual(before_moves, self.env['account.move'].search([]))

        # TEST 3: If the SO is canceled but bonus are paid, it should not let
        #         you do it
        with self.assertRaises(UserError):
            sale_order.action_cancel()

        # TEST 4: But if the bonus are not paid, it should work and delete the
        #         bonuses
        self.assertEqual(len(sale_order_bonus_not_paid.bonuses_ids), 3)
        sale_order_bonus_not_paid.action_cancel()
        self.assertEqual(len(sale_order_bonus_not_paid.bonuses_ids), 0)

        # TEST 5: Generating the bonus when no timesheet is set should not fail
        self.simulate_bonus_flow(add_timesheets=False)

    def test_02_bonus(self):
        """ TODO: Create a test for the client invoice which receive a credit
        note and which then generate a negative bonus to "cancel" a previously
        paid bonus genrated from the client invoice that got "note credited".
        See `out_refund` in `_invoice_paid_hook`.
        """
        self.simulate_bonus_flow()
        self.env.cr.commit()

    def test_03_bonus(self):
        # Orders from before June 2023 should not grant any bonuses
        existing_bonuses = self.env['gse.bonus'].search([])
        datetime = '2023-05-31 12:00:00'
        with freeze_time(datetime), patch.object(self.env.cr, 'now', lambda: datetime):
            self.simulate_bonus_flow()
        bonuses_flow1 = self.env['gse.bonus'].search([]) - existing_bonuses
        self.assertFalse(bonuses_flow1, "no bonuses should have been created because SO from before June 2023")
