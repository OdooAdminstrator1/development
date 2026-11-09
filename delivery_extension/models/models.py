from odoo import models, api, fields
class ProductionOrderMaterials(models.Model):
    _inherit = 'production.order.materials'
    description = fields.Char(
        string="Description", 
        help="Description based on client spec."
    )
    notes = fields.Char(
        string="Notes"
    )

class ProductionOrder(models.Model):
    _inherit = 'production.order'

    project_id = fields.Char(
        string="Project ID", 
        copy=False, 
        help="Unique project identifier, defaults to record ID if empty."
    )
    po_no = fields.Char(
        string="PO Number", 
        copy=False, 
        help="Unique production Order No."
    )

    _sql_constraints = [
        (
            'project_id_unique', 
            'unique(project_id)', 
            'The Project ID must be unique!'
        )
    ]

    delivery_count = fields.Integer(string='Deliveries Count', compute='_compute_delivery_count')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.project_id:
                record.project_id = str(record.id)
        return records

    @api.depends('opportunity_id')
    def _compute_delivery_count(self):
        for order in self:
            order.delivery_count = self.env['stock.picking'].search_count([('production_order_id', '=', order.id)])

    def action_view_deliveries(self):
        action = self.env.ref('stock.action_picking_tree_outgoing').read()[0]
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_location = fields.Char(string="Delivery Location")
    subject_of_delivery = fields.Char(string="Subject of Delivery")
    project_id = fields.Char(
            compute='_compute_ref_fields',
            string='Project ID',
            store=False,
        )
    project_name = fields.Char(
            compute='_compute_ref_fields',
            string='Project Name',
            store=False,
        )
    po_no = fields.Char(
            compute='_compute_ref_fields',
            string='PO Number',
            store=False
        )
    received_by = fields.Char(
            string='Received by',
        )
    
    
    title_name = fields.Char(
            string='Job name',
        )
    
    prepared_by = fields.Char(
            string='Prepared by',
        )

    checked_by = fields.Char(
            string='Checked_by',
        )
    delivered_by = fields.Char(
            string='Delivered by',
        )
    vehicle_no = fields.Char(
            string='Vehicle No.',
        )
    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order',
        domain="[('partner_id', '=', partner_id)]"
    )

    order_type = fields.Selection(
        [
            ('order', 'Order'),
            ('sample', 'Sample'),
        ],
        string='Delivery order type',
        default='order'
    )

    @api.onchange('production_order_id')
    def _onchange_production_order_id(self):
        if not self.production_order_id or self.picking_type_id.code != 'outgoing' :
            return
        
        pr_id = self.production_order_id


        # 2. Clear existing lines and populate from delivery stock moves
        lines = []
        for move in pr_id.product_ids:
            lines.append((0, 0, {
                'product_id': move.product_id.id,
                'product_uom_qty': move.qty,
                'name':move.product_id.name,
                'location_id': self.location_id,
                'location_dest_id': self.location_dest_id,
                'pre_sales_code' : move.name,
            }))
        
        self.move_ids_without_package = [(5, 0, 0)] + lines


    @api.depends('production_order_id', 'sale_id.production_order_id')
    def _compute_ref_fields(self):
        for rec in self:
            project_id=False
            project_name=False
            po_no=False

            if rec.sale_id and rec.sale_id.production_order_id:
                project_id=rec.sale_id.production_order_id.project_id
                project_name=rec.sale_id.production_order_id.name
                po_no=rec.sale_id.production_order_id.po_no  
            elif rec.production_order_id:
                project_id=rec.production_order_id.project_id
                project_name=rec.production_order_id.name
                po_no=rec.production_order_id.po_no
                
            rec.project_id=project_id
            rec.project_name=project_name
            rec.po_no=po_no


class StockMove(models.Model):
    _inherit = 'stock.move'

    pre_sales_code = fields.Char(
        string='Pre Sales Code',

    )

    serial_number = fields.Integer(
        string='No.',
        compute='_compute_serial_number',
        store=False
    )

    order_description = fields.Char(
        string='Spec.',
        compute='_compute_order_description',
        store=False
    )
    order_notes = fields.Char(
        string='Notes',
        compute='_compute_order_description',
        store=False
    )

    @api.depends('picking_id.move_ids_without_package', 'picking_id.move_ids_without_package.sequence')
    def _compute_serial_number(self):
        for move in self:
            if move.picking_id and move.picking_id.move_ids_without_package:
                # Sort moves by sequence or ID to maintain consistent numbering
               
                try:
                    
                  #  moves = move.picking_id.move_ids_without_package.sorted(lambda m: (m.sequence, m.id))
                    moves = move.picking_id.move_ids_without_package.sorted(lambda m: (m.sequence, m.id if isinstance(m.id, int) else 0))
                    move.serial_number = list(moves).index(move) + 1
                except (ValueError, TypeError):
                    move.serial_number = 1
            else:
                move.serial_number = 1


    # def _inverse_pre_sales_code(self):
    #     pass




    # @api.depends('picking_id.sale_id.production_order_id', 'product_id')
    # def _compute_pre_sales_code(self):

    #     for move in self:
    #         code=move.pre_sales_code
    #         production_order = move.picking_id.production_order_id
    #         if not production_order:
    #             production_order = move.picking_id.sale_id.production_order_id
    #         if production_order and move.product_id:
    #             material = self.env['production.order.materials'].search([
    #                 ('production_order_id', '=', production_order.id),
    #                 ('product_id', '=', move.product_id.id)
    #             ])
    #             if len(material)==1:
    #                 code = material.name
    #             elif len(material)>1 and move.product_id.name and move.pre_sales_code:
    #                 to_process = material.filtered( lambda m: m.product_id.name.lower().strip()==move.pre_sales_code.lower().strip() )
    #                 if len(to_process)>=1:
    #                     code=to_process[0].name
    #         move.pre_sales_code = code

    @api.depends('picking_id.sale_id.production_order_id', 'product_id')
    def _compute_order_description(self):
        for move in self:
            code = False
            notes = False
            p_order = move.picking_id.production_order_id
            if p_order and move.product_id and move.picking_id.production_order_id:
                material = self.env['production.order.materials'].search([
                    ('production_order_id', '=', p_order.id),
                    ('product_id', '=', move.product_id.id)
                ])
                if len(material)==1:
                    code = material.description
                    notes = material.notes
                elif len(material)>1 and move.product_id.name and move.pre_sales_code:
                    to_process = material.filtered( lambda m: m.product_id.name.lower().strip()==move.pre_sales_code.lower().strip() )
                    if len(to_process)>=1:
                        code = to_process[0].description
                        notes = to_process[0].notes
                     
            # elif move.product_id:
            #     code=move.description_picking
            move.order_description = code
            move.order_notes = notes

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _get_aggregated_product_quantities(self, **kwargs):
        aggregated_lines = super()._get_aggregated_product_quantities(
            **kwargs
        )

        seen_moves = {}

        for move_line in self:
            if (
                kwargs.get("except_package")
                and move_line.result_package_id
            ):
                continue

            properties = self._get_aggregated_properties(
                move_line=move_line
            )
            key = properties["line_key"]

            if key not in aggregated_lines:
                continue

            move = move_line.move_id
            if not move:
                continue

            seen = seen_moves.setdefault(key, set())

            # One entry per stock.move, even when it has multiple move lines.
            if move.id in seen:
                continue

            seen.add(move.id)


            aggregated_lines[key].setdefault(
                "custom_move_values", []
            ).append({
                "move": move,
                "pre_sales_code": move.pre_sales_code or "",
                "serial_number": (
                    str(move.serial_number)
                    if move.serial_number is not False
                    else ""
                ),
            })

        # Also handle aggregated rows that have no corresponding
        # move line in the current recordset.
        for line in aggregated_lines.values():
            if "custom_move_values" not in line:
                move = line.get("move")
        
                line["custom_move_values"] = (
                    [{
                        "move": move,
                        "pre_sales_code": move.pre_sales_code or "",
                        "serial_number": (
                            str(move.serial_number)
                            if move.serial_number is not False
                            else ""
                        ),
                    }]
                    if move
                    else []
                )

        return aggregated_lines

