import json
import logging
from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MidtransController(http.Controller):
    _return_url = '/payment/midtrans/return'
    _webhook_url = '/payment/midtrans/webhook'

    @http.route(_return_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def midtrans_return_from_checkout(self, **data):
        """ Process the notification data sent by Midtrans after redirection.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed.

        :param dict data: The notification data.
        """

        # Check the integrity of the notification.
        data = json.loads(request.httprequest.data)
        print(request.env['payment.transaction'])
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'midtrans', data
        )

        # self._verify_notification_signature(data, tx_sudo)

        # Handle the notification data.
        tx_sudo._handle_notification_data('midtrans', data)
        return request.redirect('/payment/status')


    @http.route('/payment/midtrans/verify', type='json', auth='public')
    def midtrans_verify_payment(self, **post):
        """ Verify payment status from frontend """
        try:
            if not all(post.get(k) for k in ['reference', 'transaction_id', 'status']):
                return {'error': 'Missing parameters'}

            tx = request.env['payment.transaction'].sudo().search([
                ('reference', '=', post['reference'])
            ], limit=1)

            if not tx:
                return {'error': 'Transaction not found'}

            tx.midtrans_transaction_id = post['transaction_id']

            if post['status'] == 'success':
                tx._set_done()
                tx._post_process_after_done()
            elif post['status'] == 'pending':
                tx._set_pending()
            else:
                tx._set_canceled()

            return {'success': True}
        except Exception as e:
            _logger.error("Midtrans verification failed: %s", str(e))
            return {'error': str(e)}

    @http.route('/payment/midtrans/notification', type='json', auth='public', csrf=False)
    def midtrans_notification(self, **post):
        """ Handle server-to-server notification """
        _logger.info("Midtrans notification received: %s", post)

        try:
            if not post.get('order_id'):
                return {'status': 'error', 'message': 'Missing order_id'}

            tx = request.env['payment.transaction'].sudo().search([
                ('reference', '=', post['order_id'])
            ], limit=1)

            if not tx:
                return {'status': 'error', 'message': 'Transaction not found'}

            # Verify with Midtrans API
            verification = self._verify_with_midtrans(tx.provider_id, post['transaction_id'])
            if not verification:
                return {'status': 'error', 'message': 'Verification failed'}

            # Process status
            transaction_status = post.get('transaction_status')
            fraud_status = post.get('fraud_status', '')

            if transaction_status == 'capture':
                if fraud_status == 'accept':
                    tx._set_done()
                else:
                    tx._set_canceled()
            elif transaction_status == 'settlement':
                tx._set_done()
            elif transaction_status in ['cancel', 'deny', 'expire']:
                tx._set_canceled()
            elif transaction_status == 'pending':
                tx._set_pending()
            else:
                _logger.warning("Unknown Midtrans status: %s", transaction_status)

            tx._post_process_after_done()
            return {'status': 'ok'}
        except Exception as e:
            _logger.error("Notification processing failed: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    def _verify_with_midtrans(self, provider, transaction_id):
        """ Verify transaction with Midtrans API """
        try:
            url = f"{provider._midtrans_get_api_url()}/{transaction_id}/status"
            response = requests.get(
                url,
                auth=(provider.midtrans_server_key, ''),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error("Midtrans verification failed: %s", str(e))
            return False
