# -*- coding: utf-8 -*-
from odoo import models


class IRExports(models.Model):
    _inherit = 'ir.exports'

    def name_get(self):
        if self.env.context.get('show_model', False):
            return [(record.id, f"{record.name} ({record.resource})") for record in self]
        else:
            return super().name_get()
