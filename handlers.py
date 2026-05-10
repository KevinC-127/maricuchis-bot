from config import *
from notion_api import *
from notion_api import _formato_stock, _texto_agotados
from ui import *
from ui import _texto_ayuda
# ============================================================
# HANDLERS — COMANDOS GENERALES
# ============================================================
async def _reply(update: Update, texto: str, **kwargs):
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except:
            pass
        await update.callback_query.message.reply_text(texto, **kwargs)
    elif update.message:
        await update.message.reply_text(texto, **kwargs)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Maricuchis Store - Bot v6.0\n\nHola Maritza! ¿Qué quieres hacer hoy?",
        reply_markup=teclado_menu_principal()
    )

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Menu principal:", reply_markup=teclado_menu_principal())

async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, _texto_ayuda())

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _reply(update, "Operacion cancelada.")
    await _mostrar_menu(update, context)
    return ConversationHandler.END

async def _mostrar_menu(update, context):
    """Muestra el menú principal desde cualquier contexto."""
    teclado = teclado_menu_principal()
    texto   = "Menú principal:"
    if update.callback_query:
        await update.callback_query.message.reply_text(texto, reply_markup=teclado)
    elif update.message:
        await update.message.reply_text(texto, reply_markup=teclado)

async def fallback_menu_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback para el botón Volver al menú dentro de cualquier ConversationHandler."""
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data.clear()
        await query.message.reply_text("Menú principal:", reply_markup=teclado_menu_principal())
    return ConversationHandler.END

async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Tu Chat ID es: {update.effective_chat.id}")

# ============================================================
# COMANDO /nueva
# ============================================================
async def cmd_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update,
        "Nueva prenda con foto\n\n"
        "Envía la foto con pie de foto así:\n"
        "  Nombre, costo, precio, stock\n\n"
        "Opcionales al final:\n"
        "  , tienda, DD/MM/YYYY\n\n"
        "Ejemplo:\n"
        "  Chompa azul, 96, 130, 12, Gamarra, 01/05/2026\n\n"
        "O usa /sinfoto si no tienes foto aún."
    )

# ============================================================
# COMANDO /limitadas
# ============================================================
async def cmd_limitadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Buscando prendas con stock limitado...")
    prendas = await fetch_inventario_completo()
    if prendas is None:
        await _reply(update, "Error al consultar Notion.")
        return
    limitadas = [p for p in prendas if 1 <= p["stock"] <= 3]
    if not limitadas:
        await _reply(update, "No hay prendas con stock limitado en este momento.")
        return
    limitadas.sort(key=lambda p: p["stock"])
    lineas = [f"Prendas con stock bajo ({len(limitadas)}):\n"]
    for p in limitadas:
        lineas.append(f"  {p['nombre']}\n  Stock: {p['stock']} uds | Precio: S/{p['precio']:.0f}")
    await _reply(update, "\n".join(lineas))

# ============================================================
# COMANDO /ganancia
# ============================================================
async def cmd_ganancia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Calculando ganancias...")
    prendas = await fetch_inventario_completo()
    if prendas is None:
        await _reply(update, "Error al consultar Notion.")
        return
    if not prendas:
        await _reply(update, "El inventario está vacío.")
        return
    total_vendidas  = sum(p["vendidas"] for p in prendas)
    ingreso_total   = sum(p["ingreso_real"] for p in prendas)
    ganancia_total  = sum(p["ganancia_real"] for p in prendas)
    ganancia_pot    = sum(p["stock"] * p["ganancia_u"] for p in prendas)
    total_invertido = sum(p["costo"] for p in prendas)
    roi = round(ganancia_total / total_invertido * 100, 1) if total_invertido > 0 else 0
    top3 = sorted(prendas, key=lambda p: p["ganancia_real"], reverse=True)[:3]
    lineas = [
        "Resumen de ganancias\n",
        f"Unidades vendidas:  {total_vendidas} uds",
        f"Ingresos totales:   S/{ingreso_total:.0f}",
        f"Ganancia realizada: S/{ganancia_total:.0f}  (ROI {roi}%)",
        f"Ganancia potencial: S/{ganancia_pot:.0f}  (stock restante)",
        "", "Top 3 más rentables:",
    ]
    for i, p in enumerate(top3, 1):
        lineas.append(f"  {i}. {p['nombre']} — S/{p['ganancia_real']:.0f}")
    await _reply(update, "\n".join(lineas))

async def cmd_agotados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buscando prendas agotadas...")
    await update.message.reply_text(await _texto_agotados())

# ============================================================
# HANDLER — MENU (botones)
# ============================================================
async def manejar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    accion = query.data
    await query.edit_message_reply_markup(reply_markup=None)
    if accion == "menu_nueva":
        await query.message.reply_text(
            "Nueva prenda con foto\n\nEnvia la foto con pie de foto asi:\n"
            "  Nombre, costo, precio, stock\n\nOpcionales al final:\n"
            "  , tienda, DD/MM/YYYY\n\nEjemplo:\n"
            "  Chompa azul, 96, 130, 12, Gamarra, 01/05/2026\n\n(Cancela con /cancelar)"
        )
    elif accion == "menu_sinfoto":
        await cmd_sin_foto(update, context)
    elif accion == "menu_adjfoto":
        await cmd_adj_foto(update, context)
    elif accion == "menu_venta":
        await cmd_vendi(update, context)
    elif accion == "menu_stock":
        await cmd_stock(update, context)
    elif accion == "menu_agotados":
        await query.message.reply_text("Buscando prendas agotadas...")
        await query.message.reply_text(await _texto_agotados())
    elif accion == "menu_verfoto":
        await cmd_ver_foto(update, context)
    elif accion == "menu_inventario":
        await cmd_inventario(update, context)
    elif accion == "menu_resumen":
        await cmd_resumen(update, context)
    elif accion == "menu_pormargen":
        await cmd_por_margen(update, context)
    elif accion == "menu_portienda":
        await cmd_por_tienda(update, context)
    elif accion == "menu_ganancias":
        await cmd_ganancias_menu(update, context)
    elif accion == "fin_resumen":
        await cmd_resumen(update, context)
    elif accion == "fin_pormargen":
        await cmd_por_margen(update, context)
    elif accion == "fin_portienda":
        await cmd_por_tienda(update, context)
    elif accion == "fin_porfecha":
        await cmd_ganancias_fecha_menu(update, context)
    elif accion in ("fin_fecha_hoy", "fin_fecha_ayer", "fin_fecha_semana", "fin_fecha_mes"):
        await cmd_ganancias_por_fecha(update, context)

    elif accion == "menu_comparar":
        await cmd_comparar(update, context)
    elif accion == "menu_inicio":
        await cmd_menu(update, context)
    elif accion == "menu_ventas_sub":
        await query.message.reply_text("💰 *Ventas — ¿Qué deseas hacer?*", reply_markup=teclado_submenu_ventas(), parse_mode="Markdown")
    elif accion == "menu_inventario_sub":
        await query.message.reply_text("📋 *Inventario — ¿Qué deseas ver?*", reply_markup=teclado_submenu_inventario(), parse_mode="Markdown")
    elif accion == "menu_nueva_menu":
        await cmd_nueva_prenda_menu(update, context)
    elif accion == "menu_nueva_guiado":
        await cmd_nueva_prenda(update, context)
    elif accion == "menu_inv_tienda":
        await cmd_inv_por_tienda(update, context)
    elif accion == "menu_inv_fecha":
        await cmd_inv_por_fecha(update, context)
    elif accion.startswith("sel_inv_tienda:"):
        await cmd_inv_tienda_resultado(update, context)
    elif accion.startswith("sel_inv_fecha:"):
        await cmd_inv_fecha_resultado(update, context)
    elif accion == "menu_ia":
        await cmd_ia(update, context)
    elif accion == "fin_topclientes":
        await cmd_top_clientes(update, context)
    elif accion.startswith("menu_verf:"):
        await cmd_ver_foto_directo(update, context)
    elif accion == "menu_ayuda":
        await query.message.reply_text(_texto_ayuda())
    elif accion == "menu_actualizar_pendiente":
        await cmd_actualizar_pendiente(update, context)

# ============================================================
# HANDLER — ACTUALIZAR PENDIENTE
# ============================================================
PENDIENTE_CONFIRMAR = 70

async def cmd_actualizar_pendiente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra ventas pendientes con checkboxes para multi-selección."""
    await _reply(update, "🔄 Buscando ventas pendientes...")
    pendientes = await fetch_ventas_pendientes()
    if not pendientes:
        await _reply(update, "✅ No hay ventas pendientes. ¡Todo está al día!")
        return ConversationHandler.END
    
    context.user_data["pendientes_cache"] = pendientes
    context.user_data["pendientes_seleccionados"] = set()
    
    await _render_pendientes_menu(update, context)
    return PENDIENTE_CONFIRMAR

async def _render_pendientes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    pendientes = context.user_data.get("pendientes_cache", [])
    seleccionados = context.user_data.get("pendientes_seleccionados", set())
    
    botones = []
    for i, v in enumerate(pendientes):
        check = "✅" if i in seleccionados else "⬜"
        lbl = v["label"]
        if len(lbl) > 50: lbl = lbl[:47] + "..."
        botones.append([InlineKeyboardButton(f"{check} {lbl}", callback_data=f"pend_toggle_{i}")])
    
    botones.append([
        InlineKeyboardButton("✅ Marcar Todos", callback_data="pend_sel_all"),
        InlineKeyboardButton("⬜ Desmarcar", callback_data="pend_unsel_all")
    ])
    
    if seleccionados:
        botones.append([InlineKeyboardButton(f"🚀 Confirmar Cobro ({len(seleccionados)})", callback_data="pend_confirm")])
    
    botones.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu_inicio")])
    
    texto = f"🔄 *Ventas pendientes ({len(pendientes)})*\n\nToca para seleccionar las ventas que ya te pagaron, luego pulsa *Confirmar Cobro*:"
    markup = InlineKeyboardMarkup(botones)
    
    if query:
        await query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(texto, reply_markup=markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(texto, reply_markup=markup, parse_mode="Markdown")

async def pendiente_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    pendientes = context.user_data.get("pendientes_cache", [])
    seleccionados = context.user_data.get("pendientes_seleccionados", set())
    
    if data.startswith("pend_toggle_"):
        idx = int(data.replace("pend_toggle_", ""))
        if idx in seleccionados:
            seleccionados.remove(idx)
        else:
            seleccionados.add(idx)
        await _render_pendientes_menu(update, context, query)
        return PENDIENTE_CONFIRMAR
        
    if data == "pend_sel_all":
        context.user_data["pendientes_seleccionados"] = set(range(len(pendientes)))
        await _render_pendientes_menu(update, context, query)
        return PENDIENTE_CONFIRMAR
        
    if data == "pend_unsel_all":
        context.user_data["pendientes_seleccionados"] = set()
        await _render_pendientes_menu(update, context, query)
        return PENDIENTE_CONFIRMAR
        
    if data == "pend_confirm":
        if not seleccionados:
            await query.answer("No has seleccionado ninguna venta.", show_alert=True)
            return PENDIENTE_CONFIRMAR
            
        await query.edit_message_text(f"⏳ Procesando {len(seleccionados)} cobros... por favor espera.")
        count = 0
        # Agrupar boletos por cliente
        boletos_por_cliente = {}
        # Importar tracker del dashboard para evitar duplicados
        from dashboard import _ventas_completadas_procesadas
        for idx in seleccionados:
            v = pendientes[idx]
            if await actualizar_estado_venta(v["id"], "Completado"):
                count += 1
                # Registrar en el tracker para que el checker no lo duplique
                _ventas_completadas_procesadas.add(v["id"])
                cliente = v.get("cliente", "")
                if cliente and cliente.lower() not in ("sin cliente", "anonimo", "anónimo", ""):
                    cant = v.get("cantidad", 0) or 1
                    boletos_por_cliente[cliente] = boletos_por_cliente.get(cliente, 0) + cant
        
        # Asignar boletos automáticamente
        from notion_api import crear_boleto_notion
        boleto_msgs = []
        for cliente, bols in boletos_por_cliente.items():
            if bols > 0:
                await crear_boleto_notion(
                    cliente=cliente,
                    boletos=bols,
                    asunto=f"Cobro de venta(s) pendiente(s)",
                )
                boleto_msgs.append(f"  🎟️ {cliente}: +{bols} boletos")
        
        context.user_data["pendientes_seleccionados"] = set()
        boleto_text = "\n".join(boleto_msgs)
        if boleto_text:
            boleto_text = f"\n\n*Boletos asignados:*\n{boleto_text}"
        await query.edit_message_text(f"✅ *Se marcaron {count} ventas como Completado*{boleto_text}", parse_mode="Markdown")
        return ConversationHandler.END

    return PENDIENTE_CONFIRMAR

# ============================================================
# HANDLER — FOTO NUEVA CON CAPTION
# ============================================================
async def recibir_foto_nueva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.caption:
        await msg.reply_text(
            "Falta el texto.\n\nReenvía la foto con pie de foto:\n"
            "  Nombre, costo, precio, stock\n\nEjemplo: Chompa azul, 96, 130, 12\n\n"
            "(Manten presionada la foto antes de enviar para agregar texto)"
        )
        return
    datos = parsear_caption(msg.caption)
    if not datos:
        await msg.reply_text(
            "Formato incorrecto.\n\nRevisa que el texto tenga:\n"
            "  Nombre, costo, precio, stock\n\nEjemplo: Chompa azul, 96, 130, 12\n\n"
            "Escribe /ayuda si necesitas ayuda."
        )
        return
    nombre, costo, precio, stock, tienda, fecha = datos
    if precio is None:
        costo_unit = costo / stock if stock > 0 else costo
        precio = calcular_precio_sugerido(costo_unit)
        precio_auto = True
    else:
        precio_auto = False
    if costo <= 0 or precio <= 0 or stock <= 0:
        await msg.reply_text("El costo, precio y stock deben ser mayores a 0. Revisa.")
        return
    aviso_precio = f"\n\n💡 Precio calculado automáticamente: S/{precio:.0f}" if precio_auto else ""
    await msg.reply_text("Subiendo foto y guardando en inventario...")
    foto      = msg.photo[-1]
    archivo   = await context.bot.get_file(foto.file_id)
    img_bytes = await archivo.download_as_bytearray()
    foto_url  = await subir_imagen(bytes(img_bytes))
    exito = await crear_prenda_notion(nombre, costo, precio, stock, foto_url, tienda, fecha)
    if exito:
        await msg.reply_text(resumen_prenda(nombre, costo, precio, stock, tienda, fecha) + aviso_precio)
    else:
        await msg.reply_text("Error al guardar en Notion. Intenta de nuevo.")

# ============================================================
# CONVERSATION HANDLER — NUEVA PRENDA GUIADO (v4.2)
# ============================================================
async def cmd_nueva_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _reply(update, "📸 *Nueva prenda*\n\nEscribe el *nombre* de la prenda:")
    return NP_NOMBRE

async def np_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 3:
        await update.message.reply_text("El nombre es muy corto. Escribe al menos 3 letras.")
        return NP_NOMBRE
    context.user_data["np_nombre"] = nombre
    await update.message.reply_text(f"Prenda: *{nombre}*\n\n💵 Escribe el *costo total* del saco (S/):")
    return NP_COSTO

async def np_recibir_costo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",",".")
    try:
        costo = float(texto)
        assert costo > 0
    except:
        await update.message.reply_text("Escribe solo el número del costo. Ejemplo: 480")
        return NP_COSTO
    context.user_data["np_costo_total"] = costo
    # precio sugerido (se calcula más tarde cuando se tenga el stock)
    context.user_data["np_costo_guardado"] = costo
    await update.message.reply_text(
        f"Costo total: S/{costo:.0f}\n\n"
        "🏷️ ¿Cuál es el *precio de venta* por unidad?\n"
        "Escribe el precio o presiona el botón para calcular automáticamente:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Precio sugerido por el bot", callback_data="np_precio_auto")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
    )
    return NP_PRECIO

async def np_recibir_precio_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El precio se calculará tras conocer el stock; guardamos bandera."""
    query = update.callback_query
    await query.answer()
    context.user_data["np_precio_auto"] = True
    await query.edit_message_text(
        "✅ Precio: lo calcularé automáticamente al finalizar.\n\n"
        "📦 ¿En qué *unidad* compraste el stock?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Docenas 📦", callback_data="np_stock_doc")],
            [InlineKeyboardButton("Unidades 🔢", callback_data="np_stock_uni")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_precio")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
    )
    return NP_STOCK_TIPO

async def np_recibir_precio_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",",".")
    try:
        precio = float(texto)
        assert precio > 0
    except:
        await update.message.reply_text("Escribe solo el número. Ejemplo: 130")
        return NP_PRECIO
    context.user_data["np_precio"] = precio
    context.user_data["np_precio_auto"] = False
    await update.message.reply_text(
        f"Precio: S/{precio:.0f}\n\n"
        "📦 ¿En qué *unidad* compraste el stock?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Docenas 📦", callback_data="np_stock_doc")],
            [InlineKeyboardButton("Unidades 🔢", callback_data="np_stock_uni")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_precio")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
    )
    return NP_STOCK_TIPO

async def np_elegir_stock_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "np_stock_doc":
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 doc (12)", callback_data="np_doc_1"),
             InlineKeyboardButton("2 doc (24)", callback_data="np_doc_2")],
            [InlineKeyboardButton("3 doc (36)", callback_data="np_doc_3"),
             InlineKeyboardButton("4 doc (48)", callback_data="np_doc_4")],
            [InlineKeyboardButton("5 doc (60)", callback_data="np_doc_5"),
             InlineKeyboardButton("6 doc (72)", callback_data="np_doc_6")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_stock")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
        await query.edit_message_text("¿Cuántas *docenas* compraste?", reply_markup=teclado)
        return NP_STOCK_DOCENAS
    else:
        await query.edit_message_text("Escribe la cantidad de *unidades*:")
        return NP_STOCK_UNICA

async def np_stock_docenas_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    docenas = int(query.data.replace("np_doc_",""))
    unidades = docenas * 12
    context.user_data["np_stock"] = unidades
    await query.edit_message_text(f"Stock: {docenas} doc → {unidades} unidades ✅")
    await _avanzar_a_tienda(update, context)
    return NP_TIENDA

async def np_stock_unidades_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    try:
        uds = int(texto)
        assert uds > 0
    except:
        await update.message.reply_text("Escribe solo el número entero. Ejemplo: 15")
        return NP_STOCK_UNICA
    context.user_data["np_stock"] = uds
    await _avanzar_a_tienda(update, context)
    return NP_TIENDA

async def _avanzar_a_tienda(update, context):
    tiendas = await fetch_tiendas_registradas()
    botones = [[InlineKeyboardButton(t, callback_data=f"np_tienda:{t}")] for t in tiendas]
    botones.append([InlineKeyboardButton("✏️ Escribir tienda manualmente", callback_data="np_tienda_manual")])
    markup = InlineKeyboardMarkup(botones)
    texto = "🏪 ¿En qué *tienda* compraste la prenda?"
    if update.callback_query:
        await update.callback_query.message.reply_text(texto, reply_markup=markup)
    else:
        await update.message.reply_text(texto, reply_markup=markup)

async def np_recibir_tienda_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "np_tienda_manual":
        await query.edit_message_text("Escribe el nombre de la tienda:")
        return NP_TIENDA
    tienda = query.data.replace("np_tienda:","")
    context.user_data["np_tienda"] = tienda
    await query.edit_message_text(f"Tienda: {tienda} ✅")
    await _avanzar_a_fecha(update, context)
    return NP_FECHA_MES

async def np_recibir_tienda_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tienda = update.message.text.strip()
    context.user_data["np_tienda"] = tienda
    await _avanzar_a_fecha(update, context)
    return NP_FECHA_MES

async def _avanzar_a_fecha(update, context):
    from datetime import datetime, timedelta, timezone
    hoy = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
    mes_actual = hoy.strftime("%B %Y")          # ej. "Mayo 2026"
    mes_ant    = (hoy.replace(day=1) - timedelta(days=1)).strftime("%B %Y")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {mes_ant} (mes anterior)", callback_data="np_mes_ant")],
        [InlineKeyboardButton(f"📅 {mes_actual} (mes actual)", callback_data="np_mes_act")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_stock")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    texto = "📅 ¿En qué *mes* compraste la prenda?"
    if update.callback_query:
        await update.callback_query.message.reply_text(texto, reply_markup=teclado)
    else:
        await update.message.reply_text(texto, reply_markup=teclado)

async def np_elegir_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "np_mes_ant":
        await query.edit_message_text(
            "Escribe la fecha de compra (mes anterior):\nFormato: DD/MM/YYYY"
        )
        return NP_FECHA_DIA
    else:
        from datetime import datetime, timedelta, timezone
        hoy    = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
        ayer   = (hoy - timedelta(days=1)).strftime("%d/%m/%Y")
        hoyfmt = hoy.strftime("%d/%m/%Y")
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Ayer ({ayer})",   callback_data=f"np_dia:{ayer}")],
            [InlineKeyboardButton(f"Hoy ({hoyfmt})",  callback_data=f"np_dia:{hoyfmt}")],
            [InlineKeyboardButton("📝 Otra fecha",    callback_data="np_dia_manual")],
            [InlineKeyboardButton("⬅️ Volver",        callback_data="np_volver_mes")],
            [InlineKeyboardButton("❌ Cancelar",      callback_data="menu_inicio")],
        ])
        await query.edit_message_text("¿Qué día fue la compra?", reply_markup=teclado)
        return NP_FECHA_DIA

async def np_recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        if query.data == "np_dia_manual":
            await query.edit_message_text("Escribe la fecha:\nFormato: DD/MM/YYYY")
            return NP_FECHA_DIA
        fecha_str = query.data.replace("np_dia:","")
        await query.edit_message_text(f"Fecha: {fecha_str} ✅")
    else:
        fecha_str = update.message.text.strip()
    # Parsear fecha
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(fecha_str, fmt)
            fecha_iso = dt.strftime("%Y-%m-%d")
            context.user_data["np_fecha"] = fecha_iso
            await _avanzar_a_foto(update, context)
            return NP_FOTO
        except:
            pass
    texto = "Formato incorrecto. Escribe la fecha así: DD/MM/YYYY\nEjemplo: 01/05/2026"
    if update.callback_query:
        await update.callback_query.message.reply_text(texto)
    else:
        await update.message.reply_text(texto)
    return NP_FECHA_DIA

async def np_volver_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Stock tipo → re-pedir precio."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("np_precio", None)
    context.user_data.pop("np_precio_auto", None)
    costo = context.user_data.get("np_costo_guardado", 0)
    await query.message.reply_text(
        f"Costo total: S/{costo:.0f}\n\n"
        "🏷️ ¿Cuál es el *precio de venta* por unidad?\n"
        "Escribe el precio o presiona el botón para calcular automáticamente:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Precio sugerido por el bot", callback_data="np_precio_auto")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
    )
    return NP_PRECIO

async def np_volver_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Docenas/Mes → re-pedir tipo de stock."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("np_stock_tipo", None)
    context.user_data.pop("np_stock", None)
    await query.message.reply_text(
        "📦 ¿En qué *unidad* compraste el stock?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Docenas 📦", callback_data="np_stock_doc")],
            [InlineKeyboardButton("Unidades 🔢", callback_data="np_stock_uni")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_precio")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
    )
    return NP_STOCK_TIPO

async def np_volver_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Día → re-pedir mes."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("np_fecha_mes", None)
    from datetime import datetime, timedelta, timezone
    hoy        = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
    mes_actual = hoy.strftime("%B %Y")
    mes_ant    = (hoy.replace(day=1) - timedelta(days=1)).strftime("%B %Y")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {mes_ant} (mes anterior)", callback_data="np_mes_ant")],
        [InlineKeyboardButton(f"📅 {mes_actual} (mes actual)", callback_data="np_mes_act")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_stock")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await query.message.reply_text("📅 ¿En qué mes compraste esta prenda?", reply_markup=teclado)
    return NP_FECHA_MES

async def np_volver_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Foto → re-pedir día."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("np_fecha_dia", None)
    from datetime import datetime, timedelta, timezone
    hoy    = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
    ayer   = (hoy - timedelta(days=1)).strftime("%d/%m/%Y")
    hoyfmt = hoy.strftime("%d/%m/%Y")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Ayer ({ayer})",  callback_data=f"np_dia:{ayer}")],
        [InlineKeyboardButton(f"Hoy ({hoyfmt})", callback_data=f"np_dia:{hoyfmt}")],
        [InlineKeyboardButton("📝 Otra fecha",   callback_data="np_dia_manual")],
        [InlineKeyboardButton("⬅️ Volver",       callback_data="np_volver_mes")],
        [InlineKeyboardButton("❌ Cancelar",      callback_data="menu_inicio")],
    ])
    await query.message.reply_text("📅 ¿Qué día compraste esta prenda?", reply_markup=teclado)
    return NP_FECHA_DIA


async def _avanzar_a_foto(update, context):
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📷 Sí, quiero agregar foto", callback_data="np_foto_si")],
        [InlineKeyboardButton("⏭️ No, guardar sin foto",    callback_data="np_foto_no")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="np_volver_dia")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    texto = "¿Quieres agregar una *foto* de la prenda? (opcional)"
    if update.callback_query:
        await update.callback_query.message.reply_text(texto, reply_markup=teclado)
    else:
        await update.message.reply_text(texto, reply_markup=teclado)

async def np_elegir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "np_foto_si":
        await query.edit_message_text("📷 Envía la foto de la prenda:")
        return NP_FOTO
    else:
        await _guardar_nueva_prenda(update, context, foto_url=None)
        return ConversationHandler.END

async def np_recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.photo:
        await msg.reply_text("Envía una foto. Si no tienes, escribe /cancelar")
        return NP_FOTO
    await msg.reply_text("Subiendo foto...")
    foto    = msg.photo[-1]
    archivo = await context.bot.get_file(foto.file_id)
    img_bytes = await archivo.download_as_bytearray()
    foto_url  = await subir_imagen(bytes(img_bytes))
    await _guardar_nueva_prenda(update, context, foto_url=foto_url)
    return ConversationHandler.END

async def _guardar_nueva_prenda(update, context, foto_url=None):
    nombre     = context.user_data.get("np_nombre","")
    costo      = context.user_data.get("np_costo_total", 0)
    stock      = context.user_data.get("np_stock", 0)
    tienda     = context.user_data.get("np_tienda","")
    fecha      = context.user_data.get("np_fecha","")
    precio_auto= context.user_data.get("np_precio_auto", False)
    if precio_auto:
        costo_u = costo / stock if stock > 0 else costo
        precio  = calcular_precio_sugerido(costo_u)
    else:
        precio  = context.user_data.get("np_precio", 0)
    aviso_precio = f"\n💡 Precio sugerido automático: S/{precio:.0f}" if precio_auto else ""
    await (update.callback_query.message if update.callback_query else update.message).reply_text(
        "Guardando en inventario..."
    )
    page_id = await crear_prenda_notion(nombre, costo, precio, stock, foto_url, tienda, fecha)
    teclado_post = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Editar última prenda", callback_data="np_edit_last")],
        [InlineKeyboardButton("➕ Agregar otra prenda", callback_data="menu_nueva_guiado")],
        [InlineKeyboardButton("🏠 Volver al menú",      callback_data="menu_inicio")],
    ])
    if page_id:
        context.user_data.clear()
        context.user_data["last_prenda_id"] = page_id
        context.user_data["last_prenda_nombre"] = nombre
        msg_ok = resumen_prenda(nombre, costo, precio, stock, tienda, fecha) + aviso_precio
        await (update.callback_query.message if update.callback_query else update.message).reply_text(
            msg_ok, reply_markup=teclado_post
        )
        return NP_EDIT_CAMPO
    else:
        await (update.callback_query.message if update.callback_query else update.message).reply_text(
            "❌ Error al guardar en Notion. Intenta de nuevo.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Agregar otra prenda", callback_data="menu_nueva_guiado")],
                [InlineKeyboardButton("🏠 Volver al menú",      callback_data="menu_inicio")],
            ])
        )
        context.user_data.clear()
        return ConversationHandler.END

async def np_edit_elegir_campo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra opciones de qué campo editar de la última prenda registrada."""
    query = update.callback_query
    await query.answer()
    nombre = context.user_data.get("last_prenda_nombre", "última prenda")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Costo", callback_data="npe_Costo"),
         InlineKeyboardButton("🏷️ Precio", callback_data="npe_Precio")],
        [InlineKeyboardButton("🏪 Tienda", callback_data="npe_Tienda"),
         InlineKeyboardButton("📅 Fecha", callback_data="npe_Fecha Compra")],
        [InlineKeyboardButton("📷 Foto", callback_data="npe_Foto")],
        [InlineKeyboardButton("✅ Listo, no editar más", callback_data="npe_done")],
    ])
    await query.edit_message_text(
        f"✏️ *Editar: {nombre}*\n\n¿Qué campo deseas corregir?",
        reply_markup=teclado, parse_mode="Markdown"
    )
    return NP_EDIT_CAMPO

async def np_edit_campo_seleccionado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el campo seleccionado para editar."""
    query = update.callback_query
    await query.answer()
    if query.data == "npe_done":
        await query.edit_message_text("✅ Prenda guardada correctamente.")
        context.user_data.clear()
        return ConversationHandler.END
    campo = query.data.replace("npe_", "")
    if campo == "Foto":
        context.user_data["edit_campo"] = "Foto"
        await query.edit_message_text("📷 Envía la nueva foto de la prenda:")
        return NP_EDIT_FOTO
    context.user_data["edit_campo"] = campo
    etiquetas = {"Costo": "costo total (S/)", "Precio": "precio de venta (S/)",
                 "Tienda": "nombre de tienda", "Fecha Compra": "fecha (DD/MM/YYYY)"}
    await query.edit_message_text(f"Escribe el nuevo valor de *{etiquetas.get(campo, campo)}*:", parse_mode="Markdown")
    return NP_EDIT_VALOR

async def np_edit_recibir_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nuevo valor y actualiza en Notion."""
    page_id = context.user_data.get("last_prenda_id")
    campo   = context.user_data.get("edit_campo", "")
    texto   = update.message.text.strip()
    if not page_id:
        await update.message.reply_text("❌ No se encontró la prenda. Intenta de nuevo.")
        return ConversationHandler.END

    props = {}
    if campo in ("Costo", "Precio"):
        try:
            valor = float(texto.replace(",", "."))
            assert valor > 0
            props[campo] = {"number": valor}
            if campo == "Costo":
                stock = context.user_data.get("np_stock", 0)
                if stock > 0:
                    props["Costo Unitario"] = {"number": round(valor / stock, 2)}
        except:
            await update.message.reply_text("Escribe solo el número. Ejemplo: 480")
            return NP_EDIT_VALOR
    elif campo == "Tienda":
        props["Tienda"] = {"rich_text": [{"text": {"content": texto}}]}
    elif campo == "Fecha Compra":
        from datetime import datetime as dt
        fecha_iso = None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                fecha_iso = dt.strptime(texto, fmt).strftime("%Y-%m-%d")
                break
            except:
                pass
        if not fecha_iso:
            await update.message.reply_text("Formato incorrecto. Usa DD/MM/YYYY. Ejemplo: 01/05/2026")
            return NP_EDIT_VALOR
        props["Fecha Compra"] = {"date": {"start": fecha_iso}}

    exito = await actualizar_prenda_notion(page_id, props)
    if exito:
        await update.message.reply_text(f"✅ *{campo}* actualizado correctamente.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Error al actualizar en Notion.")

    # Mostrar opciones de editar otro campo
    nombre = context.user_data.get("last_prenda_nombre", "última prenda")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Costo", callback_data="npe_Costo"),
         InlineKeyboardButton("🏷️ Precio", callback_data="npe_Precio")],
        [InlineKeyboardButton("🏪 Tienda", callback_data="npe_Tienda"),
         InlineKeyboardButton("📅 Fecha", callback_data="npe_Fecha Compra")],
        [InlineKeyboardButton("📷 Foto", callback_data="npe_Foto")],
        [InlineKeyboardButton("✅ Listo, no editar más", callback_data="npe_done")],
    ])
    await update.message.reply_text(
        f"✏️ *{nombre}* — ¿Deseas corregir otro campo?",
        reply_markup=teclado, parse_mode="Markdown"
    )
    return NP_EDIT_CAMPO

async def np_edit_recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe nueva foto y actualiza en Notion."""
    msg = update.message
    if not msg.photo:
        await msg.reply_text("Envía una foto. Si no deseas cambiarla, escribe /cancelar")
        return NP_EDIT_FOTO
    page_id = context.user_data.get("last_prenda_id")
    await msg.reply_text("Subiendo foto...")
    foto    = msg.photo[-1]
    archivo = await context.bot.get_file(foto.file_id)
    img_bytes = await archivo.download_as_bytearray()
    foto_url  = await subir_imagen(bytes(img_bytes))
    if foto_url and page_id:
        props = {"Foto": {"url": foto_url}}
        await actualizar_prenda_notion(page_id, props)
        await msg.reply_text("✅ Foto actualizada correctamente.")
    else:
        await msg.reply_text("❌ Error al subir la foto.")

    nombre = context.user_data.get("last_prenda_nombre", "última prenda")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Costo", callback_data="npe_Costo"),
         InlineKeyboardButton("🏷️ Precio", callback_data="npe_Precio")],
        [InlineKeyboardButton("🏪 Tienda", callback_data="npe_Tienda"),
         InlineKeyboardButton("📅 Fecha", callback_data="npe_Fecha Compra")],
        [InlineKeyboardButton("📷 Foto", callback_data="npe_Foto")],
        [InlineKeyboardButton("✅ Listo, no editar más", callback_data="npe_done")],
    ])
    await msg.reply_text(
        f"✏️ *{nombre}* — ¿Deseas corregir otro campo?",
        reply_markup=teclado, parse_mode="Markdown"
    )
    return NP_EDIT_CAMPO

# ============================================================
# CONVERSATION HANDLER — SIN FOTO (redirige al flujo guiado)
# ============================================================
async def cmd_sin_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redirige al flujo guiado de nueva prenda (mismo flujo con botones)."""
    return await cmd_nueva_prenda(update, context)

# ============================================================
# CONVERSATION HANDLER — ADJUNTAR FOTO
# ============================================================
async def cmd_adj_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Escribe el nombre (o parte) de la prenda:\n(Cancela con /cancelar)")
    return ADJFOTO_BUSCAR

async def adjfoto_buscar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras para buscar.")
        return ADJFOTO_BUSCAR
    await update.message.reply_text(f"Buscando '{termino}'...")
    prendas = await buscar_prendas_notion(termino)
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'. Intenta con otro nombre.")
        return ADJFOTO_BUSCAR
    if len(prendas) == 1:
        context.user_data["prenda_adj"] = prendas[0]
        await update.message.reply_text(f"Encontre: {prendas[0]['nombre']}\n\nAhora enviame la foto.")
        return ADJFOTO_RECIBIR
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    await update.message.reply_text(
        f"Encontre {len(prendas)} prendas. ¿A cual adjuntas la foto?",
        reply_markup=teclado_lista_prendas(prendas, "sel_adjfoto")
    )
    return ADJFOTO_CONFIRMAR

async def adjfoto_confirmar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_adjfoto:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        prendas_list = list(prendas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_prendas(prendas_list, "sel_adjfoto", pagina)
        )
        return ADJFOTO_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Operacion cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_adjfoto:", "")
    prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error. Intenta de nuevo con /adjfoto")
        return ConversationHandler.END
    context.user_data["prenda_adj"] = prenda
    await query.edit_message_text(f"{prenda['nombre']} seleccionada.\n\nAhora enviame la foto.")
    return ADJFOTO_RECIBIR

async def adjfoto_recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg    = update.message
    prenda = context.user_data.get("prenda_adj")
    if not prenda:
        await msg.reply_text("Algo salio mal. Empieza de nuevo con /adjfoto")
        return ConversationHandler.END
    if not msg.photo:
        await msg.reply_text("Eso no es una foto. Enviame una imagen.")
        return ADJFOTO_RECIBIR
    await msg.reply_text("Subiendo foto...")
    foto      = msg.photo[-1]
    archivo   = await context.bot.get_file(foto.file_id)
    img_bytes = await archivo.download_as_bytearray()
    foto_url  = await subir_imagen(bytes(img_bytes))
    if not foto_url:
        await msg.reply_text("Error al subir la foto. Intenta de nuevo.")
        return ADJFOTO_RECIBIR
    exito = await actualizar_prenda_notion(prenda["id"], {"Foto": {"url": foto_url}})
    if exito:
        await msg.reply_text(f"✅ Foto adjuntada correctamente a {prenda['nombre']}")
    else:
        await msg.reply_text("Error al actualizar en Notion.")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# CONVERSATION HANDLER — REGISTRAR VENTA
# ============================================================
async def cmd_vendi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Registrar venta\n\nEscribe el nombre (o parte) de la prenda vendida:")
    return VENTA_BUSCAR

async def venta_buscar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras para buscar.")
        return VENTA_BUSCAR
    await update.message.reply_text(f"Buscando '{termino}'...")
    prendas    = await buscar_prendas_notion(termino)
    disponibles = [p for p in prendas if p["stock"] > 0]
    agotadas    = [p for p in prendas if p["stock"] == 0]
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'.")
        return VENTA_BUSCAR
    if not disponibles:
        nombres = "\n".join(f"- {p['nombre']}" for p in agotadas)
        await update.message.reply_text(f"Todas las prendas encontradas están agotadas:\n{nombres}")
        return VENTA_BUSCAR
    if len(disponibles) == 1:
        context.user_data["prenda_venta"] = disponibles[0]
        p = disponibles[0]
        await update.message.reply_text(
            f"{p['nombre']}\n{p['stock']} unidades disponibles | Precio: S/{p['precio']:.0f}\n\n¿Cuántas unidades vendiste?"
        )
        return VENTA_CANTIDAD
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in disponibles}
    await update.message.reply_text(
        f"{len(disponibles)} prendas encontradas. ¿Cuál vendiste?",
        reply_markup=teclado_lista_prendas(disponibles, "sel_venta")
    )
    return VENTA_CONFIRMAR

async def venta_confirmar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_venta:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        prendas_list = list(prendas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_prendas(prendas_list, "sel_venta", pagina)
        )
        return VENTA_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Operacion cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_venta:", "")
    prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error. Intenta de nuevo con /venta")
        return ConversationHandler.END
    context.user_data["prenda_venta"] = prenda
    await query.edit_message_text(
        f"{prenda['nombre']}\n{prenda['stock']} unidades disponibles | Precio: S/{prenda['precio']:.0f}\n\n¿Cuántas unidades vendiste?"
    )
    return VENTA_CANTIDAD

async def venta_recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prenda = context.user_data.get("prenda_venta")
    if not prenda:
        await update.message.reply_text("Algo salio mal. Empieza de nuevo con /venta")
        return ConversationHandler.END
    try:
        cantidad = int(update.message.text.strip())
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Escribe un numero entero mayor a 0.")
        return VENTA_CANTIDAD
    if cantidad > prenda["stock"]:
        await update.message.reply_text(f"Solo hay {prenda['stock']} unidades. ¿Cuántas vendiste realmente?")
        return VENTA_CANTIDAD
    context.user_data["venta_cantidad"] = cantidad
    precio_std = prenda["precio"]
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Precio normal S/{precio_std:.0f}", callback_data="precio_venta_std")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="volver_cantidad")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await update.message.reply_text(f"¿A qué precio vendiste cada una? (Elige Precio normal o escribe el monto)", reply_markup=teclado)
    return VENTA_PRECIO

async def venta_recibir_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    prenda = context.user_data.get("prenda_venta")
    if query.data == "precio_venta_std":
        context.user_data["venta_precio_venta"] = prenda["precio"]
        await pregunta_descuento(query.message)
        return VENTA_DESCUENTO
    return VENTA_PRECIO

async def venta_recibir_precio_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio_venta = float(update.message.text.strip().replace(",", "."))
        if precio_venta <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Escribe un precio válido. Ejemplo: 35 o 35.50")
        return VENTA_PRECIO
    context.user_data["venta_precio_venta"] = precio_venta
    await pregunta_descuento(update.message)
    return VENTA_DESCUENTO

async def pregunta_fecha(msg_obj):
    from datetime import datetime, timedelta, timezone
    ahora    = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
    dia_hoy  = ahora.strftime("%a %d/%m").capitalize()
    dia_ayer = (ahora - timedelta(days=1)).strftime("%a %d/%m").capitalize()
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Hoy ({dia_hoy})", callback_data="fecha_venta_hoy")],
        [InlineKeyboardButton(f"Ayer ({dia_ayer})", callback_data="fecha_venta_ayer")],
        [InlineKeyboardButton("Otra fecha", callback_data="fecha_venta_otra")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="volver_descuento")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await msg_obj.reply_text("¿Cuándo fue la venta?", reply_markup=teclado)

async def venta_recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime, timedelta, timezone
    query = update.callback_query
    await query.answer()
    ahora = datetime.now(timezone.utc) - timedelta(hours=5)  # Lima UTC-5
    if query.data == "fecha_venta_hoy":
        context.user_data["venta_fecha"] = ahora.strftime("%Y-%m-%d")
        await venta_pedir_cliente(query.message, context)
        return VENTA_CLIENTE
    elif query.data == "fecha_venta_ayer":
        context.user_data["venta_fecha"] = (ahora - timedelta(days=1)).strftime("%Y-%m-%d")
        await venta_pedir_cliente(query.message, context)
        return VENTA_CLIENTE
    else:
        await query.message.reply_text("Escribe la fecha en formato DD/MM/YYYY:")
        return VENTA_FECHA

async def venta_recibir_fecha_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        fecha = datetime.strptime(update.message.text.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        context.user_data["venta_fecha"] = fecha
        await venta_pedir_cliente(update.message, context)
        return VENTA_CLIENTE
    except ValueError:
        await update.message.reply_text("Formato incorrecto. Usa DD/MM/YYYY. Ejemplo: 03/05/2026")
        return VENTA_FECHA




async def venta_pedir_cliente(msg_obj, context, pagina=0):
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

async def venta_recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        data = query.data
        if data.startswith("page_cliente:"):
            pagina = int(data.split(":")[1])
            await venta_pedir_cliente(query.message, context, pagina=pagina)
            return VENTA_CLIENTE
        if data == "cliente_sin_nombre":
            context.user_data["venta_cliente"] = ""
            await _finalizar_venta(update, context)
            return ConversationHandler.END
        elif data == "cliente_nueva":
            await query.message.reply_text("✏️ Escribe el nombre de la nueva clienta:")
            return VENTA_CLIENTE
        elif data.startswith("cliente_prev_"):
            context.user_data["venta_cliente"] = data[len("cliente_prev_"):]
            await _finalizar_venta(update, context)
            return ConversationHandler.END
    else:
        context.user_data["venta_cliente"] = update.message.text.strip() if update.message else ""
        await _finalizar_venta(update, context)
        return ConversationHandler.END

async def venta_recibir_cliente_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["venta_cliente"] = update.message.text.strip()
    await _finalizar_venta(update, context)
    return ConversationHandler.END

async def pregunta_descuento(msg_obj):
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sin descuento", callback_data="descuento_no")],
        [InlineKeyboardButton("Sí hubo descuento", callback_data="descuento_si")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="volver_precio")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await msg_obj.reply_text("¿Aplicaste algún descuento?", reply_markup=teclado)

async def venta_recibir_descuento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "descuento_no":
        context.user_data["venta_descuento"] = 0.0
        await pregunta_fecha(query.message)
        return VENTA_FECHA
    else:
        precio_actual = context.user_data.get("venta_precio_venta", 0)
        await query.message.reply_text(
            f"Precio registrado: S/{precio_actual:.0f}\n"
            "¿Cuánto fue el descuento? (en soles)\n"
            "Ejemplo: 1 o 2"
        )
        return VENTA_DESCUENTO

async def venta_recibir_descuento_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        descuento = float(update.message.text.strip().replace(",", "."))
        if descuento < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Escribe un monto válido. Ejemplo: 5 o 10.50")
        return VENTA_DESCUENTO
    context.user_data["venta_descuento"] = descuento
    precio_actual = context.user_data.get("venta_precio_venta", 0)
    await update.message.reply_text(
        f"✅ Descuento de S/{descuento:.0f} registrado. "
        f"Precio final: S/{precio_actual - descuento:.0f}"
    )
    await pregunta_fecha(update.message)
    return VENTA_FECHA

async def venta_volver_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Precio → re-pedir cantidad."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("venta_precio_venta", None)
    prenda = context.user_data.get("prenda_venta")
    await query.message.reply_text(
        f"¿Cuántas unidades de *{prenda['nombre']}* vendiste?\nEscribe solo el número.",
        parse_mode="Markdown"
    )
    return VENTA_CANTIDAD

async def venta_volver_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Descuento → re-pedir precio."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("venta_descuento", None)
    prenda = context.user_data.get("prenda_venta")
    precio_std = prenda["precio"]
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Precio normal S/{precio_std:.0f}", callback_data="precio_venta_std")],
        [InlineKeyboardButton("⬅️ Volver", callback_data="volver_cantidad")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await query.message.reply_text("¿A qué precio vendiste cada una?", reply_markup=teclado)
    return VENTA_PRECIO

async def venta_volver_descuento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Fecha → re-pedir descuento."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("venta_fecha", None)
    await pregunta_descuento(query.message)
    return VENTA_DESCUENTO

async def venta_volver_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver desde Cliente → re-pedir fecha."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("venta_cliente", None)
    await pregunta_fecha(query.message)
    return VENTA_FECHA


async def _finalizar_venta(update, context):
    prenda      = context.user_data.get("prenda_venta")
    cantidad    = context.user_data.get("venta_cantidad")
    precio_venta = context.user_data.get("venta_precio_venta")
    fecha       = context.user_data.get("venta_fecha")
    descuento   = context.user_data.get("venta_descuento", 0.0)
    cliente     = context.user_data.get("venta_cliente", "")
    if not all([prenda, cantidad, precio_venta, fecha]):
        await _reply(update, "Datos incompletos. Intenta de nuevo con /venta")
        context.user_data.clear()
        return
    costo_u      = prenda["costo_u"]
    ganancia_tot = (precio_venta - descuento - costo_u) * cantidad
    nuevo_stock  = prenda["stock"] - cantidad
    await actualizar_prenda_notion(prenda["id"], {"Stock": {"number": nuevo_stock}})
    await crear_venta_notion(
        prenda_id=prenda["id"],
        cantidad=cantidad,
        precio_final=precio_venta,
        ganancia=ganancia_tot,
        fecha_iso=fecha,
        cliente=cliente,
        descuento=descuento,
    )
    
    # Auto-asignar boletos por la compra (1 boleto por prenda)
    from notion_api import crear_boleto_notion
    if cliente and cliente.lower() != "anonimo" and cantidad > 0:
        await crear_boleto_notion(
            cliente=cliente,
            boletos=cantidad,
            asunto=f"Compra de {cantidad}x {prenda['nombre']}",
            fecha_iso=fecha
        )
    descuento_linea = f"\nDescuento:  -S/{descuento:.0f}" if descuento > 0 else ""
    msg = (
        f"✅ Venta registrada!\n\n"
        f"Prenda: {prenda['nombre']}\n"
        f"Vendidas: {cantidad} uds a S/{precio_venta:.0f}"
        f"{descuento_linea}\n"
        f"Ganancia: S/{ganancia_tot:.0f}\n"
        f"Stock restante: {nuevo_stock} uds"
    )
    if nuevo_stock == 0:
        msg += "\n\n⚠️ ¡Prenda AGOTADA! Considera reponerla."
    elif nuevo_stock <= 3:
        msg += f"\n\n⚡ Stock bajo: solo quedan {nuevo_stock} uds."
    teclado_post = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Registrar otra venta", callback_data="menu_venta")],
        [InlineKeyboardButton("🏠 Volver al menú",        callback_data="menu_inicio")],
    ])
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=teclado_post)
    elif update.message:
        await update.message.reply_text(msg, reply_markup=teclado_post)
    else:
        await _reply(update, msg, reply_markup=teclado_post)

# ============================================================
# CONVERSATION HANDLER — CONSULTAR PRENDA
# ============================================================
async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Consultar prenda\n\nEscribe el nombre (o parte):")
    return STOCK_BUSCAR

async def stock_buscar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return STOCK_BUSCAR
    await update.message.reply_text(f"Buscando '{termino}'...")
    prendas = await buscar_prendas_notion(termino)
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'.")
        return STOCK_BUSCAR
    if len(prendas) == 1:
        prenda = prendas[0]
        texto = await _formato_stock(prenda)
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ Ver foto", callback_data=f"menu_verf:{prenda['id']}")]
        ])
        await update.message.reply_text(texto, reply_markup=teclado)
        return ConversationHandler.END
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    await update.message.reply_text(
        f"Encontre {len(prendas)} prendas. ¿Cuál quieres consultar?",
        reply_markup=teclado_lista_prendas(prendas, "sel_stock")
    )
    return STOCK_CONFIRMAR

async def stock_confirmar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        if query.data.startswith("page_sel_stock:"):
            pagina = int(query.data.split(":")[1])
            prendas_dict = context.user_data.get("prendas_encontradas", {})
            prendas_list = list(prendas_dict.values())
            await query.edit_message_reply_markup(
                reply_markup=teclado_lista_prendas(prendas_list, "sel_stock", pagina)
            )
            return STOCK_CONFIRMAR
        if query.data == "cancelar":
            await query.edit_message_text("Cancelado.")
            context.user_data.clear()
            return ConversationHandler.END
        
        page_id = query.data.replace("sel_stock:", "")
        prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
        if not prenda:
            await query.edit_message_text("Error. Intenta de nuevo con /prenda")
            return ConversationHandler.END
        
        # Mostrar datos de la prenda y botón para ver foto
        texto = await _formato_stock(prenda)
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼️ Ver foto", callback_data=f"menu_verf:{page_id}")]
        ])
        await query.edit_message_text(texto, reply_markup=teclado)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        import traceback
        error_msg = f"Error en stock_confirmar_prenda: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        await query.message.reply_text(f"Ocurrió un error interno:\n{str(e)}")
        context.user_data.clear()
        return ConversationHandler.END

# ============================================================
# CONVERSATION HANDLER — EDITAR PRENDA
# ============================================================
# ============================================================
# CONVERSATION HANDLER — ELIMINAR VENTA
# ============================================================
async def cmd_eliminar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Eliminar venta\n\nEscribe el nombre (o parte) de la prenda de la venta a eliminar:")
    return ELIMINAR_VENTA_BUSCAR

async def eliminar_venta_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return ELIMINAR_VENTA_BUSCAR
    await update.message.reply_text("Buscando ventas...")
    ventas = await buscar_ventas_notion(termino)
    if not ventas:
        await update.message.reply_text("No encontré ventas con ese nombre.")
        return ELIMINAR_VENTA_BUSCAR
    context.user_data["ventas_encontradas"] = {v["id"]: v for v in ventas}
    await update.message.reply_text(
        f"Encontré {len(ventas)} ventas. ¿Cuál quieres eliminar?",
        reply_markup=teclado_lista_ventas(ventas, "sel_elimventa")
    )
    return ELIMINAR_VENTA_CONFIRMAR

async def eliminar_venta_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_elimventa:"):
        pagina = int(query.data.split(":")[1])
        ventas_dict = context.user_data.get("ventas_encontradas", {})
        ventas_list = list(ventas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_ventas(ventas_list, "sel_elimventa", pagina)
        )
        return ELIMINAR_VENTA_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Operación cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_elimventa:", "")
    venta   = context.user_data.get("ventas_encontradas", {}).get(page_id)
    if not venta:
        await query.edit_message_text("Error. Intenta de nuevo con /eliminar_venta")
        return ConversationHandler.END
    exito = await eliminar_venta_notion(page_id)
    if exito:
        await query.edit_message_text(
            f"✅ Venta eliminada y stock restaurado.\n\n"
            f"Prenda: {venta['nombre']}\n"
            f"Cantidad: {venta['cantidad']} uds\n"
            f"Stock restaurado: +{venta['cantidad']} uds"
        )
    else:
        await query.edit_message_text("❌ Error al eliminar la venta. Intenta de nuevo.")
    context.user_data.clear()
    return ConversationHandler.END

async def cmd_editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "✏️ Actualizar / Eliminar prenda\n\nEscribe el nombre (o parte) de la prenda:")
    return EDITAR_BUSCAR

async def editar_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return EDITAR_BUSCAR
    prendas = await buscar_prendas_notion(termino)
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'.")
        return EDITAR_BUSCAR
    if len(prendas) == 1:
        context.user_data["prenda_editar"] = prendas[0]
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Nombre",  callback_data="ec_nombre"),
             InlineKeyboardButton("💵 Costo",   callback_data="ec_costo")],
            [InlineKeyboardButton("🏷️ Precio",  callback_data="ec_precio"),
             InlineKeyboardButton("📦 Stock",   callback_data="ec_stock")],
            [InlineKeyboardButton("🏪 Tienda",  callback_data="ec_tienda"),
             InlineKeyboardButton("📅 Fecha",   callback_data="ec_fecha")],
            [InlineKeyboardButton("🗑️ Eliminar esta prenda", callback_data="ec_eliminar")],
            [InlineKeyboardButton("❌ Cancelar",              callback_data="cancelar")],
        ])
        await update.message.reply_text(
            f"Prenda: *{prendas[0]['nombre']}*\n\n¿Qué quieres hacer?",
            reply_markup=teclado,
            parse_mode="Markdown"
        )
        return EDITAR_CAMPO
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    await update.message.reply_text(
        f"Encontre {len(prendas)} prendas. ¿Cuál quieres editar?",
        reply_markup=teclado_lista_prendas(prendas, "sel_editar")
    )
    return EDITAR_CONFIRMAR

async def editar_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_editar:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        prendas_list = list(prendas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_prendas(prendas_list, "sel_editar", pagina)
        )
        return EDITAR_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Cancelado.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_editar:", "")
    prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error.")
        return ConversationHandler.END
    context.user_data["prenda_editar"] = prenda
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Nombre",  callback_data="ec_nombre"),
         InlineKeyboardButton("💵 Costo",   callback_data="ec_costo")],
        [InlineKeyboardButton("🏷️ Precio",  callback_data="ec_precio"),
         InlineKeyboardButton("📦 Stock",   callback_data="ec_stock")],
        [InlineKeyboardButton("🏪 Tienda",  callback_data="ec_tienda"),
         InlineKeyboardButton("📅 Fecha",   callback_data="ec_fecha")],
        [InlineKeyboardButton("🗑️ Eliminar esta prenda", callback_data="ec_eliminar")],
        [InlineKeyboardButton("❌ Cancelar",              callback_data="cancelar")],
    ])
    await query.edit_message_text(
        f"Prenda: *{prenda['nombre']}*\n\n¿Qué quieres hacer?",
        reply_markup=teclado
    )
    return EDITAR_CAMPO

async def editar_campo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prenda = context.user_data.get("prenda_editar")

    if query.data == "cancelar":
        await query.edit_message_text("Cancelado.")
        context.user_data.clear()
        return ConversationHandler.END

    # ── Eliminar prenda ──────────────────────────────────────
    if query.data == "ec_eliminar":
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, eliminar definitivamente", callback_data="ec_elim_ok")],
            [InlineKeyboardButton("❌ Cancelar",                      callback_data="cancelar")],
        ])
        await query.edit_message_text(
            f"⚠️ ¿Segura que quieres eliminar *{prenda['nombre']}*?\n"
            "Esto no se puede deshacer.",
            reply_markup=teclado
        )
        return EDITAR_CAMPO

    if query.data == "ec_elim_ok":
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{prenda['id']}",
            headers=NOTION_HEADERS, json={"archived": True}
        , timeout=15)
        if r.status_code == 200:
            await query.edit_message_text(f"🗑️ Prenda *{prenda['nombre']}* eliminada correctamente.")
        else:
            await query.edit_message_text("❌ Error al eliminar. Intenta de nuevo.")
        context.user_data.clear()
        return ConversationHandler.END

    # ── Editar campo ─────────────────────────────────────────
    campo_map = {
        "ec_nombre": "nombre",
        "ec_costo":  "costo",
        "ec_precio": "precio",
        "ec_stock":  "stock",
        "ec_tienda": "tienda",
        "ec_fecha":  "fecha",
    }
    campo = campo_map.get(query.data)
    if not campo:
        await query.edit_message_text("Opción no reconocida.")
        return ConversationHandler.END
    context.user_data["campo_editar"] = campo
    hints = {
        "nombre": "Escribe el nuevo nombre:",
        "costo":  "Escribe el nuevo costo total (S/):",
        "precio": "Escribe el nuevo precio de venta (S/):",
        "stock":  "Escribe el nuevo stock (número entero):",
        "tienda": "Escribe el nombre de la tienda:",
        "fecha":  "Escribe la nueva fecha (DD/MM/YYYY):",
    }
    await query.edit_message_text(hints[campo])
    return EDITAR_VALOR

async def editar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prenda = context.user_data.get("prenda_editar")
    campo  = context.user_data.get("campo_editar")
    valor  = update.message.text.strip()
    cambios = {}
    try:
        if campo == "nombre":
            cambios["Prenda"] = {"title": [{"text": {"content": valor}}]}
        elif campo == "costo":
            costo = float(valor)
            cambios["Costo"] = {"number": costo}
            if prenda["stock"] > 0:
                cambios["Costo Unitario"] = {"number": round(costo / prenda["stock"], 2)}
        elif campo == "precio":
            cambios["Precio"] = {"number": float(valor)}
        elif campo == "stock":
            cambios["Stock"] = {"number": int(valor)}
        elif campo == "tienda":
            cambios["Tienda"] = {"rich_text": [{"text": {"content": valor}}]}
        elif campo == "fecha":
            fecha = datetime.strptime(valor, "%d/%m/%Y").strftime("%Y-%m-%d")
            cambios["Fecha Compra"] = {"date": {"start": fecha}}
    except ValueError:
        await update.message.reply_text("Valor inválido. Intenta de nuevo.")
        return EDITAR_VALOR
    exito = await actualizar_prenda_notion(prenda["id"], cambios)
    if exito:
        await update.message.reply_text(f"✅ '{campo}' actualizado correctamente en {prenda['nombre']}.")
    else:
        await update.message.reply_text("❌ Error al actualizar. Intenta de nuevo.")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# CONVERSATION HANDLER — ELIMINAR PRENDA
# ============================================================
async def cmd_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Eliminar prenda\n\nEscribe el nombre (o parte):")
    return ELIMINAR_BUSCAR

async def eliminar_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    prendas = await buscar_prendas_notion(termino)
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'.")
        return ELIMINAR_BUSCAR
    if len(prendas) == 1:
        context.user_data["prenda_eliminar"] = prendas[0]
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sí, eliminar", callback_data="confirmar_eliminar")],
            [InlineKeyboardButton("❌ Cancelar",     callback_data="cancelar")],
        ])
        await update.message.reply_text(
            f"¿Segura que quieres eliminar '{prendas[0]['nombre']}'? Esta acción no se puede deshacer.",
            reply_markup=teclado
        )
        return ELIMINAR_CONFIRMAR
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    await update.message.reply_text(
        f"Encontre {len(prendas)} prendas. ¿Cuál quieres eliminar?",
        reply_markup=teclado_lista_prendas(prendas, "sel_eliminar")
    )
    return ELIMINAR_CONFIRMAR

async def eliminar_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_eliminar:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        prendas_list = list(prendas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_prendas(prendas_list, "sel_eliminar", pagina)
        )
        return ELIMINAR_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Cancelado.")
        context.user_data.clear()
        return ConversationHandler.END
    if query.data == "confirmar_eliminar":
        prenda = context.user_data.get("prenda_eliminar")
        r = requests.patch(
            f"https://api.notion.com/v1/pages/{prenda['id']}",
            headers=NOTION_HEADERS,
            json={"archived": True}
        , timeout=15)
        if r.status_code == 200:
            await query.edit_message_text(f"✅ '{prenda['nombre']}' eliminada del inventario.")
        else:
            await query.edit_message_text("❌ Error al eliminar. Intenta de nuevo.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_eliminar:", "")
    prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error.")
        return ConversationHandler.END
    context.user_data["prenda_eliminar"] = prenda
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Sí, eliminar", callback_data="confirmar_eliminar")],
        [InlineKeyboardButton("❌ Cancelar",     callback_data="cancelar")],
    ])
    await query.edit_message_text(
        f"¿Segura que quieres eliminar '{prenda['nombre']}'? Esta acción no se puede deshacer.",
        reply_markup=teclado
    )
    return ELIMINAR_CONFIRMAR

# ============================================================
# CONVERSATION HANDLER — VER FOTO
# ============================================================
async def cmd_ver_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Ver foto\n\nEscribe el nombre (o parte) de la prenda:")
    return FOTO_BUSCAR

async def verfoto_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return FOTO_BUSCAR
    prendas = await buscar_prendas_notion(termino)
    if not prendas:
        await update.message.reply_text(f"No encontre prendas con '{termino}'.")
        return FOTO_BUSCAR
    if len(prendas) == 1:
        foto_url = await obtener_foto_url(prendas[0]["id"])
        if foto_url:
            await update.message.reply_photo(photo=foto_url, caption=prendas[0]["nombre"])
        else:
            await update.message.reply_text(f"'{prendas[0]['nombre']}' no tiene foto registrada.")
        return ConversationHandler.END
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    await update.message.reply_text(
        f"Encontre {len(prendas)} prendas. ¿De cuál quieres ver la foto?",
        reply_markup=teclado_lista_prendas(prendas, "sel_foto")
    )
    return FOTO_CONFIRMAR

async def verfoto_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("page_sel_foto:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        prendas_list = list(prendas_dict.values())
        await query.edit_message_reply_markup(
            reply_markup=teclado_lista_prendas(prendas_list, "sel_foto", pagina)
        )
        return FOTO_CONFIRMAR
    if query.data == "cancelar":
        await query.edit_message_text("Cancelado.")
        context.user_data.clear()
        return ConversationHandler.END
    page_id = query.data.replace("sel_foto:", "")
    prenda  = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error.")
        return ConversationHandler.END
    foto_url = await obtener_foto_url(page_id)
    if foto_url:
        await query.message.reply_photo(photo=foto_url, caption=prenda["nombre"])
    else:
        await query.edit_message_text(f"'{prenda['nombre']}' no tiene foto registrada.")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# CONVERSATION HANDLER — COMPARAR PRENDAS
# ============================================================
async def cmd_comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update,
        "Comparar prendas\n\nEscribe los nombres separados por coma.\n"
        "Ejemplo: chompa azul, blusa floral"
    )
    return COMPARAR_BUSCAR

async def comparar_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    terminos = [t.strip() for t in update.message.text.split(",") if t.strip()]
    if len(terminos) < 2:
        await update.message.reply_text("Escribe al menos 2 prendas separadas por coma.")
        return COMPARAR_BUSCAR
    inventario = await fetch_inventario_completo() or []
    encontradas = []
    no_encontradas = []
    campos = [
        ("Stock actual", lambda p: f"{p['stock']} uds"),
        ("Precio", lambda p: f"S/{p['precio']:.0f}"),
        ("Costo unit.", lambda p: f"S/{p['costo_u']:.2f}"),
        ("Ganancia/ud", lambda p: f"S/{p['ganancia_u']:.0f}"),
        ("Margen", lambda p: f"{p['margen']}%"),
        ("Vendidas", lambda p: f"{p['vendidas']} uds"),
        ("Ganancia total", lambda p: f"S/{p['ganancia_real']:.0f}"),
    ]
    for termino in terminos:
        res = [p for p in inventario if termino.lower() in p["nombre"].lower()]
        if res:
            encontradas.append(res[0])
        else:
            no_encontradas.append(termino)
    if len(encontradas) < 2:
        await update.message.reply_text(
            f"No encontre suficientes prendas. No encontradas: {', '.join(no_encontradas)}"
        )
        return COMPARAR_BUSCAR
    lineas = ["📊 Comparación de prendas\n"]
    detalle = {p["id"]: p for p in encontradas}
    for label, fn in campos:
        valores = "  |  ".join(fn(detalle[p["id"]]) for p in encontradas)
        lineas.append(f"{label:15}: {valores}")
    nombres = "  vs  ".join(p["nombre"] for p in encontradas)
    lineas.insert(1, nombres + "\n")
    if no_encontradas:
        lineas.append(f"\nNo encontradas: {', '.join(no_encontradas)}")
    await update.message.reply_text("\n".join(lineas))
    return ConversationHandler.END

# ============================================================
# COMANDOS DE REPORTES
# ============================================================
async def cmd_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Consultando inventario completo...")
    prendas = await fetch_inventario_completo()
    if prendas is None:
        await _reply(update, "Error al consultar Notion.")
        return
    if not prendas:
        await _reply(update, "El inventario está vacío.")
        return
    disp     = sum(1 for p in prendas if p["estado"] == "Disponible")
    limitado = sum(1 for p in prendas if p["estado"] == "Stock limitado")
    agotado  = sum(1 for p in prendas if p["estado"] == "Agotado")
    lineas = [
        f"Inventario completo ({len(prendas)} prendas)\n",
        f"Verde (Disponible):      {disp}",
        f"Amarillo (Stock bajo):   {limitado}",
        f"Rojo (Agotado):          {agotado}\n",
    ]
    # Tabla en formato monospace para Telegram
    col_nombre = max(len(p["nombre"]) for p in prendas)
    col_nombre = min(col_nombre, 22)  # máximo 22 chars
    encabezado = f"{'Prenda':<22} {'Stk':>4} {'S/':>5} Est"
    separador  = "─" * (22 + 4 + 5 + 4 + 3)
    filas = [encabezado, separador]
    for p in prendas:
        icono  = "🟢" if p["estado"] == "Disponible" else ("🟡" if p["estado"] == "Stock limitado" else "🔴")
        nombre = p["nombre"][:22].ljust(22)
        stk    = str(p["stock"]).rjust(4)
        precio = str(int(p["precio"])).rjust(5)
        filas.append(f"{nombre} {stk} {precio} {icono}")
    tabla = "\n".join(filas)
    resumen_hdr = "\n".join(lineas)
    await _reply(update, resumen_hdr + "\n\n<pre>" + tabla + "</pre>", parse_mode="HTML")

# ============================================================
# HANDLER — INVENTARIO FILTRADO POR TIENDA / FECHA
# ============================================================
def _tabla_prendas(prendas, titulo):
    """Genera una tabla formateada de prendas para Telegram."""
    if not prendas:
        return f"{titulo}\n\nNo se encontraron prendas."
    disp     = sum(1 for p in prendas if p["estado"] == "Disponible")
    limitado = sum(1 for p in prendas if p["estado"] == "Stock limitado")
    agotado  = sum(1 for p in prendas if p["estado"] == "Agotado")
    lineas = [
        f"{titulo} ({len(prendas)} prendas)\n",
        f"🟢 Disponible: {disp}  🟡 Stock bajo: {limitado}  🔴 Agotado: {agotado}\n",
    ]
    encabezado = f"{'Prenda':<22} {'Stk':>4} {'S/':>5} Est"
    separador  = "─" * (22 + 4 + 5 + 4 + 3)
    filas = [encabezado, separador]
    for p in prendas:
        icono  = "🟢" if p["estado"] == "Disponible" else ("🟡" if p["estado"] == "Stock limitado" else "🔴")
        nombre = p["nombre"][:22].ljust(22)
        stk    = str(p["stock"]).rjust(4)
        precio = str(int(p["precio"])).rjust(5)
        filas.append(f"{nombre} {stk} {precio} {icono}")
    tabla = "\n".join(filas)
    resumen_hdr = "\n".join(lineas)
    return resumen_hdr + "\n<pre>" + tabla + "</pre>"

async def cmd_inv_por_tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra botones con tiendas registradas para filtrar inventario."""
    query = update.callback_query
    if query:
        await query.answer()
    tiendas = await fetch_tiendas_registradas()
    if not tiendas:
        await _reply(update, "No hay tiendas registradas en el inventario.")
        return
    # Guardar mapeo índice → tienda para evitar callback_data largo
    context.user_data["inv_tiendas"] = {str(i): t for i, t in enumerate(tiendas)}
    botones = [[InlineKeyboardButton(f"🏪 {t}", callback_data=f"sel_inv_tienda:{i}")] for i, t in enumerate(tiendas)]
    botones.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu_inventario_sub")])
    await _reply(update, "🏪 *¿De qué tienda deseas ver el inventario?*",
                 reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def cmd_inv_tienda_resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el inventario filtrado por tienda."""
    query = update.callback_query
    await query.answer()
    idx = query.data.replace("sel_inv_tienda:", "")
    tienda = context.user_data.get("inv_tiendas", {}).get(idx, idx)
    await query.message.reply_text(f"Buscando prendas de *{tienda}*...", parse_mode="Markdown")
    prendas = await fetch_inventario_completo()
    if not prendas:
        await query.message.reply_text("Error al consultar inventario.")
        return
    filtradas = [p for p in prendas if p.get("tienda", "").strip().lower() == tienda.strip().lower()]
    texto = _tabla_prendas(filtradas, f"🏪 Inventario — {tienda}")
    await query.message.reply_text(texto, parse_mode="HTML")


async def cmd_inv_por_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra botones con meses de compra registrados para filtrar inventario."""
    query = update.callback_query
    if query:
        await query.answer()
    prendas = await fetch_inventario_completo()
    if not prendas:
        await _reply(update, "No hay prendas en el inventario.")
        return
    meses = sorted({p["fecha"][:7] for p in prendas if p.get("fecha", "")}, reverse=True)
    if not meses:
        await _reply(update, "No hay fechas de compra registradas en el inventario.")
        return
    from datetime import datetime
    botones = []
    for m in meses[:12]:  # últimos 12 meses
        try:
            label = datetime.strptime(m, "%Y-%m").strftime("%B %Y").capitalize()
        except:
            label = m
        botones.append([InlineKeyboardButton(f"📅 {label}", callback_data=f"sel_inv_fecha:{m}")])
    botones.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu_inventario_sub")])
    await _reply(update, "📅 *¿De qué mes de compra deseas ver el inventario?*",
                 reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")

async def cmd_inv_fecha_resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el inventario filtrado por mes de compra."""
    query = update.callback_query
    await query.answer()
    mes = query.data.replace("sel_inv_fecha:", "")
    from datetime import datetime
    try:
        label = datetime.strptime(mes, "%Y-%m").strftime("%B %Y").capitalize()
    except:
        label = mes
    await query.message.reply_text(f"Buscando prendas compradas en *{label}*...", parse_mode="Markdown")
    prendas = await fetch_inventario_completo()
    if not prendas:
        await query.message.reply_text("Error al consultar inventario.")
        return
    filtradas = [p for p in prendas if p.get("fecha", "").startswith(mes)]
    texto = _tabla_prendas(filtradas, f"📅 Inventario — {label}")
    await query.message.reply_text(texto, parse_mode="HTML")

async def cmd_ganancias_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submenú financiero con opciones de resumen."""
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 Resumen general",  callback_data="fin_resumen")],
        [InlineKeyboardButton("📈 Por margen",        callback_data="fin_pormargen")],
        [InlineKeyboardButton("🏪 Por tienda",        callback_data="fin_portienda")],
        [InlineKeyboardButton("📅 Por fecha",         callback_data="fin_porfecha")],
        [InlineKeyboardButton("👥 Top Clientes",      callback_data="fin_topclientes")],
        [InlineKeyboardButton("❌ Cancelar",          callback_data="menu_inicio")],
    ])
    msg = update.message or update.callback_query.message
    await msg.reply_text("💰 *Ganancias — ¿qué quieres ver?*", reply_markup=teclado, parse_mode="Markdown")

async def cmd_ganancias_fecha_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submenú de ganancias por fecha."""
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 Hoy",          callback_data="fin_fecha_hoy")],
        [InlineKeyboardButton("📆 Ayer",         callback_data="fin_fecha_ayer")],
        [InlineKeyboardButton("📆 Esta semana",  callback_data="fin_fecha_semana")],
        [InlineKeyboardButton("📆 Este mes",     callback_data="fin_fecha_mes")],
        [InlineKeyboardButton("⬅️ Volver",       callback_data="menu_ganancias")],
        [InlineKeyboardButton("❌ Cancelar",     callback_data="menu_inicio")],
    ])
    query = update.callback_query
    await query.edit_message_text("📅 *Ganancias por fecha — ¿qué período?*", reply_markup=teclado, parse_mode="Markdown")

async def cmd_ganancias_por_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calcula ganancias netas del período solicitado consultando la BD de ventas."""
    from datetime import timedelta, datetime as dt
    import pytz
    query = update.callback_query
    await query.answer()
    periodo = query.data  # fin_fecha_hoy / ayer / semana / mes

    # Usar timezone Lima (UTC-5) en vez de UTC del servidor
    tz_lima = pytz.timezone('America/Lima')
    hoy = dt.now(tz_lima).date()
    if periodo == "fin_fecha_hoy":
        desde = hasta = hoy
        etiqueta = "Hoy"
    elif periodo == "fin_fecha_ayer":
        desde = hasta = hoy - timedelta(days=1)
        etiqueta = "Ayer"
    elif periodo == "fin_fecha_semana":
        desde = hoy - timedelta(days=hoy.weekday())  # lunes
        hasta = desde + timedelta(days=6)             # domingo
        etiqueta = f"Esta semana ({desde.strftime('%d/%m')} – {hasta.strftime('%d/%m')})"
    elif periodo == "fin_fecha_mes":
        desde = hoy.replace(day=1)
        hasta = hoy
        etiqueta = hoy.strftime("%B %Y").capitalize()
    else:
        return

    # Consultar Notion ventas filtrado por rango de fecha
    if not NOTION_VENTAS_ID:
        await query.message.reply_text("No hay base de datos de ventas configurada.")
        return

    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Fecha", "date": {"on_or_after": desde.isoformat()}},
                {"property": "Fecha", "date": {"on_or_before": hasta.isoformat()}},
            ]
        },
        "page_size": 100
    }
    await query.message.reply_text(f"Calculando ganancias: {etiqueta}…")
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        await query.message.reply_text("Error al consultar Notion. Intenta de nuevo.")
        return

    resultados = r.json().get("results", [])
    if not resultados:
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Volver", callback_data="fin_porfecha")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
        ])
        await query.message.reply_text(
            f"📅 *{etiqueta}*\nSin ventas registradas en este período.",
            reply_markup=teclado, parse_mode="Markdown"
        )
        return

    ventas = []
    for page in resultados:
        props = page.get("properties", {})
        try:
            ganancia = props.get("Ganancia", {}).get("number") or 0
            cantidad = props.get("Cantidad", {}).get("number") or 0
            precio   = props.get("Precio Venta", {}).get("number") or 0
            costo_u_v= props.get("Costo unitario", {}).get("number") or 0
            estado_sel = props.get("Estado", {}).get("select") or {}
            estado   = estado_sel.get("name", "Completado")
            prenda_r = props.get("Prenda", {}).get("rich_text", [])
            prenda   = prenda_r[0]["text"]["content"] if prenda_r else "Sin nombre"
            cliente_r = props.get("Cliente", {}).get("rich_text", [])
            cliente  = cliente_r[0]["text"]["content"] if cliente_r else ""
            # Ganancia Efectiva: pendientes no cuentan
            ganancia_efectiva = ganancia if estado != "Pendiente" else 0
            ventas.append({"prenda": prenda, "cantidad": cantidad,
                           "precio": precio, "ganancia": ganancia_efectiva,
                           "costo_u": costo_u_v, "cliente": cliente,
                           "estado": estado})
        except Exception:
            continue

    total_gan  = sum(v["ganancia"] for v in ventas)
    total_uds  = sum(v["cantidad"] for v in ventas)
    total_ing  = sum(v["ganancia"] + (v["costo_u"] * v["cantidad"]) for v in ventas if v["estado"] != "Pendiente")
    n_ventas   = len(ventas)
    pendientes = sum(1 for v in ventas if v["estado"] == "Pendiente")

    lineas = [
        f"📅 *Ganancias — {etiqueta}*\n",
        f"Ventas registradas: {n_ventas}",
        f"Unidades vendidas:  {total_uds} uds",
        f"Ingresos:           S/{total_ing:.0f}",
        f"Ganancia neta:      S/{total_gan:.0f}",
    ]
    if pendientes > 0:
        lineas.append(f"⏳ Pendientes:       {pendientes}")
    lineas += ["\nDetalle:"]
    for v in ventas:
        cli = f" → {v['cliente']}" if v["cliente"] else ""
        pend = " ⏳" if v["estado"] == "Pendiente" else ""
        lineas.append(f"  • {v['prenda']} x{v['cantidad']}  +S/{v['ganancia']:.0f}{cli}{pend}")

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver", callback_data="fin_porfecha")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    await query.message.reply_text(
        "\n".join(lineas), reply_markup=teclado, parse_mode="Markdown"
    )

async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "📊 Calculando resumen financiero...")
    prendas = await fetch_inventario_completo()
    if prendas is None:
        await _reply(update, "Error al consultar Notion.")
        return
    if not prendas:
        await _reply(update, "El inventario está vacío.")
        return

    # Datos del inventario (stock, inversión, potencial)
    total_prendas    = len(prendas)
    disponibles      = sum(1 for p in prendas if p["estado"] == "Disponible")
    limitadas        = sum(1 for p in prendas if p["estado"] == "Stock limitado")
    agotadas         = sum(1 for p in prendas if p["estado"] == "Agotado")
    inversion_rest   = sum(p["inversion_rest"] for p in prendas)
    valor_stock_rest = sum(p["valor_restante"] for p in prendas)
    ganancia_pot     = sum(p["stock"] * p["ganancia_u"] for p in prendas)
    total_invertido  = sum(p["costo"] for p in prendas)
    stock_bajo       = [p for p in prendas if 0 < p["stock"] <= 3]

    # Datos REALES de ventas (consulta BD Ventas)
    v = await fetch_resumen_ventas_real()

    # ROI real (ganancia neta / inversión total)
    roi = round(v["ganancia"] / total_invertido * 100, 1) if total_invertido > 0 else 0
    # % inversión recuperada
    recuperado_pct = round(v["ingresos"] / total_invertido * 100, 1) if total_invertido > 0 else 0

    lineas = [
        "📊 *Resumen Financiero — Maricuchis Store*\n",

        "━━━ 📦 INVENTARIO ━━━",
        f"Prendas: {total_prendas} ({disponibles} disponibles, {limitadas} limitado, {agotadas} agotadas)\n",

        "━━━ 💵 VENTAS REALES ━━━",
        f"Total de ventas: {v['num_ventas']}",
        f"Unidades vendidas: {v['uds']} uds",
        f"Ingresos cobrados: S/{v['ingresos']:.0f}",
        f"Ganancia bruta: S/{v['ganancia']:.0f}",
        f"Descuentos otorgados: -S/{v['descuentos']:.0f}",
    ]
    if v["pendientes"] > 0:
        lineas.append(f"⏳ Ventas pendientes: {v['pendientes']}")
    
    lineas += [
        "",
        "━━━ 📅 VENTAS POR PERÍODO ━━━",
        f"Hoy:     S/{v['hoy_ing']:.0f} ingreso → S/{v['hoy_gan']:.0f} ganancia",
        f"Semana:  S/{v['semana_ing']:.0f} ingreso → S/{v['semana_gan']:.0f} ganancia",
        f"Mes:     S/{v['mes_ing']:.0f} ingreso → S/{v['mes_gan']:.0f} ganancia",
    ]

    if v["gastos"] > 0:
        lineas += [
            "",
            "━━━ 💸 GASTOS ━━━",
            f"Total gastos: S/{v['gastos']:.0f}",
            f"🟢 Ganancia NETA (ganancia - gastos): S/{v['ganancia_neta']:.0f}",
        ]

    lineas += [
        "",
        "━━━ 📈 RENDIMIENTO ━━━",
        f"Total invertido: S/{total_invertido:.0f}",
        f"Recuperado: S/{v['ingresos']:.0f} ({recuperado_pct}%)",
        f"ROI: {roi}%",
    ]

    lineas += [
        "",
        "━━━ 🏪 STOCK RESTANTE ━━━",
        f"Inversión en stock: S/{inversion_rest:.0f}",
        f"Valor de venta: S/{valor_stock_rest:.0f}",
        f"Ganancia potencial: S/{ganancia_pot:.0f}",
    ]

    if v["top_prenda"]:
        lineas += [
            "",
            "━━━ 🏆 MÁS VENDIDA ━━━",
            f"{v['top_prenda']} — {v['top_prenda_uds']} uds vendidas",
        ]

    if stock_bajo:
        lineas += ["", "⚡ STOCK BAJO"]
        for p in stock_bajo:
            lineas.append(f"  • {p['nombre']}: {p['stock']} uds")

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver", callback_data="menu_ganancias")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    msg = update.message or update.callback_query.message
    await msg.reply_text("\n".join(lineas), reply_markup=teclado, parse_mode="Markdown")

async def cmd_por_margen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Calculando ranking por margen...")
    prendas = await fetch_inventario_completo()
    if not prendas:
        await _reply(update, "Inventario vacío o error.")
        return
    ranking = sorted(prendas, key=lambda p: p["margen"], reverse=True)
    lineas  = [f"Ranking por margen de ganancia ({len(ranking)} prendas)\n"]
    for i, p in enumerate(ranking, 1):
        lineas.append(
            f"{i:2}. {p['nombre']}\n"
            f"    Margen: {p['margen']}% | Ganancia/ud: S/{p['ganancia_u']:.0f} | Stock: {p['stock']}"
        )
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver", callback_data="menu_ganancias")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    msg = update.message or update.callback_query.message
    await msg.reply_text("\n".join(lineas), reply_markup=teclado)

async def cmd_por_tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _reply(update, "Agrupando por tienda...")
    prendas = await fetch_inventario_completo()
    if not prendas:
        await _reply(update, "Inventario vacío o error.")
        return
    tiendas = {}
    for p in prendas:
        t = p["tienda"] or "Sin tienda"
        if t not in tiendas:
            tiendas[t] = {"prendas": [], "inversion": 0, "ganancia": 0}
        tiendas[t]["prendas"].append(p["nombre"])
        tiendas[t]["inversion"] += p["costo"]
        tiendas[t]["ganancia"]  += p["ganancia_real"]
    lineas = ["Resumen por tienda\n"]
    for t, datos in sorted(tiendas.items()):
        lineas.append(f"📍 {t}")
        lineas.append(f"   Prendas:   {len(datos['prendas'])}")
        lineas.append(f"   Inversión: S/{datos['inversion']:.0f}")
        lineas.append(f"   Ganancia:  S/{datos['ganancia']:.0f}\n")
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Volver", callback_data="menu_ganancias")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="menu_inicio")],
    ])
    msg = update.message or update.callback_query.message
    await msg.reply_text("\n".join(lineas), reply_markup=teclado)

async def cmd_grafico_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text("Generando gráfico de stock… ⏳")
    buf = await generar_grafico_stock()
    if not buf:
        await msg.reply_text("No hay prendas en el inventario aún.")
        return
    await msg.reply_photo(photo=buf, caption="📦 Stock actual por prenda\nVerde=Disponible | Amarillo=Stock bajo | Rojo=Agotado")


# ============================================================
# AUDITORÍA DE GANANCIAS
# ============================================================
async def auditar_y_corregir_ganancias(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_auditar_y_corregir_ganancias, *args, **kwargs))

def _sync_auditar_y_corregir_ganancias() -> dict:
    """Revisa todos los registros de ventas y corrige Ganancia si está mal calculada."""
    if not NOTION_VENTAS_ID:
        return {"error": "No hay BD de ventas configurada."}
    url     = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {"page_size": 100}
    todos   = []
    # Paginar por si hay más de 100 registros
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if r.status_code != 200:
            return {"error": f"Error Notion {r.status_code}"}
        data = r.json()
        todos += data.get("results", [])
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    revisados  = 0
    corregidos = 0
    errores    = 0
    detalles   = []

    for page in todos:
        try:
            props    = page.get("properties", {})
            page_id  = page["id"]
            cantidad  = props.get("Cantidad",       {}).get("number") or 0
            precio    = props.get("Precio Venta",    {}).get("number") or 0
            costo_u   = props.get("Costo unitario", {}).get("number") or 0
            descuento = props.get("Descuento",      {}).get("number") or 0
            ganancia_actual = props.get("Ganancia", {}).get("number")
            prenda_r = props.get("Prenda", {}).get("rich_text", [])
            prenda   = prenda_r[0]["text"]["content"] if prenda_r else "?"

            if cantidad == 0 or precio == 0:
                continue  # sin datos suficientes, saltar

            ganancia_correcta = round((precio - descuento - costo_u) * cantidad, 2)
            revisados += 1

            # Solo corrige si la ganancia guardada es mayor a la calculada (bug, no descuento)
            if ganancia_actual is None or (ganancia_actual - ganancia_correcta) > 0.01:
                # Corregir en Notion
                patch = requests.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=NOTION_HEADERS,
                    json={"properties": {"Ganancia": {"number": ganancia_correcta}}}
                , timeout=15)
                if patch.status_code == 200:
                    corregidos += 1
                    detalles.append({
                        "prenda": prenda,
                        "antes": ganancia_actual,
                        "despues": ganancia_correcta,
                        "cantidad": cantidad,
                        "precio": precio,
                        "costo_u": costo_u,
                    })
                else:
                    errores += 1
        except Exception:
            errores += 1
            continue

    return {
        "revisados": revisados,
        "corregidos": corregidos,
        "errores": errores,
        "detalles": detalles,
    }

async def cmd_auditar_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /auditarventas — revisa y corrige ganancias mal calculadas."""
    msg = update.message or update.callback_query.message
    await msg.reply_text("🔍 Auditando registros de ventas... puede tomar unos segundos.")
    resultado = await auditar_y_corregir_ganancias()

    if "error" in resultado:
        await msg.reply_text(f"❌ {resultado['error']}")
        return

    rev  = resultado["revisados"]
    cor  = resultado["corregidos"]
    err  = resultado["errores"]
    dets = resultado["detalles"]

    if cor == 0:
        await msg.reply_text(
            f"✅ Auditoría completa\n\n"
            f"Registros revisados: {rev}\n"
            f"Correcciones: ninguna necesaria\n"
            f"Todo está bien calculado. 👍"
        )
        return

    lineas = [
        f"✅ Auditoría completa\n",
        f"Registros revisados: {rev}",
        f"Corregidos:          {cor}",
        f"Errores:             {err}\n",
        "─── Detalle de correcciones ───",
    ]
    for d in dets:
        antes   = f"S/{d['antes']:.0f}" if d["antes"] is not None else "vacío"
        lineas.append(
            f"• {d['prenda']}\n"
            f"  {d['cantidad']} uds × (S/{d['precio']:.0f} - S/{d['costo_u']:.0f}) "
            f"= S/{d['despues']:.0f}  (antes: {antes})"
        )
    if err > 0:
        lineas.append(f"\n⚠️ {err} registro(s) no se pudieron corregir.")

    await msg.reply_text("\n".join(lineas))


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
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
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
    page_id = query.data.replace("menu_verf:", "")
    foto_url = await obtener_foto_url(page_id)
    if foto_url:
        await query.message.reply_photo(photo=foto_url)
    else:
        await query.message.reply_text("Esta prenda no tiene foto registrada.")

async def cmd_nueva_prenda_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = teclado_menu_nueva_prenda()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📸 *Registrar prenda — ¿Qué deseas hacer?*", reply_markup=teclado, parse_mode="Markdown")
    else:
        await update.message.reply_text("📸 *Registrar prenda — ¿Qué deseas hacer?*", reply_markup=teclado, parse_mode="Markdown")

# ============================================================
# CONVERSATION HANDLER — BOLETOS
# ============================================================
from config import BOLETO_CLIENTE, BOLETO_CANTIDAD, BOLETO_ASUNTO
from notion_api import crear_boleto_notion

async def cmd_boletos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clientes_prev = await obtener_clientes_previos()
    context.user_data["clientes_previos"] = clientes_prev
    teclado = teclado_lista_clientes(clientes_prev, 0)
    await _reply(update, "🎫 Asignar Boletos\n\n¿A qué clienta deseas asignarle o restarle boletos?", reply_markup=teclado)
    return BOLETO_CLIENTE

async def boleto_recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        data = query.data
        if data.startswith("page_cliente:"):
            pagina = int(data.split(":")[1])
            clientes_prev = context.user_data.get("clientes_previos", [])
            teclado = teclado_lista_clientes(clientes_prev, pagina)
            await query.edit_message_reply_markup(reply_markup=teclado)
            return BOLETO_CLIENTE
        if data == "cliente_sin_nombre":
            await query.message.reply_text("No se puede asignar boletos a un cliente anónimo. Escribe el nombre:")
            return BOLETO_CLIENTE
        elif data == "cliente_nueva":
            await query.message.reply_text("✏️ Escribe el nombre de la nueva clienta:")
            return BOLETO_CLIENTE
        elif data.startswith("cliente_prev_"):
            context.user_data["boleto_cliente"] = data[len("cliente_prev_"):]
    else:
        context.user_data["boleto_cliente"] = update.message.text.strip()
    
    await _reply(update, f"👤 Clienta: {context.user_data['boleto_cliente']}\n\nEscribe el número de boletos a asignar (ej. 2) o restar (ej. -1):")
    return BOLETO_CANTIDAD

async def boleto_recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        boletos = int(update.message.text.strip())
        if boletos == 0: raise ValueError
    except ValueError:
        await update.message.reply_text("Ingresa un número válido distinto de 0 (ejemplo: 2 o -1):")
        return BOLETO_CANTIDAD
        
    context.user_data["boleto_cantidad"] = boletos
    await update.message.reply_text("Escribe el asunto o motivo (ej. Compartió historia, Compra de saldo):")
    return BOLETO_ASUNTO

async def boleto_recibir_asunto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asunto = update.message.text.strip()
    cliente = context.user_data["boleto_cliente"]
    boletos = context.user_data["boleto_cantidad"]
    
    await update.message.reply_text("Guardando...")
    ok = await crear_boleto_notion(cliente=cliente, boletos=boletos, asunto=asunto)
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    teclado_post = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Registrar otro boleto", callback_data="menu_boletos")],
        [InlineKeyboardButton("🏠 Volver al menú",        callback_data="menu_inicio")],
    ])
    
    if ok:
        await update.message.reply_text(f"✅ ¡Se registraron {boletos} boletos para {cliente}!\nAsunto: {asunto}", reply_markup=teclado_post)
    else:
        await update.message.reply_text("❌ Hubo un error al guardar en Notion.", reply_markup=teclado_post)
        
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# GESTIÓN DE AUDIOS (TRANSCRIPCIÓN GROQ WHISPER)
# ============================================================
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎙️ Escuchando...")
    
    try:
        # 1. Obtener el archivo de voz desde Telegram
        file_id = update.message.voice.file_id
        new_file = await context.bot.get_file(file_id)
        
        # 2. Descargarlo en memoria
        import io
        file_bytes = await new_file.download_as_bytearray()
        
        # 3. Transcribirlo
        from audio_api import transcribir_audio_groq
        texto = await transcribir_audio_groq(bytes(file_bytes))
        
        if not texto or texto.startswith("[Error"):
            await msg.edit_text(f"❌ No pude entender el audio.\n{texto}")
            return
        
        # 4. Mostrar transcripción brevemente y procesar con IA
        await msg.edit_text(f"🎙️ _\"{texto}\"_\n\n🧠 Procesando...", parse_mode="Markdown")
        
        # 5. Pasar al cerebro IA
        from handlers_ia import handle_ia_message
        await handle_ia_message(update, context, texto)
        
        # Borrar el mensaje de procesamiento si IA ya respondió
        try:
            await msg.delete()
        except:
            pass
            
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error procesando audio: {e}")
        await msg.edit_text("❌ Ocurrió un error al procesar el audio.")
