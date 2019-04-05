# -*- coding = utf-8 -*-
import logging
import json
import ast


from odoo.osv import osv
from odoo import fields, exceptions


class account_move_line(osv.osv):
    _inherit = "account.move.line"

    vat = fields.Boolean(string="VAT Posted", default=False, readonly=True),
    vat_submission_id = fields.Many2one('mtd_vat.vat_submission_logs', string='VAT Submission Period')
    unique_number = fields.Many2one(
        related='vat_submission_id.unique_number',
        type='char',
        string="HMRC Unique Number",
        store=True,
        readonly=True
    )

class account_tax_chart(osv.osv_memory):
    _inherit = "account.tax.chart"

    vat_posted = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
        ('all', 'All')],
        'VAT Posted',
        required=True,
        default='no')

    previous_period = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')],
        'Include Transaction of Previous period',
        required=True,
        default='yes')

    def account_tax_chart_open_window(self, cr, uid, ids, context=None):
        result = super(account_tax_chart, self).account_tax_chart_open_window(cr, uid, ids, context=context)
        # Get the record to access the information provided by the user
        data = self.browse(cr, uid, ids, context=context)[0]
        period_ids = [data.period_id.id]
        fiscalyear_ids = [data.period_id.fiscalyear_id.id]

        if data.previous_period == 'yes':
            cutoff_date_rec = self.pool.get('mtd_vat.hmrc_posting_configuration').search(cr, uid, [
                ('name', '=', data.period_id.company_id.id)])
            if cutoff_date_rec:
                cutoff_date = self.pool.get('mtd_vat.hmrc_posting_configuration').browse(cr, uid, cutoff_date_rec,
                    context=context).cutoff_date
                all_periods_before_cutoff = self.pool.get('account.period').search(cr, uid,
                    [('date_start', '>=', cutoff_date.date_start),
                    ('state', '=', 'draft'),
                    ('company_id', '=', data.period_id.company_id.id)], context=context)
            else:
                raise exceptions.Warning(
                    "Chart of Taxes can not be generated!\nPlease create HMRC Posting Templae record first \n" +
                    "HMRC Posting Tempale can be generated from 'Accounting/Configuration/Miscellaneous/HMRC Posting Template' "
                )
            # return list of periods
            period_ids = self.pool.get('account.period').search(cr, uid,
                [('id', 'in', tuple(all_periods_before_cutoff)),
                 ('date_start', '<=', data.period_id.date_start)], context=context)
            fiscalyear_ids = []
            for period in period_ids:
                fiscalyear_id = self.pool.get('account.period').browse(cr, uid, period).fiscalyear_id.id
                if fiscalyear_id not in fiscalyear_ids:
                    fiscalyear_ids.append(fiscalyear_id)

        vat = ''
        if data.vat_posted == 'yes':
            vat = 'True'
        elif data.vat_posted == 'no':
            vat = 'False'

        context = result['context']
        new = ast.literal_eval(context)
        new['period_id'] = period_ids
        new['vat'] = vat
        new['fiscalyear_id'] = fiscalyear_ids
        result['context'] = new

        return result


class account_move(osv.osv):
    _inherit = "account.move"

    def button_cancel(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context):
            for item in line.line_id:
                if item.vat:
                    raise exceptions.Warning('You cannot modify a vat posted entry of this journal.')

        result = super(account_move, self).button_cancel(cr, uid, ids, context=context)
        return result
