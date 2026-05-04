import re

# Append teclado_lista_clientes to ia_gemini.py
with open('ia_gemini.py', 'a', encoding='utf-8') as f:
    f.write('''
def teclado_lista_clientes(clientes: list, pagina: int = 0, por_pagina: int = 30) -> InlineKeyboardMarkup:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    botones = []
    inicio = pagina * por_pagina
    fin = inicio + por_pagina
    pagina_clientes = clientes[inicio:fin]
    
    for i in range(0, len(pagina_clientes), 2):
        cb_data1 = f"cliente_prev_{pagina_clientes[i]}"[:64]
        fila = [InlineKeyboardButton(pagina_clientes[i], callback_data=cb_data1)]
        if i + 1 < len(pagina_clientes):
            cb_data2 = f"cliente_prev_{pagina_clientes[i+1]}"[:64]
            fila.append(InlineKeyboardButton(pagina_clientes[i+1], callback_data=cb_data2))
        botones.append(fila)
        
    nav_botones = []
    if pagina > 0:
        nav_botones.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"page_cliente:{pagina-1}"))
    if fin < len(clientes):
        nav_botones.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"page_cliente:{pagina+1}"))
        
    if nav_botones:
        botones.append(nav_botones)
        
    botones.append([InlineKeyboardButton("✏️ Nueva clienta", callback_data="cliente_nueva")])
    botones.append([InlineKeyboardButton("Sin nombre", callback_data="cliente_sin_nombre")])
    botones.append([InlineKeyboardButton("⬅️ Volver", callback_data="volver_fecha")])
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")])
    return InlineKeyboardMarkup(botones)
''')

# Modify handlers.py for venta_pedir_cliente
with open('handlers.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_pedir_cliente = '''async def venta_pedir_cliente(msg_obj, context, pagina=0):
    clientes_prev = context.user_data.get("clientes_previos")
    if not clientes_prev:
        clientes_prev = await obtener_clientes_previos()
        context.user_data["clientes_previos"] = clientes_prev
        
    teclado = teclado_lista_clientes(clientes_prev, pagina)
    texto = "👤 *¿A quién le vendiste?*"
    if clientes_prev:
        texto += f"\\n_{len(clientes_prev)} clientas registradas. Elige o agrega una nueva:_"
    
    if hasattr(msg_obj, "edit_text"):
        try:
            await msg_obj.edit_text(texto, reply_markup=teclado, parse_mode="Markdown")
        except Exception:
            await msg_obj.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
    else:
        await msg_obj.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
'''

code = re.sub(
    r'async def venta_pedir_cliente\(msg_obj, context\):.*?await msg_obj\.reply_text\(texto, reply_markup=teclado, parse_mode="Markdown"\)\n',
    new_pedir_cliente,
    code,
    flags=re.DOTALL
)

injection = '''        if data.startswith("page_cliente:"):
            pagina = int(data.split(":")[1])
            await venta_pedir_cliente(query.message, context, pagina=pagina)
            return VENTA_CLIENTE
'''

code = re.sub(
    r'(async def venta_recibir_cliente\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n\s+query = update\.callback_query\n\s+if query:\n\s+await query\.answer\(\)\n\s+data = query\.data\n)',
    lambda m: m.group(1) + injection,
    code
)

with open('handlers.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
