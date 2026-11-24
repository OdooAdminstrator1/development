import base64

from odoo import fields, models
from odoo.tools import float_is_zero

try:
    from num2words import num2words
except ImportError:
    num2words = None

SALE_INVOICE_TEMPLATE = 'delivery_extension.report_invoice_document_sale'

# Partner field holding the commercial registration number (partner_commercial_registration).
PARTNER_CR_FIELDS = ('x_commercial_registration', 'x_commercial_registeration')

# Currency unit / sub-unit names used for the amount in words, per language.
CURRENCY_WORDS = {
    'SAR': {
        'ar': ('ريال سعودي', 'هللة'),
        'en': ('Saudi Riyals', 'Halalas'),
    },
}


def _join(values, separator=', '):
    """Join the distinct non-empty values, keeping their order."""
    return separator.join(dict.fromkeys(value for value in values if value))


def _display_digits(value, digits):
    """Decimals to print: none for whole numbers."""
    return 0 if float_is_zero(value - round(value), precision_digits=digits) else digits


def _number_to_words(number, lang):
    try:
        words = num2words(number, lang=lang)
    except NotImplementedError:
        words = num2words(number, lang='en')
    return words if lang == 'ar' else words.title()


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_name_invoice_report(self):
        # Customer invoices created from a sale order print with the AESCO tax invoice.
        self.ensure_one()
        if self.move_type == 'out_invoice' and self.invoice_line_ids.sudo().sale_line_ids:
            return SALE_INVOICE_TEMPLATE
        return super()._get_name_invoice_report()

    def _use_sale_invoice_layout(self):
        """True when every invoice of self prints with the sale invoice layout,
        so the report can apply that layout's page margins."""
        return bool(self) and all(
            move._get_name_invoice_report() == SALE_INVOICE_TEMPLATE for move in self)

    def _get_sale_invoice_report_values(self):
        self.ensure_one()
        # sudo: accounting users have no access to production orders and deliveries.
        sale_lines = self.invoice_line_ids.sudo().sale_line_ids
        orders = sale_lines.order_id
        production_orders = orders.production_order_id
        pickings = sale_lines.move_ids.picking_id.filtered(
            lambda p: p.state == 'done' and p.picking_type_code == 'outgoing')

        lines = []
        number = 0
        for line in self.invoice_line_ids.sorted(lambda l: (l.sequence, l.id)):
            if line.display_type == 'product':
                number += 1
                lines.append(self._get_sale_invoice_line_values(line, number))
            else:
                lines.append({'display_type': line.display_type, 'description': line.name})
        total_gross = sum(vals['gross'] for vals in lines if vals['display_type'] == 'product')

        partner = self.commercial_partner_id
        currency = self.currency_id
        currency_ar = CURRENCY_WORDS.get(currency.name, {}).get('ar')
        return {
            'supply_date': self._get_sale_invoice_supply_date(pickings),
            'dn_numbers': _join(pickings.sorted('date_done').mapped('name')),
            'po_ref': _join(production_orders.mapped('po_no')) or self.ref,
            'project_name': _join(production_orders.mapped('name')),
            'sale_orders': _join(orders.mapped('name')),
            'customer_cr': next(
                (partner[fname] for fname in PARTNER_CR_FIELDS
                 if fname in partner._fields and partner[fname]), False),
            'qr_image': self._get_sale_invoice_qr_image(),
            'currency_label': '%s / %s' % (currency.name, currency_ar[0]) if currency_ar else currency.name,
            'lines': lines,
            'total_gross': total_gross,
            # Derived from the untaxed total so that the totals box always adds up.
            'total_discount': total_gross - self.amount_untaxed,
            'amount_words_ar': self._sale_invoice_amount_to_words(self.amount_total, 'ar'),
            'amount_words_en': self._sale_invoice_amount_to_words(self.amount_total, 'en'),
        }

    def _get_sale_invoice_line_values(self, line, number):
        product = line.product_id
        sale_lines = line.sudo().sale_line_ids
        materials =sale_lines.order_id.production_order_id.product_ids.filtered(
            lambda m: product and m.product_id == product)
        if len(materials) > 1:
            # Same product under several customer codes: keep the codes of the
            # delivery moves of this line when they tell them apart.
            codes = {code.strip().lower() for code in sale_lines.move_ids.mapped('pre_sales_code') if code}
            materials = materials.filtered(lambda m: (m.name or '').strip().lower() in codes) or materials

        # Untaxed amount before discount (also right when prices include taxes).
        gross = line.currency_id.round(line.tax_ids.compute_all(
            line.price_unit, currency=line.currency_id, quantity=line.quantity,
            product=product, partner=line.partner_id)['total_excluded'])
        precision = self.env['decimal.precision']
        return {
            'display_type': 'product',
            'number': number,
            'customer_code': _join(materials.mapped('name')),
            'aesco_code': product.estimation_code or '',
            'description': _join(materials.mapped('description'), '\n') or product.name or line.name,
            'quantity': line.quantity,
            'quantity_digits': _display_digits(line.quantity, precision.precision_get('Product Unit of Measure')),
            'uom': line.product_uom_id.name or '',
            'price_unit': line.price_unit,
            'discount': line.discount,
            'discount_digits': _display_digits(line.discount, precision.precision_get('Discount')),
            'gross': gross,
            'discount_amount': gross - line.price_subtotal,
            'subtotal': line.price_subtotal,
            'tax': line.price_total - line.price_subtotal,
            'total': line.price_total,
        }

    def _get_sale_invoice_supply_date(self, pickings):
        # 'Delivery Date' of the invoice (Odoo 17, editable for Saudi companies),
        # otherwise the date of the last delivery.
        if 'delivery_date' in self._fields and self.delivery_date:
            return self.delivery_date
        done_dates = [date for date in pickings.mapped('date_done') if date]
        if done_dates:
            return fields.Datetime.context_timestamp(self, max(done_dates)).date()
        return False

    def _get_sale_invoice_qr_image(self):
        """ZATCA QR code of the Saudi localization (l10n_sa) as a data URI."""
        qr_code = 'l10n_sa_qr_code_str' in self._fields and self.l10n_sa_qr_code_str
        if not qr_code:
            return False
        try:
            barcode = self.env['ir.actions.report'].barcode('QR', qr_code, width=150, height=150)
        except ValueError:
            return False
        return 'data:image/png;base64,%s' % base64.b64encode(barcode).decode()

    def _sale_invoice_amount_to_words(self, amount, lang):
        if num2words is None:
            return ''
        currency = self.currency_id
        unit, subunit = CURRENCY_WORDS.get(currency.name, {}).get(lang) or (
            currency.currency_unit_label or currency.name, currency.currency_subunit_label or '')
        integer, __, fraction = ('%.*f' % (currency.decimal_places, abs(amount))).partition('.')
        words = '%s %s' % (_number_to_words(int(integer), lang), unit)
        if int(fraction or 0):
            words += '%s%s %s' % (' و ' if lang == 'ar' else ' and ',
                                  _number_to_words(int(fraction), lang), subunit)
        return words
