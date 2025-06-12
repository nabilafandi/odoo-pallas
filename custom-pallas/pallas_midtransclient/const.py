# Part of Odoo. See LICENSE file for full copyright and licensing details.

# The codes of the payment methods to activate when Xendit is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    # Primary payment methods.
    'midtrans',
}

CURRENCY_DECIMALS = {
    'IDR': 0,
}
# Mapping of payment code to channel code according to Xendit API
PAYMENT_METHODS_MAPPING = {
    'midtrans': 'midtrans',
}

PAYMENT_STATUS_MAPPING = {
    'draft': (),
    'pending': ('pending'),
    'done': ('settlement', 'PAID', 'CAPTURED'),
    'cancel': ('cancel', 'expire'),
    'error': ('failure','deny')
}
