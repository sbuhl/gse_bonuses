from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    disallow_transport_expenses = fields.Boolean("Exclude from Technician Transport Expenses")
    disallow_transport_expenses_reason = fields.Text("Reason", tracking=True)

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            for task in self.filtered(lambda t: t.stage_id.name == 'Done'):
                self.env['gse.bonus'].generate_bonuses(task.sale_order_id)
        return res
