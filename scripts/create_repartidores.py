group = env.ref("restaurant_casa_vieja_base.group_restaurant_repartidor")
users_data = [
    ("repartidor1@casavieja.test", "Repartidor Uno"),
    ("repartidor2@casavieja.test", "Repartidor Dos"),
    ("repartidor3@casavieja.test", "Repartidor Tres"),
]
created = []
for login, name in users_data:
    if env["res.users"].search([("login", "=", login)]):
        created.append(("EXISTS", login))
        continue
    u = env["res.users"].create({
        "login": login,
        "name": name,
        "password": "1234",
        "groups_id": [(6, 0, [group.id])],
    })
    created.append((u.id, login))
env.cr.commit()
print("CREATED:", created)
