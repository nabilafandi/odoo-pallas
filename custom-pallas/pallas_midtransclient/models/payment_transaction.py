# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

import psycopg2
from werkzeug import urls

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from odoo.addons.payment import utils as payment_utils
from odoo.addons.pallas_midtransclient import const
import time

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # def _get_processing_values(self):
    #     processing_values = {
    #         'provider_id': self.provider_id.id,
    #         'provider_code': self.provider_code,
    #         'reference': self.reference,
    #         'amount': self.amount,
    #         'currency_id': self.currency_id.id,
    #         'partner_id': self.partner_id.id,
    #     }
    #     return processing_values

    def _get_specific_processing_values(self, processing_values):
        """ Override of payment to return Midtrans-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'midtrans':
            return res

        if self.currency_id.name in const.CURRENCY_DECIMALS:
            rounding = const.CURRENCY_DECIMALS.get(self.currency_id.name)
        else:
            rounding = self.currency_id.decimal_places
        rounded_amount = float_round(self.amount, rounding, rounding_method='DOWN')
        return {
            'rounded_amount': rounded_amount
        }

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to return Xendit-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'midtrans' or self.payment_method_code == 'card':
            return res

        # Initiate the payment and retrieve the invoice data.
        payload = self._midtrans_prepare_invoice_request_payload()
        _logger.info("Sending invoice request for link creation:\n%s", pprint.pformat(payload))
        # invoice_data = self.provider_id._xendit_make_request('v2/invoices', payload=payload)
        invoice_data = self.provider_id._midtrans_make_request(payload)
        _logger.info("Received invoice request response:\n%s", pprint.pformat(invoice_data))

        # Extract the payment link URL and embed it in the redirect form.
        rendering_values = {
            'api_url': invoice_data.get('invoice_url')
        }
        rendering_values = {
            'redirect_url': invoice_data.get('redirect_url'),
            'midtrans_token': invoice_data.get('token'),
            'client_key': self.provider_id.midtrans_client_key,
        }
        print(rendering_values)
        return rendering_values

    def _midtrans_prepare_invoice_request_payload(self):
        """ Create the payload for the invoice request based on the transaction values.

        :return: The request payload.
        :rtype: dict
        """
        base_url = self.provider_id.get_base_url()
        redirect_url = urls.url_join(base_url, '/payment/status')
        payload = {
            "transaction_details": {
                "order_id": f"{self.reference}-midtrans-{time.time()}",
                "gross_amount": int(self.amount),
            },
            "customer_details": {
                "first_name": self.partner_name,
                "email": self.partner_email,
            },
        }
        return payload

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        print('notification_data', notification_data)
        """ Override of `payment` to find the transaction based on the notification data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: payment.transaction
        :raise ValidationError: If inconsistent data were received.
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'midtrans' or len(tx) == 1:
            return tx

        reference = notification_data.get('order_id').split('-midtrans')[0]
        if not reference:
            raise ValidationError("Midtrans: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'midtrans')])
        if not tx:
            raise ValidationError(
                "Midtrans: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on Xendit data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data were received.
        """
        self.ensure_one()

        super()._process_notification_data(notification_data)
        if self.provider_code != 'midtrans':
            return

        # Update the provider reference.
        self.provider_reference = notification_data.get('id')

        # Update payment method.
        payment_method_code = notification_data.get('payment_method', '')
        payment_method = self.env['payment.method']._get_from_code(
            payment_method_code, mapping=const.PAYMENT_METHODS_MAPPING
        )
        self.payment_method_id = payment_method or self.payment_method_id

        # Update the payment state.
        payment_status = notification_data.get('transaction_status')
        if payment_status in const.PAYMENT_STATUS_MAPPING['pending']:
            self._set_pending()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['done']:
            self._set_done()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['cancel']:
            self._set_canceled()
        elif payment_status in const.PAYMENT_STATUS_MAPPING['error']:
            failure_reason = notification_data.get('failure_reason')
            self._set_error(_(
                "An error occurred during the processing of your payment (%s). Please try again.",
                failure_reason,
            ))

    def _process_payment(self):
        for tx in self:
            try:
                tx._post_process()
                self.env.cr.commit()
            except psycopg2.OperationalError:
                self.env.cr.rollback()  # Rollback and try later.
            except Exception as e:
                _logger.exception(
                    "encountered an error while post-processing transaction with reference %s:\n%s",
                    tx.reference, e
                )
                self.env.cr.rollback()
