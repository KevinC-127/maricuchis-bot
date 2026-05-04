
async def cmd_top_clientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    msg = update.message or query.message
    await msg.reply_text("Analizando historial de clientes... ⏳")
    
    if not NOTION_VENTAS_ID:
        await msg.reply_text("No hay BD de ventas configurada.")
        return

    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {"page_size": 100}
    
    # Paginar para obtener todos (opcional, pero 100 es bueno para empezar)
    r = requests.post(url, headers=NOTION_HEADERS, json=payload)
    if r.status_code != 200:
        await msg.reply_text("Error al consultar Notion. Intenta de nuevo.")
        return
    
    ventas = r.json().get("results", [])
    clientes = {}
    
    for page in ventas:
        props = page.get("properties", {})
        try:
            cliente_r = props.get("Cliente", {}).get("rich_text", [])
            cliente = cliente_r[0]["text"]["content"].strip() if cliente_r else ""
            if not cliente or cliente.lower() == "anonimo": continue
            
            ganancia = props.get("Ganancia", {}).get("number") or 0
            cantidad = props.get("Cantidad", {}).get("number") or 0
            
            if cliente not in clientes:
                clientes[cliente] = {"cantidad": 0, "ganancia": 0, "compras": 0}
            
            clientes[cliente]["cantidad"] += cantidad
            clientes[cliente]["ganancia"] += ganancia
            clientes[cliente]["compras"] += 1
        except Exception:
            continue
            
    if not clientes:
        await msg.reply_text("No se encontraron clientes registrados con nombre en las ventas.")
        return
        
    top = sorted(clientes.items(), key=lambda x: x[1]["ganancia"], reverse=True)[:10]
    
    lineas = ["👥 *Top 10 Clientes*"]
    lineas.append("Basado en las ganancias totales generadas:\n")
    
    for i, (cli, datos) in enumerate(top, 1):
        lineas.append(f"{i}. *{cli}*")
        lineas.append(f"   Ganancia: S/{datos['ganancia']:.0f} | Uds: {datos['cantidad']} | Compras: {datos['compras']}")
        
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver", callback_data="menu_ganancias")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await msg.reply_text("\n".join(lineas), reply_markup=teclado, parse_mode="Markdown")

async def cmd_ver_foto_directo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page_id = query.data.replace("vf_dir:", "")
    foto_url = await obtener_foto_url(page_id)
    if foto_url:
        await query.message.reply_photo(photo=foto_url)
    else:
        await query.message.reply_text("Esta prenda no tiene foto registrada.")

async def cmd_nueva_prenda_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = teclado_menu_nueva_prenda()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📸 *Nueva prenda — ¿Qué deseas hacer?*", reply_markup=teclado, parse_mode="Markdown")
    else:
        await update.message.reply_text("📸 *Nueva prenda — ¿Qué deseas hacer?*", reply_markup=teclado, parse_mode="Markdown")
