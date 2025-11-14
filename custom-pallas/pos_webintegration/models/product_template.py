from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _apply_taxes_to_price(
            self, price, currency, product_taxes, taxes, product_or_template,
            website=None,
    ):
        website = website or self.env['website'].get_current_website()
        price = self.env['product.product']._get_tax_included_unit_price_from_price(
            price,
            product_taxes,
            product_taxes_after_fp=taxes,
        )
        show_tax = website.show_line_subtotals_tax_selection
        tax_display = 'total_excluded' if show_tax == 'tax_excluded' else 'total_included'

        # The list_price is always the price of one.
        return taxes.compute_all(
            price, currency, 1, product_or_template, self.env.user.partner_id
        )[tax_display]

    def _get_sales_prices(self, pos_config):
        if not self:
            return {}

        pricelist = pos_config.pricelist_id
        currency = pos_config.currency_id
        fiscal_position = pos_config.default_fiscal_position_id.sudo()
        date = fields.Date.context_today(self)

        pricelist_prices = pricelist._compute_price_rule(self, 1.0)
        # comparison_prices_enabled = self.env.user.has_group('website_sale.group_product_price_comparison')

        res = {}
        for template in self:
            pricelist_price, pricelist_rule_id = pricelist_prices[template.id]

            product_taxes = template.sudo().taxes_id._filter_taxes_by_company(self.env.company)
            taxes = fiscal_position.map_tax(product_taxes)

            base_price = None
            template_price_vals = {
                'price_reduce': self._apply_taxes_to_price(
                    pricelist_price, currency, product_taxes, taxes, template, website=website,
                ),
            }
            pricelist_item = template.env['product.pricelist.item'].browse(pricelist_rule_id)
            if pricelist_item._show_discount_on_shop():
                pricelist_base_price = pricelist_item._compute_price_before_discount(
                    product=template,
                    quantity=1.0,
                    date=date,
                    uom=template.uom_id,
                    currency=currency,
                )
                if currency.compare_amounts(pricelist_base_price, pricelist_price) == 1:
                    base_price = pricelist_base_price
                    template_price_vals['base_price'] = self._apply_taxes_to_price(
                        base_price, currency, product_taxes, taxes, template, website=website,
                    )

            if not base_price and comparison_prices_enabled and template.compare_list_price:
                template_price_vals['base_price'] = template.currency_id._convert(
                    template.compare_list_price,
                    currency,
                    self.env.company,
                    date,
                    round=False,
                )

            res[template.id] = template_price_vals

        return res
