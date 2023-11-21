from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()

        # For the pickings related to a sale order, generate bonuses
        # TODO: Perf possible imp: Check if possible to exclude picking not
        #       related to `service_tracking` SOL.
        #       Looks like there is no direct relation to a SOL from a task,
        #       would need an inverse field from SOL.task_id, not worth it?
        for order_sudo in self.sudo().sale_id:
            self.env['gse.bonus'].generate_bonuses(order_sudo)

        return res
