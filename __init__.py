# -*- coding: utf-8 -*-

from . import models

"""
TODO:
- When SO is canceled, the bonus is correctly deleted.
  Need to triple check other flows that would lead to a "not fully invoiced/paid/delivered/task done" state too
  Eg task/payment/delivery is canceled -> Is that possible? Doesn't it cancel the confirmed SO?
- Check multi currency: if SO is not in $, generate commission not in $ but vendor bill should be in $
- "On the Invoice, there should be a "Calculate Bonus" button that will trigger the computation of the bonus."
  -> It's auto now, you want it manual?
  -> Could add a Regenerate button from SO
"""
