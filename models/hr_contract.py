from odoo import fields, models


class Contract(models.Model):
    _inherit = 'hr.contract'

    allow_transport_expenses = fields.Boolean("Allow Technician Transport Expenses")
