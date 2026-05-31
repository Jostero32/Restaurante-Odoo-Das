import odoo
from odoo import SUPERUSER_ID, api
from odoo.tools import config


def main():
    config.parse_config(["-c", "/etc/odoo/odoo.conf", "-d", "odoo"])
    registry = odoo.registry("odoo")

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        view = env["ir.ui.view"].browse(2886)

        content = view.arch_base
        content = content.replace(
            "Elige si prefieres salón principal, terraza o zona privada.",
            "Elige si prefieres salón principal, patio o zona privada.",
        )
        content = content.replace('value="terrace"', 'value="patio"')
        content = content.replace(
            "<t t-foreach=\"zone_options\" t-as=\"option\">\n                                                <option t-att-value=\"option[0]\" t-att-selected=\"option[0] == selected_zone and 'selected' or None\">\n                                                    <t t-esc=\"option[1]\"/>\n                                                </option>\n                                            </t>",
            "<option value=\"main\" t-att-selected=\"selected_zone == 'main' and 'selected' or None\">Interior</option>\n                                            <option value=\"patio\" t-att-selected=\"selected_zone == 'patio' and 'selected' or None\">Patio</option>\n                                            <option value=\"private\" t-att-selected=\"selected_zone == 'private' and 'selected' or None\">Privado</option>",
        )
        view.write({"arch_base": content})
        cr.commit()

    print("Updated view 2886")


if __name__ == "__main__":
    main()