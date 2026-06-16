from collections import defaultdict

from odoo import models


class PartnerLedgerInitialBalance(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _build_partner_lines(self, report, options, level_shift=0):

        lines = []

        totals_by_column_group = {
            column_group_key: {
                total: 0.0
                for total in [
                    'initial_balance',
                    'debit',
                    'credit',
                    'balance',
                ]
            }
            for column_group_key in options['column_groups']
        }

        partners_results = self._query_partners(options)

        partner_ids = [
            partner.id
            for partner, dummy in partners_results
            if partner
        ]

        initial_balances = self._get_initial_balance_values(
            partner_ids,
            options,
        )

        for partner, results in partners_results:

            partner_values = defaultdict(dict)

            partner_id = partner.id if partner else None

            for column_group_key in options['column_groups']:

                sums = results.get(column_group_key, {})

                partner_values[column_group_key]['debit'] = sums.get(
                    'debit',
                    0.0,
                )

                partner_values[column_group_key]['credit'] = sums.get(
                    'credit',
                    0.0,
                )

                partner_values[column_group_key]['balance'] = sums.get(
                    'balance',
                    0.0,
                )

                partner_values[column_group_key]['initial_balance'] = (
                    initial_balances.get(partner_id, {})
                    .get(column_group_key, {})
                    .get('balance', 0.0)
                )

                totals_by_column_group[column_group_key][
                    'initial_balance'
                ] += partner_values[column_group_key][
                    'initial_balance'
                ]

                totals_by_column_group[column_group_key][
                    'debit'
                ] += partner_values[column_group_key][
                    'debit'
                ]

                totals_by_column_group[column_group_key][
                    'credit'
                ] += partner_values[column_group_key][
                    'credit'
                ]

                totals_by_column_group[column_group_key][
                    'balance'
                ] += partner_values[column_group_key][
                    'balance'
                ]

            lines.append(
                self._get_report_line_partners(
                    options,
                    partner,
                    partner_values,
                    level_shift=level_shift,
                )
            )

        return lines, totals_by_column_group
        
    def _get_report_line_partners(self,options,partner,partner_values,level_shift=0,):

        company_currency = self.env.company.currency_id
        report = self.env['account.report'].browse(
            options['report_id']
        )

        unfoldable = False
        column_values = []

        for column in options['columns']:

            label = column['expression_label']

            value = partner_values[
                column['column_group_key']
            ].get(label)

            unfoldable = (
                unfoldable
                or (
                    label in ('debit', 'credit')
                    and not company_currency.is_zero(value)
                )
            )

            column_values.append(
                report._build_column_dict(
                    value,
                    column,
                    options=options,
                )
            )

        line_id = (
            report._get_generic_line_id(
                'res.partner',
                partner.id,
            )
            if partner
            else report._get_generic_line_id(
                'res.partner',
                None,
                markup='no_partner',
            )
        )

        return {
            'id': line_id,
            'name': partner.name if partner else 'Unknown Partner',
            'columns': column_values,
            'level': 1 + level_shift,
            'unfoldable': unfoldable,
            'unfolded': (
                line_id in options['unfolded_lines']
                or options['unfold_all']
            ),
            'expand_function':
                '_report_expand_unfoldable_line_partner_ledger',
        }



    def _get_report_line_move_line(
        self,
        options,
        aml_query_result,
        partner_line_id,
        init_bal_by_col_group,
        level_shift=0,
    ):
        aml_query_result = dict(aml_query_result)

        aml_query_result.setdefault('initial_balance', None)

        return super()._get_report_line_move_line(
            options,
            aml_query_result,
            partner_line_id,
            init_bal_by_col_group,
            level_shift,
        )

