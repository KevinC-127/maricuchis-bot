import re

with open('handlers.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove the 'Mas de 10 resultados' limits in venta_buscar_prenda, etc.
# Look for:
#    if len(disponibles) > 10:
#        await update.message.reply_text("Mas de 10 resultados. Se más específica.")
#        return VENTA_BUSCAR
code = re.sub(r'(\s+)if len\(disponibles\) > 10:.*?return [A-Z_]+\s', r'\1', code, flags=re.DOTALL)
code = re.sub(r'(\s+)if len\(prendas\) > 15:.*?return [A-Z_]+\s', r'\1', code, flags=re.DOTALL)


# 2. Add pagination catch to all handlers
handlers = {
    'stock_confirmar_prenda': ('sel_stock', 'STOCK_CONFIRMAR'),
    'venta_confirmar_prenda': ('sel_venta', 'VENTA_CONFIRMAR'),
    'editar_confirmar': ('sel_editar', 'EDITAR_CONFIRMAR'),
    'eliminar_confirmar': ('sel_eliminar', 'ELIMINAR_CONFIRMAR'),
    'verfoto_confirmar': ('sel_foto', 'FOTO_CONFIRMAR'),
    'adjfoto_confirmar_prenda': ('sel_adjfoto', 'ADJFOTO_CONFIRMAR')
}

for func_name, (accion, state) in handlers.items():
    # Find the start of the function, which might or might not have 'try:' right after query.answer()
    pattern = rf'(async def {func_name}\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):\s+query = update\.callback_query\s+await query\.answer\(\)\s+(?:try:\s+)?)'
    
    # We will inject the pagination check right after await query.answer() or try:
    injection = f'''
        if query.data.startswith("page_{accion}:"):
            pagina = int(query.data.split(":")[1])
            prendas_dict = context.user_data.get("prendas_encontradas", {{}})
            prendas_list = list(prendas_dict.values())
            await query.edit_message_reply_markup(
                reply_markup=teclado_lista_prendas(prendas_list, "{accion}", pagina)
            )
            return {state}
'''
    
    code = re.sub(pattern, lambda m: m.group(1) + injection, code)

with open('handlers.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
