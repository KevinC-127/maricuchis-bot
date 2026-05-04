import re

# Append teclado_lista_ventas to ia_gemini.py
with open('ia_gemini.py', 'a', encoding='utf-8') as f:
    f.write('''
def teclado_lista_ventas(ventas: list, accion: str, pagina: int = 0, por_pagina: int = 10) -> InlineKeyboardMarkup:
    botones = []
    inicio = pagina * por_pagina
    fin = inicio + por_pagina
    pagina_ventas = ventas[inicio:fin]
    
    for v in pagina_ventas:
        botones.append([InlineKeyboardButton(v['label'], callback_data=f"{accion}:{v['id']}")])
        
    nav_botones = []
    if pagina > 0:
        nav_botones.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"page_{accion}:{pagina-1}"))
    if fin < len(ventas):
        nav_botones.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"page_{accion}:{pagina+1}"))
        
    if nav_botones:
        botones.append(nav_botones)
        
    botones.append([InlineKeyboardButton("Cancelar", callback_data="cancelar")])
    return InlineKeyboardMarkup(botones)
''')

# Modify handlers.py for eliminar_venta
with open('handlers.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(
    r'    botones = \[\]\n    for v in ventas\[:10\]:\n        botones\.append\(\[InlineKeyboardButton\(v\["label"\], callback_data=f"sel_elimventa:\{v\[\'id\'\]\}"\)\]\)\n    botones\.append\(\[InlineKeyboardButton\("Cancelar", callback_data="cancelar"\)\]\)\n    await update\.message\.reply_text\(\n        f"Encontré \{len\(ventas\[:10\]\)\} ventas\. ¿Cuál quieres eliminar\?",\n        reply_markup=InlineKeyboardMarkup\(botones\)\n    \)',
    '    await update.message.reply_text(\n        f"Encontré {len(ventas)} ventas. ¿Cuál quieres eliminar?",\n        reply_markup=teclado_lista_ventas(ventas, "sel_elimventa")\n    )',
    code
)

injection = '''    if query.data.startswith("page_sel_elimventa:"):
        pagina = int(query.data.split(":")[1])
        ventas_dict = context.user_data.get("ventas_encontradas", {})
        ventas_list = list(ventas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_ventas(ventas_list, "sel_elimventa", pagina)
        )
        return ELIMINAR_VENTA_CONFIRMAR\n'''

code = re.sub(
    r'(async def eliminar_venta_confirmar\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n\s+query = update\.callback_query\n\s+await query\.answer\(\)\n)',
    lambda m: m.group(1) + injection,
    code
)

with open('handlers.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
