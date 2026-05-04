import re

with open('handlers.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove the 'Mas de 10 resultados' limits
code = re.sub(r'\s+if len\(disponibles\) > 10:.*?return VENTA_BUSCAR\n', '\n', code, flags=re.DOTALL)
code = re.sub(r'\s+if len\(prendas\) > 10:.*?return ADJFOTO_BUSCAR\n', '\n', code, flags=re.DOTALL)

# 2. Add pagination catch to all handlers
handlers = {
    'stock_confirmar_prenda': ('sel_stock', 'STOCK_CONFIRMAR', True),
    'venta_confirmar_prenda': ('sel_venta', 'VENTA_CONFIRMAR', False),
    'editar_confirmar': ('sel_editar', 'EDITAR_CONFIRMAR', False),
    'eliminar_confirmar': ('sel_eliminar', 'ELIMINAR_CONFIRMAR', False),
    'verfoto_confirmar': ('sel_foto', 'FOTO_CONFIRMAR', False),
    'adjfoto_confirmar_prenda': ('sel_adjfoto', 'ADJFOTO_CONFIRMAR', False)
}

for func_name, (accion, state, has_try) in handlers.items():
    if has_try:
        # stock_confirmar_prenda has try:
        pattern = rf'(async def {func_name}\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n\s+query = update\.callback_query\n\s+await query\.answer\(\)\n\s+try:\n)'
    else:
        pattern = rf'(async def {func_name}\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\n\s+query = update\.callback_query\n\s+await query\.answer\(\)\n)'
    
    indent = "        " if has_try else "    "
    injection = f'''{indent}if query.data.startswith("page_{accion}:"):
{indent}    pagina = int(query.data.split(":")[1])
{indent}    prendas_dict = context.user_data.get("prendas_encontradas", {{}})
{indent}    prendas_list = list(prendas_dict.values())
{indent}    await query.edit_message_reply_markup(
{indent}        reply_markup=teclado_lista_prendas(prendas_list, "{accion}", pagina)
{indent}    )
{indent}    return {state}\n'''
    
    code = re.sub(pattern, lambda m: m.group(1) + injection, code)

with open('handlers.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
