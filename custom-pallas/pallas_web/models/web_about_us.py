from odoo import fields, models, api
from odoo.exceptions import ValidationError
class WebAboutUs(models.Model):
    _name = 'web.about.us'
    _description = 'About Us Page Content'

    title = fields.Char(string='Title', required=True)
    title_image = fields.Binary(string='Title Image')
    tagline = fields.Text(string='Tagline')
    description = fields.Text(string='Description')
    event_images = fields.One2many('event.image', 'about_us_id', string='Events Images')

    @api.model
    def create(self, vals):
        # Check if a record already exists
        if self.search_count([]) >= 1:
            raise ValidationError("Only one 'About Us' record is allowed.")
        return super(WebAboutUs, self).create(vals)

    _sql_constraints = [
        ('single_record', 'CHECK(1=1)', 'Only one record is allowed.'),
    ]
class EventImage(models.Model):
    _name = 'event.image'
    _description = 'Events Images'

    image = fields.Binary(string='Image', required=True)
    about_us_id = fields.Many2one('web.about.us', string='About Us')
