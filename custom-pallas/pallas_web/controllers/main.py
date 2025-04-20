from odoo import http
from odoo.http import request, Response, content_disposition
import json
import base64


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
    def _get_base_url(self):
        """Helper method to get the base URL."""
        return request.httprequest.host_url.rstrip('/')

    def _get_record_or_error(self, model_name, error_message, limit=1, id=None):
        """Helper method to fetch a record or return an error response."""
        if not id:
            record = request.env[model_name].sudo().search([], limit= limit)
        else:
            record = request.env[model_name].sudo().browse(id)
        if not record:
            return None, self._make_json_response({'error': error_message}, status=404)
        return record, None
    @http.route('/api/product/category', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_category(self, **kwargs):
        categories, error_response = self._get_record_or_error('product.public.category', 'No information found.', limit=0)
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
        products = request.env['product.template'].sudo().search([('public_categ_ids','=',category_id)])
        if not category:
            return self._make_json_response({'error': 'No information found.'}, status=404)

        data = {
            "category": category.name,
            "products": [],
        }
        base_url = self._get_base_url()
        for product in products:
            data['products'].append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.list_price,
                "images": product.product_template_image_ids.mapped(lambda r: { "id": r.id, "image_url": f"{base_url}/web/image/{r._name}/{r.id}/image_1920" if r.image_1920 else None, }),
            })
        return self._make_json_response(data)

    @http.route('/api/product/<int:product_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_details(self, product_id, **kwargs):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product:
            return self._make_json_response({'error': 'No information found.'}, status=404)

        base_url = self._get_base_url()
        data = {
            "id": product.id,
            "name": product.name,
            "description": product.description_ecommerce,
            "price": product.list_price,
            "images": product.product_template_image_ids.mapped(lambda r: {"id": r.id,"image_url": f"{base_url}/web/image/{r._name}/{r.id}/image_1920" if r.image_1920 else None, }),
            "related_products": product.alternative_product_ids.mapped(lambda r: {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "price": r.list_price,
                "images": r.product_template_image_ids.mapped(lambda i: {"id": i.id, "image_url": f"{base_url}/web/image/{i._name}/{i.id}/image_1920" if i.image_1920 else None})
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
            "attributes": product.attribute_line_ids.mapped(lambda l: {"id": l.attribute_id.id,"name": l.attribute_id.name, "values": l.value_ids.mapped(lambda v: {"id": v.id, "name": v.name}),
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
        return request.httprequest.host_url.rstrip('/')

    def _get_record_or_error(self, model_name, error_message):
        """Helper method to fetch a record or return an error response."""
        record = request.env[model_name].sudo().search([], limit=1)
        if not record:
            return None, self._make_json_response({'error': error_message}, status=404)
        return record, None

    def _get_public_image_url(self, model, rec_id, field):
        """Generate URL for public image access"""
        return f"{self._get_base_url()}/api/public/image/{model}/{rec_id}/{field}"

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

        base_url = self._get_base_url()
        data = {
            'company_name': request.env.user.company_id.name,
            'title': about_us.title,
            'title_image_url': self._get_public_image_url('web.about.us', about_us.id, 'title_image') if about_us.title_image else None,            'tagline': about_us.tagline,
            'description': about_us.description,
            'event_images': [
                {'id': img.id, 'url': self._get_public_image_url(img._name, img.id, 'image')} for img in about_us.event_images
            ]
        }

        return self._make_json_response(data)

    @http.route('/api/home', type='http', auth='public', methods=['GET'], csrf=False)
    def get_home(self, **kwargs):
        home, error_response = self._get_record_or_error('web.home', 'No information found.')
        if error_response:
            return error_response

        base_url = self._get_base_url()
        data = {
            'tagline': home.tagline,
            'background_image': self._get_public_image_url('web.home', home.id, 'background_image') if home.background_image else None,
        }

        return self._make_json_response(data)

    @http.route('/api/location', type='http', auth='public', methods=['GET'], csrf=False)
    def get_location(self, **kwargs):
        location, error_response = self._get_record_or_error('web.location', 'No information found.')
        if error_response:
            return error_response

        base_url = self._get_base_url()
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

        base_url = self._get_base_url()
        data = {
            "name": promo.name,
            "banner_image": self._get_public_image_url('web.promo', promo.id, 'banner_image') if promo.banner_image else None,
            "promo_lines": [
                {"id": line.id, "name": line.name, "description": line.description, 
                "image_url":self._get_public_image_url(line._name, line.id, 'image') if line.image else None,
                # "image_url":f"{base_url}/web/image/{line._name}/{line.id}/image",
                }
                for line in promo.promo_ids
            ]
        }

        return self._make_json_response(data)


