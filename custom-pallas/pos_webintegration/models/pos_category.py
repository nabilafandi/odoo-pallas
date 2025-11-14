from odoo import fields, models, api


class ModelName(models.Model):
    _inherit = 'pos.category'
    _parent_store = True


    @api.depends('parent_path')
    def _compute_parents_and_self(self):
        for category in self:
            if category.parent_path:
                category.parents_and_self = self.env['pos.category'].browse(
                    [int(p) for p in category.parent_path.split('/')[:-1]])
            else:
                category.parents_and_self = category

    parents_and_self = fields.Many2many(
        comodel_name='pos.category',
        compute='_compute_parents_and_self',
    )
    product_tmpl_ids = fields.Many2many(
        comodel_name='product.template',
        relation='product_pos_category_product_template_rel',
    )
    parent_path = fields.Char(index=True)

