from odoo import fields, models

class WebLocation(models.Model):
    _name = 'web.location'
    _description = 'Web Location Page'

    name = fields.Char(string='Name')
    description = fields.Text(string='Description')
    address = fields.Text(string='Address')
    shop_hour = fields.Text(string='Shop Hours')
    telephone = fields.Char(string='Telephone')
    link_whatsapp = fields.Char(string='Link Whatsapp')
    link_map = fields.Char(string='Link Map')
    location_images = fields.One2many('location.image', 'location_id', string='Location Images')

class LocationImage(models.Model):
    _name = 'location.image'
    _description = 'location Images'

    image = fields.Binary(string='Image', required=True)
    location_id = fields.Many2one('web.location', string='Locations')