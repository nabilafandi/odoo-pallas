from odoo import fields, models

class WebHome(models.Model):
    _name = 'web.home'
    _description = 'Web Home Page'

    tagline = fields.Char(string='Tagline')
    background_image = fields.Binary(string="Background Image")
