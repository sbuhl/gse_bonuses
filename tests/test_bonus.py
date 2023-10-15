# coding: utf-8

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
        self.product_order_service1 = self.env['product.product'].create({
            'name': "Service Ordered, create no task",
            'standard_price': 11,
            'list_price': 13,
            'type': 'service',
            'invoice_policy': 'order',
            'uom_id': uom_hour.id,
            'uom_po_id': uom_hour.id,
            'default_code': 'SERV-ORDERED1',
            'service_tracking': 'no',
            'project_id': False,
        })
        self.product_order_service2 = self.env['product.product'].create({
            'name': "Service Ordered, create task in global project",
            'standard_price': 30,
            'list_price': 90,
            'type': 'service',
            'invoice_policy': 'order',
            'uom_id': uom_hour.id,
            'uom_po_id': uom_hour.id,
            'default_code': 'SERV-ORDERED2',
            'service_tracking': 'task_global_project',
            'project_id': self.project_global.id,
        })
        self.partner = self.env['res.partner'].create({'name': "Mur en béton"})
        self.employee_user = self.env['hr.employee'].create({'name': 'Employee User'})

    def test_01_bonus(self):
        # Create SO + SOL
        SaleOrder = self.env['sale.order'].with_context(tracking_disable=True)
        SaleOrderLine = self.env['sale.order.line'].with_context(tracking_disable=True)
        sale_order = SaleOrder.create({
            'partner_id': self.partner.id,
            'partner_invoice_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
        })
        so_line_order_no_task = SaleOrderLine.create({
            'product_id': self.product_order_service1.id,
            'product_uom_qty': 10,
            'order_id': sale_order.id,
        })

        so_line_order_task_in_global = SaleOrderLine.create({
            'product_id': self.product_order_service2.id,
            'product_uom_qty': 10,
            'order_id': sale_order.id,
        })
        sale_order.action_confirm()
        task_serv2 = self.env['project.task'].search([('sale_line_id', '=', so_line_order_task_in_global.id)])
        timesheet1 = self.env['account.analytic.line'].create({
            'name': 'Test Line',
            'project_id': task_serv2.project_id.id,
            'task_id': task_serv2.id,
            'unit_amount': 10.5,
            'employee_id': self.employee_user.id,
        })
        timesheet2 = self.env['account.analytic.line'].create({
            'name': 'Test Line',
            'project_id': task_serv2.project_id.id,
            'task_id': task_serv2.id,
            'unit_amount': 39.5,
            'employee_id': self.employee_user.id,
        })
        timesheet3 = self.env['account.analytic.line'].create({
            'name': 'Test Line',
            'project_id': task_serv2.project_id.id,
            'unit_amount': 10,
            'employee_id': self.employee_user.id,
        })
        invoice1 = sale_order._create_invoices()[0]
        invoice1.action_post()
        # TODO: Pay invoice
        # TODO: Deliver regular product
        # TODO: Deliver timesheet product (set task as done?)
