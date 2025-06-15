from odoo import _, fields, models
import midtransclient
from odoo.addons.pallas_midtransclient import const
from odoo.exceptions import ValidationError


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('midtrans', "Midtrans")], ondelete={'midtrans': 'set default'}
    )
    midtrans_email_account = fields.Char(
        string="Email",
        help="The public business email solely used to identify the account with Midtrans",
        default=lambda self: self.env.company.email,
    )
    midtrans_merchant_id = fields.Char(string="Midtrans Merchant ID")
    midtrans_client_key = fields.Char(string="Midtrans Client Key", groups='base.group_system')
    midtrans_server_key = fields.Char(string="Midtrans Server Key", groups='base.group_system')
    midtrans_access_token = fields.Char(
        string="Midtrans Access Token",
        help="The short-lived token used to access Paypal APIs",
        groups='base.group_system',
    )
    midtrans_access_token_expiry = fields.Datetime(
        string="Midtrans Access Token Expiry",
        help="The moment at which the access token becomes invalid.",
        default='1970-01-01',
        groups='base.group_system',
    )
    midtrans_webhook_id = fields.Char(string="Midtrans Webhook ID")

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'midtrans':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _midtrans_make_request(self,payload):
        print('payload', payload)
        snap = midtransclient.Snap(
            is_production=False,
            server_key=self.midtrans_server_key,
        )

        print(payload)
        try:
            snap_response = snap.create_transaction(payload)
            print(snap_response)
            return snap_response
        except Exception as e:
            print(e)
            raise ValidationError(e)
            # return False
