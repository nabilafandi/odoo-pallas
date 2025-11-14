from odoo import http
import json
from odoo.addons.pos_self_order.controllers.self_entry import PosSelfKiosk
from odoo.exceptions import ValidationError
from odoo.http import request, Response, content_disposition
from datetime import date, datetime
from odoo.addons.website.controllers.main import QueryURL
from odoo.tools import clean_context, float_round, groupby, lazy, single_email_re, str2bool, SQL



from odoo.osv import expression

class TableCompute:

    def __init__(self):
        self.table = {}

    def _check_place(self, posx, posy, sizex, sizey, ppr):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= ppr:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(ppr):
                self.table[posy + y].setdefault(x, None)
        return res

    def process(self, products, ppg=20, ppr=4):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        x = 0
        for p in products:
            x = min(max(p.website_size_x, 1), ppr)
            y = min(max(p.website_size_y, 1), ppr)
            if index >= ppg:
                x = y = 1

            pos = minpos
            while not self._check_place(pos % ppr, pos // ppr, x, y, ppr):
                pos += 1
            # if 21st products (index 20) and the last line is full (ppr products in it), break
            # (pos + 1.0) / ppr is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= ppg and ((pos + 1.0) // ppr) > maxy:
                break

            if x == 1 and y == 1:   # simple heuristic for CPU optimization
                minpos = pos // ppr

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
            self.table[pos // ppr][pos % ppr] = {
                'product': p, 'x': x, 'y': y,
                'ribbon': p.sudo().website_ribbon_id,
            }
            if index <= ppg:
                maxy = max(maxy, y + (pos // ppr))
            index += 1

        # Format table according to HTML needs
        rows = sorted(self.table.items())
        rows = [r[1] for r in rows]
        for col in range(len(rows)):
            cols = sorted(rows[col].items())
            x += len(cols)
            rows[col] = [r[1] for r in cols if r[1]]

        return rows


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

def _get_search_domain(search, category, attrib_values):
    """Build a domain to search products.

    This method can be overridden to add new search criteria.
    """
    domains = [[]]  # Add your base domain here if needed, e.g., [('available_in_pos', '=', True)]
    if search:
        for srch in search.split(" "):
            domains.append(
                expression.OR([
                    [('name', 'ilike', srch)],
                    [('default_code', 'ilike', srch)],
                    [('description', 'ilike', srch)],
                ])
            )

    if category:
        domains.append([('categ_id', 'child_of', int(category.id))])

    if attrib_values:
        domains.extend(request.env['product.template']._get_attrib_values_domain(attrib_values))

    return expression.AND(domains)

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


    def _shop_get_query_url_kwargs(
        self, category, search, min_price, max_price, order=None, tags=None, attribute_value=None, **post
    ):
        return {
            'category': category,
            'search': search,
            'tags': tags,
            'min_price': min_price,
            'max_price': max_price,
            'order': order,
            'attribute_value': attribute_value,
        }
    def _get_search_options(
        self, category=None, attrib_values=None, tags=None, min_price=0.0, max_price=0.0,
        conversion_rate=1, **post
    ):
        return {
            'displayDescription': True,
            'displayDetail': True,
            'displayExtraDetail': True,
            'displayExtraLink': True,
            'displayImage': True,
            'allowFuzzy': not post.get('noFuzzy'),
            'category': str(category.id) if category else None,
            'tags': tags,
            'min_price': min_price / conversion_rate,
            'max_price': max_price / conversion_rate,
            'attrib_values': attrib_values,
            'display_currency': post.get('display_currency'),
        }

    def _shop_lookup_products(self, attrib_set, options, post, search, website):
        # No limit because attributes are obtained from complete product list
        product_count, details, fuzzy_search_term = website._search_with_fuzzy("products_only", search,
                                                                               limit=None,
                                                                               order=self._get_search_order(post),
                                                                               options=options)
        search_result = details[0].get('results', request.env['product.template']).with_context(bin_size=True)

        return fuzzy_search_term, product_count, search_result

    def _get_search_order(self, post):
        # OrderBy will be parsed in orm and so no direct sql injection
        # id is added to be sure that order is a unique sort key
        order = post.get('order') or "name asc"
        return 'is_published desc, %s, id desc' % order

    @http.route([
        '/pos-storefront',
        '/pos-storefront/page/<int:page>',
        '/pos-storefront/category/<model("pos.category"):category>',
        '/pos-storefront/category/<model("pos.category"):category>/page/<int:page>',
    ], type='http', auth="public")
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, ppg=False, config_id='1', access_token="",table_identifier="", **post):
        pos_config, _, _ = self._verify_entry_access(config_id, access_token, table_identifier)

        try:
            min_price = float(min_price)
        except ValueError:
            min_price = 0
        try:
            max_price = float(max_price)
        except ValueError:
            max_price = 0

        Category = request.env['pos.category']
        if category:
            category = Category.search([('id', '=', int(category))], limit=1)
            # if not category or not category.can_access_from_current_website():
            #     raise ValidationError('You are not allowed to access this product.')
            if not category:
                raise ValidationError('You are not allowed to access this product.')
        else:
            category = Category

        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = 20

        ppr = 4
        gap = "16px"

        request_args = request.httprequest.args
        attrib_list = request_args.getlist('attribute_value')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}
        if attrib_list:
            post['attribute_value'] = attrib_list

        # TODO make filter by tags functional
        filter_by_tags_enabled = False
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

        # now = datetime.timestamp(datetime.now())
        # pricelist = website.pricelist_id
        # if 'website_sale_pricelist_time' in request.session:
        #     # Check if we need to refresh the cached pricelist
        #     pricelist_save_time = request.session['website_sale_pricelist_time']
        #     if pricelist_save_time < now - 60 * 60:
        #         request.session.pop('website_sale_current_pl', None)
        #         website.invalidate_recordset(['pricelist_id'])
        #         pricelist = website.pricelist_id
        #         request.session['website_sale_pricelist_time'] = now
        #         request.session['website_sale_current_pl'] = pricelist.id
        # else:
        #     request.session['website_sale_pricelist_time'] = now
        #     request.session['website_sale_current_pl'] = pricelist.id
        #
        # TODO make filter by price functional
        filter_by_price_enabled = False
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
            conversion_rate=1,
            display_currency=pos_config.currency_id.id,
            **post
        )
        fuzzy_search_term, product_count, search_product = self._shop_lookup_products(attrib_set, options, post, search, pos_config)

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

        categs_domain = [('parent_id', '=', False)]
        if search:
            search_categories = Category.search(
                [('product_tmpl_ids', 'in', search_product.ids)]
            ).parents_and_self
            categs_domain.append(('id', 'in', search_categories.ids))
        else:
            search_categories = Category
        categs = lazy(lambda: Category.search(categs_domain))

        if category:
            url = "/shop/category/%s" % request.env['ir.http']._slug(category)

        pager = pos_config.pager(url=url, total=product_count, page=page, step=ppg, scope=5, url_args=post)
        offset = pager['offset']
        products = search_product[offset:offset + ppg]

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            attributes = lazy(lambda: ProductAttribute.search([
                ('product_tmpl_ids', 'in', search_product.ids),
                # ('visibility', '=', 'visible'),
            ]))
        else:
            attributes = lazy(lambda: ProductAttribute.browse(attributes_ids))

        # layout_mode = request.session.get('website_sale_shop_layout_mode')
        # if not layout_mode:
        #     if website.viewref('website_sale.products_list_view').active:
        #         layout_mode = 'list'
        #     else:
        #         layout_mode = 'grid'
        #     request.session['website_sale_shop_layout_mode'] = layout_mode

        # products_prices = lazy(lambda: products._get_sales_prices(website))
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
            # 'layout_mode': layout_mode,
            # 'products_prices': products_prices,
            # 'get_product_prices': lambda product: lazy(lambda: products_prices[product.id]),
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
        return request.render("website_sale.products", values)



    def get_list_product(self):
