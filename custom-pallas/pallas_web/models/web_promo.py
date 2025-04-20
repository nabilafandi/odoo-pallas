from odoo import fields, models

class WebPromo(models.Model):
    _name = 'web.promo'
    _description = 'Web Promo Page'

    name = fields.Char(string='Name')
    banner_image = fields.Binary(string='Banner Image')
    promo_ids = fields.One2many('promo.line','promo_id',string="Promos")

class PromoLine(models.Model):
    _name = 'promo.line'
    _description = 'Promo Lines'

    name = fields.Char(string='Name')
    description = fields.Text(string='Description')
    image = fields.Binary(string='Image', required=True)
    promo_id = fields.Many2one('web.promo')

