/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useEffect } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useInputField } from "@web/views/fields/input_field_hook";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class FieldColorPicker extends Component {
    static template = "web_widget_colorpicker.FieldColorPicker";
    static props = {
        ...standardFieldProps,
    };

    elRef = useRef("el");
    inputRef = useRef("ColorChar");
    pickrRef = useRef("pickrContainer");

    setup() {
        this.pickrInstance = null;

        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "rgba(0, 0, 0, 1)",
            refName: "ColorChar",
            parse: (v) => this.parse(v),
        });

        onMounted(() => {
            if (this.props.readonly) return;

            const inputEl = this.inputRef.el;
            const pickrContainer = this.pickrRef.el;

            if (inputEl && pickrContainer && window.Pickr) {
                // Initialize Pickr
                this.pickrInstance = window.Pickr.create({
                    el: pickrContainer,
                    theme: 'classic', // or 'nano', 'monolith'
                    default: this.value || 'rgba(0, 0, 0, 1)',
                    components: {
                        // Main components
                        preview: true,
                        opacity: true,
                        hue: true,
                        // Additional components
                        interaction: {
                            hex: false,
                            rgba: true,
                            hsla: false,
                            hsva: false,
                            cmyk: false,
                            input: true,
                            clear: false,
                            save: true
                        }
                    }
                });

                // Event handlers
                this.pickrInstance.on('save', (color) => {
                    if (color) {
                        const rgbaColor = color.toRGBA().toString(0);
                        inputEl.value = rgbaColor;
                        this.props.record.update({ [this.props.name]: rgbaColor });
                    }
                    this.pickrInstance.hide();
                });

                this.pickrInstance.on('change', (color) => {
                    if (color) {
                        const rgbaColor = color.toRGBA().toString(0);
                        inputEl.value = rgbaColor;
                    }
                });

                // Set initial value
                if (this.value) {
                    this.pickrInstance.setColor(this.value);
                    inputEl.value = this.value;
                }
            }
        });

        // Watch for value changes when navigating between records
        useEffect(
            () => {
                if (this.pickrInstance && !this.props.readonly) {
                    const currentValue = this.value || 'rgba(0, 0, 0, 1)';
                    const inputEl = this.inputRef.el;

                    // Update Pickr color
                    this.pickrInstance.setColor(currentValue);

                    // Update input field value
                    if (inputEl) {
                        inputEl.value = currentValue;
                    }
                }
            },
            () => [this.value] // Dependencies: re-run when value changes
        );

        onWillUnmount(() => {
            // Cleanup when component is unmounted
            if (this.pickrInstance) {
                this.pickrInstance.destroyAndRemove();
                this.pickrInstance = null;
            }
        });

        super.setup();
    }

    get formattedValue() {
        return this.value || "rgba(0, 0, 0, 1)";
    }

    get value() {
        return this.props.record.data[this.props.name];
    }

    parse(value) {
        // Check for valid RGBA color
        const isValidRgba = /^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*(?:0|1|0?\.\d+))?\s*\)$/.test(value);
        return isValidRgba ? value : "rgba(0, 0, 0, 1)";
    }
}

export const fieldColorPicker = {
    component: FieldColorPicker,
    displayName: _t("Color Picker Field"),
    supportedTypes: ["char"]
};

// Add the field to the correct category
registry.category("fields").add("colorpicker", fieldColorPicker);
