# -*- coding: utf-8 -*-

from odoo import models, fields


# This is actually the timesheet model
class AnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    bonuses_ids = fields.One2many('gse.bonus', 'timesheet_id')
