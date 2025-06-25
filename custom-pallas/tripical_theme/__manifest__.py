{
    'name': 'Tripical Theme',
    'version': '1.0',
    'summary': 'Changes Odoo primary color to red',
    'description': 'Replaces all purple primary colors with red',
    'category': 'Theme/Backend',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'tripical_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_frontend': [
            'tripical_theme/static/src/scss/font.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
