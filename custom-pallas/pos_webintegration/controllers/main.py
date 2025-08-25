from odoo import http
import json
from odoo.addons.pos_self_order.controllers.self_entry import PosSelfKiosk
from odoo.http import request, Response, content_disposition
from datetime import date, datetime

from odoo.osv import expression


def get_base_url():
    """Helper method to get the base URL."""
    # return "http://145.79.13.25:8069"
    return request.httprequest.host_url.rstrip('/')

def inject_image_urls(records, model_name,image_type):
    for record in records:
        if 'id' in record:
            record['image_url'] = f'{get_base_url()}/web/image/{model_name}/{record['id']}/{image_type}'
    return records

def serialize(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return 'long byte string'
    elif isinstance(obj, str) and len(obj) > 500:
        return 'long byte string'
    return obj

def sanitize(data):
    if isinstance(data, dict):
        data = {k: sanitize(v) for k, v in data.items()}
        return data
    elif isinstance(data, list):
        return [sanitize(item) for item in data]
    else:
        return serialize(data)

class PosStorefrontController(PosSelfKiosk):



    @http.route('/pos-storefront/categories/<config_id>', type='json', auth='public')
    def get_pos_category(self, config_id, access_token=None, table_identifier=None):
        pos_config_data = self.get_self_ordering_data(config_id, access_token, table_identifier)
        categories = pos_config_data.get('pos.category', {}).get('data', [])
        inject_image_urls(categories, 'pos.category', 'image_128')
        data = sanitize(categories)
        return data

    @http.route('/pos-storefront/products/<config_id>', type='json', auth='public')
    def get_pos_product(self, config_id, access_token=None, table_identifier=None):
        pos_config_data = self.get_self_ordering_data(config_id, access_token, table_identifier)
        products = pos_config_data.get('product.product', {}).get('data', [])
        inject_image_urls(products, 'product.product', 'image_128')
        data = sanitize(products)
        return data

    @http.route('/pos-storefront/general/<config_id>', type='http', auth='public', methods=['GET'])
    def get_pos_general(self, config_id=None, access_token=None, table_identifier=None):
        pos_config_data = self.get_self_ordering_data(config_id, access_token, table_identifier)
        data = sanitize(pos_config_data)

        return request.make_response(
            json.dumps(data),
            headers={
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
        )


    # def _get_search_domain(self, search, category, attrib_values):
    #     """Build a domain to search products.
    #
    #     This method can be overridden to add new search criteria.
    #     """
    #     domains = [[]]  # Add your base domain here if needed, e.g., [('available_in_pos', '=', True)]
    #     if search:
    #         for srch in search.split(" "):
    #             domains.append(
    #                 expression.OR([
    #                     [('name', 'ilike', srch)],
    #                     [('default_code', 'ilike', srch)],
    #                     [('description', 'ilike', srch)],
    #                 ])
    #             )
    #
    #     if category:
    #         domains.append([('categ_id', 'child_of', int(category.id))])
    #
    #     if attrib_values:
    #         domains.extend(request.env['product.template']._get_attrib_values_domain(attrib_values))
    #
    #     return expression.AND(domains)
    #
    # @http.route([
    #     '/self-order/shop',
    #     '/self-order/shop/page/<int:page>',
    #     '/self-order/shop/category/<model("product.category"):category>',
    #     '/self-order/shop/category/<model("product.category"):category>/page/<int:page>'
    # ], type='json', auth="public")
    # def products(self, page=0, category=None, search='', ppg=20, **post):
    #     ProductTemplate = request.env['product.template']
    #
    #     # Attribute filtering
    #     attrib_list = request.httprequest.args.getlist('attribute_value')
    #     attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
    #
    #     # Search domain
    #     domain = self._get_search_domain(search, category, attrib_values)
    #
    #     # Pagination
    #     product_count = ProductTemplate.search_count(domain)
    #     ppg = int(ppg)
    #     offset = page * ppg
    #
    #     products = ProductTemplate.search(domain, limit=ppg, offset=offset, order='name, id')
    #
    #     products_data = []
    #     for product in products:
    #         products_data.append({
    #             'id': product.id,
    #             'name': product.name,
    #             'price': product.list_price,
    #             # You can add more fields here as needed
    #             'image_128': product.image_128,
    #         })
    #
    #     return {
    #         'products': products_data,
    #         'pager': {
    #             'page': page,
    #             'total': product_count,
    #             'step': ppg,
    #             'page_count': -(-product_count // ppg), # ceiling division
    #         },
    #     }