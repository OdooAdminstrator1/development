from odoo import api, fields, models, tools

class CrmLeadFile(models.Model):
    _name = 'crm.lead.stage.file'
    _description = 'Opportunity File'

    name = fields.Char(string="Filename")
    file = fields.Binary(string="File", required=True, attachment=True) 
    crm_lead_id = fields.Many2one('crm.lead', string="opportunity")
    file_download = fields.Binary(string="Download", related="file", readonly=True)
    opportunity_stage = fields.Char(
        string="Opportunity Stage",
        compute='_compute_opportunity_stage',
        store=True,
        readonly=True
    )

    @api.depends('crm_lead_id.stage_id')
    def _compute_opportunity_stage(self):
        """Automatically get the stage name from the linked opportunity"""
        for file_record in self:
            if file_record.crm_lead_id  and (not file_record.opportunity_stage):
                file_record.opportunity_stage = file_record.crm_lead_id.stage_id.name
            else:
                file_record.opportunity_stage = False

    @api.model
    def create(self, vals):
        """Override create to automatically set opportunity_stage when a new file is created"""
        record = super(CrmLeadFile, self).create(vals)
        # Force computation of opportunity_stage after creation
        if 'opportunity_stage' not in vals:
            record._compute_opportunity_stage()
        return record

class crmlead(models.Model):
    _inherit = 'crm.lead'
    file_ids = fields.One2many('crm.lead.stage.file', 'crm_lead_id', string="Files")