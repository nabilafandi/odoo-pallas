from odoo import http
from odoo.http import request, Response, content_disposition
import json
import base64
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from datetime import datetime
from odoo.addons.website.controllers.main import QueryURL
from werkzeug.exceptions import Forbidden, NotFound
from odoo.tools import clean_context, float_round, groupby, lazy, single_email_re, str2bool, SQL
from odoo.osv import expression
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.main import TableCompute
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo import fields
from odoo.addons.payment import utils as payment_utils


def get_base_url():
    """Helper method to get the base URL."""
    return "http://145.79.13.25:8069"
    # return request.httprequest.host_url.rstrip('/')

class ProductController(http.Controller):

    def _make_json_response(self, data, status=200):
        """Helper method to create a JSON response with common headers."""
        return request.make_response(
            json.dumps(data),
            headers={
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            status=status
        )

    

    def _get_record_or_error(self, model_name, error_message, limit=1, id=None):
        """Helper method to fetch a record or return an error response."""
        if not id:
            record = request.env[model_name].sudo().search([], limit=limit)
        else:
            record = request.env[model_name].sudo().browse(id)
        if not record:
            return None, self._make_json_response({'error': error_message}, status=404)
        return record, None

    @http.route('/api/product/category', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_category(self, **kwargs):
        categories, error_response = self._get_record_or_error('product.public.category', 'No information found.',
                                                               limit=0)
        if error_response:
            return error_response

        def process_category(category):
            """Recursively process a category and its children."""
            return {
                'id': category.id,
                'name': category.name,
                'description': category.website_description,
                'child_ids': [process_category(child) for child in category.child_id]
            }

        data = [process_category(category) for category in categories if not category.parent_id]
        return self._make_json_response(data)

    @http.route('/api/product/category/<int:category_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_by_category(self, category_id, **kwargs):
        category = request.env['product.public.category'].sudo().browse(category_id)
        products = request.env['product.template'].sudo().search([('public_categ_ids', '=', category_id)])
        if not category:
            return self._make_json_response({'error': 'No information found.'}, status=404)

        data = {
            "category": category.name,
            "products": [],
        }
        base_url = get_base_url()
        for product in products:
            data['products'].append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.list_price,
                "images": product.product_template_image_ids.mapped(lambda r: {"id": r.id,
                                                                               "image_url": f"{base_url}/web/image/{r._name}/{r.id}/image_1920" if r.image_1920 else None, }),
            })
        return self._make_json_response(data)

    @http.route('/api/product/<int:product_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_details(self, product_id, **kwargs):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product:
            return self._make_json_response({'error': 'No information found.'}, status=404)

        base_url = get_base_url()
        data = {
            "id": product.id,
            "name": product.name,
            "description": product.description_ecommerce,
            "price": product.list_price,
            "images": product.product_template_image_ids.mapped(lambda r: {"id": r.id,
                                                                           "image_url": f"{base_url}/web/image/{r._name}/{r.id}/image_1920" if r.image_1920 else None, }),
            "related_products": product.alternative_product_ids.mapped(lambda r: {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "price": r.list_price,
                "images": r.product_template_image_ids.mapped(lambda i: {"id": i.id,
                                                                         "image_url": f"{base_url}/web/image/{i._name}/{i.id}/image_1920" if i.image_1920 else None})
            }),
            "variants": product.product_variant_ids.mapped(lambda v: {
                "id": v.id,
                "name": v.display_name,
                "attributes": v.attribute_line_ids.mapped(lambda l: {
                    "attribute_id": l.attribute_id.id,
                    "value_ids": l.value_ids.ids
                }),
                "price": v.list_price,
            }),
            "attributes": product.attribute_line_ids.mapped(
                lambda l: {"id": l.attribute_id.id, "name": l.attribute_id.name,
                           "values": l.value_ids.mapped(lambda v: {"id": v.id, "name": v.name}),
                           })
        }
        return self._make_json_response(data)


class WebAdminController(http.Controller):

    def _make_json_response(self, data, status=200):
        """Helper method to create a JSON response with common headers."""
        return request.make_response(
            json.dumps(data),
            headers={
                'Content-Type': 'application/json',
                # 'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            },
            status=status
        )

    def _get_base_url(self):
        """Helper method to get the base URL."""
        # return request.httprequest.host_url.rstrip('/')
        return "http://145.79.13.25:8069"

    def _get_record_or_error(self, model_name, error_message):
        """Helper method to fetch a record or return an error response."""
        record = request.env[model_name].sudo().search([], limit=1)
        if not record:
            return None, self._make_json_response({'error': error_message}, status=404)
        return record, None

    def _get_public_image_url(self, model, rec_id, field):
        """Generate URL for public image access"""
        return f"{get_base_url()}/api/public/image/{model}/{rec_id}/{field}"

    @http.route('/api/public/image/<string:model>/<int:id>/<string:field>',
                type='http', auth="public", methods=['GET'], csrf=False)
    def get_public_image(self, model, id, field, **kwargs):
        """Public endpoint to serve images without authentication"""
        record = request.env[model].sudo().browse(id)
        if record and record[field]:
            image_data = base64.b64decode(record[field])
            return request.make_response(
                image_data,
                headers=[
                    ('Content-Type', 'image/jpeg'),
                    ('Content-Disposition', content_disposition(f'{field}.jpg')),
                    ('Cache-Control', 'public, max-age=86400'),  # 1 day cache
                    ('Access-Control-Allow-Origin', '*')
                ]
            )
        return request.not_found()

    @http.route('/api/about-us', type='http', auth='public', methods=['GET'], csrf=False)
    def get_about_us(self, **kwargs):
        print('dsadsad')
        about_us, error_response = self._get_record_or_error('web.about.us', 'No information found.')
        if error_response:
            return error_response

        base_url = get_base_url()
        data = {
            'company_name': request.env.user.company_id.name,
            'title': about_us.title,
            'title_image_url': self._get_public_image_url('web.about.us', about_us.id,
                                                          'title_image') if about_us.title_image else None,
            'tagline': about_us.tagline,
            'description': about_us.description,
            'event_images': [
                {'id': img.id, 'url': self._get_public_image_url(img._name, img.id, 'image')} for img in
                about_us.event_images
            ] if about_us.event_images else []
        }

        return self._make_json_response(data)

    @http.route('/api/home', type='http', auth='public', methods=['GET'], csrf=False)
    def get_home(self, **kwargs):
        home, error_response = self._get_record_or_error('web.home', 'No information found.')
        if error_response:
            return error_response

        base_url = get_base_url()
        data = {
            'tagline': home.tagline,
            'background_image': self._get_public_image_url('web.home', home.id,
                                                           'background_image') if home.background_image else None,
        }

        return self._make_json_response(data)

    @http.route('/api/location', type='http', auth='public', methods=['GET'], csrf=False)
    def get_location(self, **kwargs):
        location, error_response = self._get_record_or_error('web.location', 'No information found.')
        if error_response:
            return error_response

        base_url = get_base_url()
        data = {
            'name': location.name,
            'description': location.description,
            'address': location.address,
            'shop_hour': location.shop_hour,
            'telephone': location.telephone,
            'link_whatsapp': location.link_whatsapp,
            'link_map': location.link_map,
            'location_images': [
                {
                    'id': img.id,
                    'url': self._get_public_image_url(img._name, img.id, 'image') if img.image else None,
                }
                for img in location.location_images
            ],
        }

        return self._make_json_response(data)

    @http.route('/api/promo', type='http', auth='public', methods=['GET'], csrf=False)
    def get_promo(self, **kwargs):
        promo, error_response = self._get_record_or_error('web.promo', 'No information found.')
        if error_response:
            return error_response

        base_url = get_base_url()
        data = {
            "name": promo.name,
            "banner_image": self._get_public_image_url('web.promo', promo.id,
                                                       'banner_image') if promo.banner_image else None,
            "promo_lines": [
                {"id": line.id, "name": line.name, "description": line.description,
                 "image_url": self._get_public_image_url(line._name, line.id, 'image') if line.image else None,
                 # "image_url":f"{base_url}/web/image/{line._name}/{line.id}/image",
                 }
                for line in promo.promo_ids
            ]
        }

        return self._make_json_response(data)


class CustomWebsiteSale(WebsiteSale):
    def _get_base_url(self):
        """Helper method to get the base URL."""
        return request.httprequest.host_url.rstrip('/')

    @http.route('/api/cart/view', type='http', auth='public', website=True, methods=['GET'], csrf=False)
    def cart_view(self, **kwargs):
        base_url = get_base_url()
        if not request.website.has_ecommerce_access():
            return request.redirect('/web/login')

        order = request.website.sale_get_order()
        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()
        request.session['website_sale_cart_quantity'] = order.cart_quantity
        cart_items = order.website_order_line
        order_lines = []
        for item in cart_items:
            line_vals = {
                'line_id': item.id,
                'product_id': item.product_id.id,
                'image': item.product_id.product_template_image_ids.mapped(lambda r: {"id": r.id,
                                                                                      "image_url": f"{base_url}/web/image/{r._name}/{r.id}/image_1920" if r.image_1920 else None, })[
                    0],
                'name': item.name_short,
                'quantity': item.product_qty,
                'price_unit': item.price_unit,
                'subtotal': item._get_cart_display_price(),
            }
            order_lines.append(line_vals)
        cart = {
            'order_id': order.id,
            'total': order.amount_total,
            'lines': order_lines,
        }
        return self._make_json_response(cart)

    @http.route(['/api/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update_json(self, product_id=None, line_id=None, add_qty=None, set_qty=None, display=True,
                         product_custom_attribute_values=None, no_variant_attribute_value_ids=None, **kwargs):

        payload = json.loads(request.httprequest.data.decode('utf-8'))
        product_id = payload.get('product_id')
        product_template_id = payload.get('product_template_id')
        attribute_value_ids = payload.get('attribute_value_ids')
        line_id = payload.get('line_id')
        add_qty = payload.get('add_qty')
        set_qty = payload.get('set_qty')
        display = payload.get('display')
        product_custom_attribute_values = payload.get('product_custom_attribute_values')
        no_variant_attribute_value_ids = payload.get('no_variant_attribute_value_ids')

        if product_template_id and attribute_value_ids:
            product_template = request.env['product.template'].browse(product_template_id)
            template_attribute_values = request.env['product.template.attribute.value'].search([
                ('product_tmpl_id', '=', product_template.id),
                ('product_attribute_value_id', 'in', attribute_value_ids)
            ])
            product_id = product_template._get_variant_id_for_combination(template_attribute_values)
        """
        This route is called :
            - When changing quantity from the cart.
            - When adding a product from the wishlist.
            - When adding a product to cart on the same page (without redirection).
        """
        order = request.website.sale_get_order(force_create=True)
        if order.state != 'draft':
            request.website.sale_reset()
            if kwargs.get('force_create'):
                order = request.website.sale_get_order(force_create=True)
            else:
                return {}

        if product_custom_attribute_values:
            product_custom_attribute_values = json_scriptsafe.loads(product_custom_attribute_values)

        # old API, will be dropped soon with product configurator refactorings
        no_variant_attribute_values = kwargs.pop('no_variant_attribute_values', None)
        if no_variant_attribute_values and no_variant_attribute_value_ids is None:
            no_variants_attribute_values_data = json_scriptsafe.loads(no_variant_attribute_values)
            no_variant_attribute_value_ids = [
                int(ptav_data['value']) for ptav_data in no_variants_attribute_values_data
            ]

        values = order._cart_update(
            product_id=product_id,
            line_id=line_id,
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            **kwargs
        )
        # If the line is a combo product line, and it already has combo items, we need to update
        # the combo item quantities as well.
        line = request.env['sale.order.line'].browse(values['line_id'])
        if line.product_type == 'combo' and line.linked_line_ids:
            for linked_line_id in line.linked_line_ids:
                if values['quantity'] != linked_line_id.product_uom_qty:
                    order._cart_update(
                        product_id=linked_line_id.product_id.id,
                        line_id=linked_line_id.id,
                        set_qty=values['quantity'],
                    )

        values['notification_info'] = self._get_cart_notification_information(order, [values['line_id']])
        values['notification_info']['warning'] = values.pop('warning', '')
        request.session['website_sale_cart_quantity'] = order.cart_quantity

        if not order.cart_quantity:
            request.website.sale_reset()
            return values

        values['cart_quantity'] = order.cart_quantity
        values['minor_amount'] = payment_utils.to_minor_currency_units(
            order.amount_total, order.currency_id
        )
        values['amount'] = order.amount_total

        if not display:
            return values

        values['cart_ready'] = order._is_cart_ready()
        values['website_sale.cart_lines'] = request.env['ir.ui.view']._render_template(
            "website_sale.cart_lines", {
                'website_sale_order': order,
                'date': fields.Date.today(),
                'suggested_products': order._cart_accessories()
            }
        )
        values['website_sale.total'] = request.env['ir.ui.view']._render_template(
            "website_sale.total", {
                'website_sale_order': order,
            }
        )
        return values

    @http.route(['/api/cart/add'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(
            self, product_id, add_qty=1, set_qty=0, product_custom_attribute_values=None,
            no_variant_attribute_value_ids=None, **kwargs
    ):
        payload = json.loads(request.httprequest.data.decode('utf-8'))
        product_id = payload['product_id']
        add_qty = payload.get('add_qty')
        set_qty = payload.get('set_qty')
        product_custom_attribute_values = payload.get('product_custom_attribute_values')
        no_variant_attribute_value_ids = payload.get('no_variant_attribute_value_ids')

        """This route is called when adding a product to cart (no options)."""
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        if product_custom_attribute_values:
            product_custom_attribute_values = json_scriptsafe.loads(product_custom_attribute_values)

        # old API, will be dropped soon with product configurator refactorings
        no_variant_attribute_values = kwargs.pop('no_variant_attribute_values', None)
        if no_variant_attribute_values and no_variant_attribute_value_ids is None:
            no_variants_attribute_values_data = json_scriptsafe.loads(no_variant_attribute_values)
            no_variant_attribute_value_ids = [
                int(ptav_data['value']) for ptav_data in no_variants_attribute_values_data
            ]

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            **kwargs
        )

        request.session['website_sale_cart_quantity'] = sale_order.cart_quantity

        return request.redirect("/shop/cart")

    def _make_json_response(self, data, status=200):
        """Helper method to create a JSON response with common headers."""
        return request.make_response(
            json.dumps(data),
            headers={
                'Content-Type': 'application/json',
                # 'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            },
            status=status
        )

    def sitemap_shop(env, rule, qs):
        website = env['website'].get_current_website()
        if website and website.ecommerce_access == 'logged_in' and not qs:
            # Make sure urls are not listed in sitemap when restriction is active
            # and no autocomplete query string is provided
            return

        if not qs or qs.lower() in '/shop':
            yield {'loc': '/shop'}

        Category = env['product.public.category']
        dom = sitemap_qs2dom(qs, '/shop/category', Category._rec_name)
        dom += website.website_domain()
        for cat in Category.search(dom):
            loc = '/shop/category/%s' % env['ir.http']._slug(cat)
            if not qs or qs.lower() in loc:
                yield {'loc': loc}

    @http.route('/shop/route', type='http', auth="public", website=True, sitemap=sitemap_shop)
    def shop_json(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, **post):
        if not request.website.has_ecommerce_access():
            return request.redirect('/web/login')
        try:
            min_price = float(min_price)
        except ValueError:
            min_price = 0
        try:
            max_price = float(max_price)
        except ValueError:
            max_price = 0

        Category = request.env['product.public.category']
        if category:
            category = Category.search([('id', '=', int(category))], limit=1)
            if not category or not category.can_access_from_current_website():
                raise NotFound()
        else:
            category = Category

        website = request.env['website'].get_current_website()
        website_domain = website.website_domain()
        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = website.shop_ppg or 20

        ppr = website.shop_ppr or 4

        gap = website.shop_gap or "16px"

        request_args = request.httprequest.args
        attrib_list = request_args.getlist('attribute_value')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}
        if attrib_list:
            post['attribute_value'] = attrib_list

        filter_by_tags_enabled = website.is_view_active('website_sale.filter_products_tags')
        if filter_by_tags_enabled:
            tags = request_args.getlist('tags')
            # Allow only numeric tag values to avoid internal error.
            if tags and all(tag.isnumeric() for tag in tags):
                post['tags'] = tags
                tags = {int(tag) for tag in tags}
            else:
                post['tags'] = None
                tags = {}

        keep = QueryURL('/shop',
                        **self._shop_get_query_url_kwargs(category and int(category), search, min_price, max_price,
                                                          **post))

        now = datetime.timestamp(datetime.now())
        pricelist = website.pricelist_id
        if 'website_sale_pricelist_time' in request.session:
            # Check if we need to refresh the cached pricelist
            pricelist_save_time = request.session['website_sale_pricelist_time']
            if pricelist_save_time < now - 60 * 60:
                request.session.pop('website_sale_current_pl', None)
                website.invalidate_recordset(['pricelist_id'])
                pricelist = website.pricelist_id
                request.session['website_sale_pricelist_time'] = now
                request.session['website_sale_current_pl'] = pricelist.id
        else:
            request.session['website_sale_pricelist_time'] = now
            request.session['website_sale_current_pl'] = pricelist.id

        filter_by_price_enabled = website.is_view_active('website_sale.filter_products_price')
        if filter_by_price_enabled:
            company_currency = website.company_id.sudo().currency_id
            conversion_rate = request.env['res.currency']._get_conversion_rate(
                company_currency, website.currency_id, request.website.company_id, fields.Date.today())
        else:
            conversion_rate = 1

        url = '/shop'
        if search:
            post['search'] = search

        options = self._get_search_options(
            category=category,
            attrib_values=attrib_values,
            min_price=min_price,
            max_price=max_price,
            conversion_rate=conversion_rate,
            display_currency=website.currency_id,
            **post
        )
        fuzzy_search_term, product_count, search_product = self._shop_lookup_products(attrib_set, options, post, search,
                                                                                      website)

        filter_by_price_enabled = website.is_view_active('website_sale.filter_products_price')
        if filter_by_price_enabled:
            # TODO Find an alternative way to obtain the domain through the search metadata.
            Product = request.env['product.template'].with_context(bin_size=True)
            domain = self._get_shop_domain(search, category, attrib_values)

            # This is ~4 times more efficient than a search for the cheapest and most expensive products
            query = Product._where_calc(domain)
            Product._apply_ir_rules(query, 'read')
            sql = query.select(
                SQL(
                    "COALESCE(MIN(list_price), 0) * %(conversion_rate)s, COALESCE(MAX(list_price), 0) * %(conversion_rate)s",
                    conversion_rate=conversion_rate,
                )
            )
            available_min_price, available_max_price = request.env.execute_query(sql)[0]

            if min_price or max_price:
                # The if/else condition in the min_price / max_price value assignment
                # tackles the case where we switch to a list of products with different
                # available min / max prices than the ones set in the previous page.
                # In order to have logical results and not yield empty product lists, the
                # price filter is set to their respective available prices when the specified
                # min exceeds the max, and / or the specified max is lower than the available min.
                if min_price:
                    min_price = min_price if min_price <= available_max_price else available_min_price
                    post['min_price'] = min_price
                if max_price:
                    max_price = max_price if max_price >= available_min_price else available_max_price
                    post['max_price'] = max_price

        ProductTag = request.env['product.tag']
        if filter_by_tags_enabled and search_product:
            all_tags = ProductTag.search(
                expression.AND([
                    [('product_ids.is_published', '=', True), ('visible_on_ecommerce', '=', True)],
                    website_domain
                ])
            )
        else:
            all_tags = ProductTag

        categs_domain = [('parent_id', '=', False)] + website_domain
        if search:
            search_categories = Category.search(
                [('product_tmpl_ids', 'in', search_product.ids)] + website_domain
            ).parents_and_self
            categs_domain.append(('id', 'in', search_categories.ids))
        else:
            search_categories = Category
        categs = lazy(lambda: Category.search(categs_domain))

        if category:
            url = "/shop/category/%s" % request.env['ir.http']._slug(category)

        pager = website.pager(url=url, total=product_count, page=page, step=ppg, scope=5, url_args=post)
        offset = pager['offset']
        products = search_product[offset:offset + ppg]

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            attributes = lazy(lambda: ProductAttribute.search([
                ('product_tmpl_ids', 'in', search_product.ids),
                ('visibility', '=', 'visible'),
            ]))
        else:
            attributes = lazy(lambda: ProductAttribute.browse(attributes_ids))

        layout_mode = request.session.get('website_sale_shop_layout_mode')
        if not layout_mode:
            if website.viewref('website_sale.products_list_view').active:
                layout_mode = 'list'
            else:
                layout_mode = 'grid'
            request.session['website_sale_shop_layout_mode'] = layout_mode

        products_prices = lazy(lambda: products._get_sales_prices(website))

        attributes_values = request.env['product.attribute.value'].browse(attrib_set)
        sorted_attributes_values = attributes_values.sorted('sequence')
        multi_attributes_values = sorted_attributes_values.filtered(lambda av: av.display_type == 'multi')
        single_attributes_values = sorted_attributes_values - multi_attributes_values
        grouped_attributes_values = list(groupby(single_attributes_values, lambda av: av.attribute_id.id))
        grouped_attributes_values.extend([(av.attribute_id.id, [av]) for av in multi_attributes_values])

        selected_attributes_hash = grouped_attributes_values and "#attribute_values=%s" % (
            ','.join(str(v[0].id) for k, v in grouped_attributes_values)
        ) or ''

        values = {
            'search': fuzzy_search_term or search,
            'original_search': fuzzy_search_term and search,
            'order': post.get('order', ''),
            'category': category,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'products': products,
            'search_product': search_product,
            'search_count': product_count,  # common for all searchbox
            'bins': lazy(lambda: TableCompute().process(products, ppg, ppr)),
            'ppg': ppg,
            'ppr': ppr,
            'gap': gap,
            'categories': categs,
            'attributes': attributes,
            'keep': keep,
            'selected_attributes_hash': selected_attributes_hash,
            'search_categories_ids': search_categories.ids,
            'layout_mode': layout_mode,
            'products_prices': products_prices,
            'get_product_prices': lambda product: lazy(lambda: products_prices[product.id]),
            'float_round': float_round,
        }
        if filter_by_price_enabled:
            values['min_price'] = min_price or available_min_price
            values['max_price'] = max_price or available_max_price
            values['available_min_price'] = float_round(available_min_price, 2)
            values['available_max_price'] = float_round(available_max_price, 2)
        if filter_by_tags_enabled:
            values.update({'all_tags': all_tags, 'tags': tags})
        if category:
            values['main_object'] = category
        values.update(self._get_additional_extra_shop_values(values, **post))
        print(values)

        return self._make_json_response(values, 200)

    @http.route('/api/cart/add', type='http', auth='public', methods=['POST'], csrf=False)
    def add_to_cart(self, product_id=None, quantity=1, **kwargs):
        """API endpoint to add product to cart."""
        if not product_id:
            return self._make_json_response({'error': 'Missing product_id'}, status=400)

        try:
            product_id = int(product_id)
            quantity = float(quantity)
        except (ValueError, TypeError):
            return self._make_json_response({'error': 'Invalid input format'}, status=400)

        # Get current website and pricelist
        website = request.website
        pricelist = website.pricelist_id

        # Fetch product template
        product = request.env['product.product'].sudo().browse(product_id)
        if not product.exists() or not product.is_published:
            return self._make_json_response({'error': 'Product not found or unavailable'}, status=404)

        # Get or create sale order (cart)
        order = website._get_current_pricelist()
        if not order:
            order = website._create_empty_carrier_session()

        # Add product to cart
        order._cart_update(product_id=product_id, add_qty=quantity)

        return self._make_json_response({
            'message': 'Product added successfully',
            'cart_total': len(order.order_line),
            'product_id': product_id,
            'quantity': quantity
        }, status=200)
