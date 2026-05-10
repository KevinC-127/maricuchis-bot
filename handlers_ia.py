"""
handlers_ia.py — Handler IA para mensajes libres (texto, audio, imagen)
Conecta el cerebro IA (ia_brain.py) con los handlers de Telegram.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import logger
from ia_brain import (
    get_sesion, crear_sesion, actualizar_sesion, cerrar_sesion,
    clasificar_intencion, extraer_datos, completar_datos,
    campos_faltantes_prenda, campos_faltantes_venta,
    formatear_resumen_prenda, formatear_resumen_venta, llamar_llm,
)

# Estado de conversación para confirmaciones IA
IA_CONFIRMAR = 500

# ============================================================
# CARGA DE CONTEXTO DESDE NOTION
# ============================================================
async def _cargar_contexto():
    """Carga clientes, prendas y tiendas desde Notion."""
    from notion_api import obtener_clientes_previos, buscar_prendas_notion
    import asyncio

    clientes = await obtener_clientes_previos()

    # Cargar inventario completo (top_inventario del dashboard)
    from dashboard import _sync_get_stats
    stats = await asyncio.to_thread(_sync_get_stats)
    prendas = stats.get("top_inventario", [])
    
    tiendas_set = set()
    for p in prendas:
        if p.get("tienda"):
            tiendas_set.add(p["tienda"])
    tiendas = sorted(tiendas_set) if tiendas_set else ["Gamarra", "Ambulante"]

    return clientes, prendas, tiendas


# ============================================================
# HANDLER PRINCIPAL — Procesa texto/audio libre
# ============================================================
async def handle_ia_message(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str = None):
    """Procesa un mensaje libre (texto o audio transcrito) con IA."""
    chat_id = update.effective_chat.id
    mensaje = texto or update.message.text or ""
    
    if not mensaje.strip():
        return
    
    # 1. ¿Hay sesión activa?
    sesion = get_sesion(chat_id)
    if sesion:
        await _continuar_sesion(update, context, sesion, mensaje)
        return

    # 2. Clasificar intención
    msg = await update.message.reply_text("🧠 Procesando...")
    resultado = await clasificar_intencion(mensaje)
    
    if resultado.get("error"):
        await msg.edit_text("❌ Error al procesar. Intenta de nuevo o usa los comandos /menu")
        return

    intencion = resultado.get("intencion", "no_entendido")
    datos_ini = resultado.get("datos", {})
    logger.info(f"IA clasificó: {intencion} | datos: {datos_ini}")

    # 3. Ejecutar según intención
    if intencion == "cancelar":
        cerrar_sesion(chat_id)
        await msg.edit_text("❌ No hay operación activa para cancelar.")
    
    elif intencion == "sin_sentido":
        await msg.edit_text("🤔 No entendí eso. ¿Qué necesitas?\n\nPuedes decirme cosas como:\n• _\"Registra chompa azul, costo 15, precio 25, 12 uds, de Gamarra\"_\n• _\"Victoria compró 2 chompas\"_\n• _\"Cuánto stock tiene polo cruzado\"_\n• _\"Muéstrame la foto de capa\"_", parse_mode="Markdown")

    elif intencion == "no_entendido":
        await msg.edit_text("🤔 ¿Qué necesitas hacer?\n\n• 📦 Agregar prenda nueva\n• 🛒 Registrar una venta\n• 🔍 Consultar stock/precio\n• 📸 Ver foto de prenda\n• ⏳ Actualizar un pendiente")

    elif intencion == "registrar_venta":
        await _iniciar_venta(update, context, msg, mensaje)

    elif intencion == "agregar_prenda":
        await _iniciar_prenda(update, context, msg, mensaje)

    elif intencion == "actualizar_pendiente":
        await _iniciar_pendiente(update, context, msg, mensaje)

    elif intencion == "ver_foto":
        await _iniciar_ver_foto(update, context, msg, mensaje)

    elif intencion.startswith("consultar_"):
        await _procesar_consulta(update, context, msg, mensaje, intencion)

    else:
        await msg.edit_text("🤔 No entendí. Intenta ser más específico o usa /menu")


# ============================================================
# FLUJO: REGISTRAR VENTA
# ============================================================
async def _iniciar_venta(update, context, msg, mensaje):
    chat_id = update.effective_chat.id
    await msg.edit_text("🛒 Procesando venta...")
    
    clientes, prendas, tiendas = await _cargar_contexto()
    datos = await extraer_datos("registrar_venta", mensaje, clientes, prendas, tiendas)
    
    if datos.get("error"):
        await msg.edit_text("❌ Error al interpretar. Intenta de nuevo.")
        return

    # === VALIDAR ITEMS CONTRA INVENTARIO REAL ===
    items_validados = []
    items_problemas = []
    
    for item in datos.get("items", []):
        prenda_nom = item.get("prenda", "")
        # Buscar coincidencias en inventario local
        matches = [p for p in prendas if prenda_nom.lower() in p["nombre"].lower() or p["nombre"].lower() in prenda_nom.lower()]
        
        if not matches:
            # Búsqueda más flexible por palabras
            palabras = prenda_nom.lower().split()
            matches = [p for p in prendas if any(w in p["nombre"].lower() for w in palabras if len(w) > 2)]
        
        if len(matches) == 1:
            # Coincidencia única → validado
            p = matches[0]
            item["prenda"] = p["nombre"]
            item["prenda_exacta"] = True
            item["_inv"] = p  # referencia interna
            if not item.get("precio"):
                item["precio"] = p.get("precio", 0)
            items_validados.append(item)
        elif len(matches) > 1:
            # Múltiples coincidencias → pedir aclaración
            sugerencias = [p["nombre"] for p in matches[:5]]
            items_problemas.append({"original": prenda_nom, "sugerencias": sugerencias, "item": item})
        else:
            # Sin coincidencia
            items_problemas.append({"original": prenda_nom, "sugerencias": [], "item": item})
    
    # === DISTRIBUIR PRECIO TOTAL SI LO DIERON ===
    precio_total_dado = datos.get("precio_total_dado")
    if precio_total_dado and items_validados and not items_problemas:
        # Calcular suma de precios de lista
        suma_lista = sum(it.get("_inv", {}).get("precio", 0) * it.get("cantidad", 1) for it in items_validados)
        if suma_lista == precio_total_dado:
            # El total coincide con precios de lista → usar precios de lista
            for it in items_validados:
                it["precio"] = it.get("_inv", {}).get("precio", it.get("precio", 0))
        else:
            # Total diferente → hay descuento, distribuir proporcionalmente
            for it in items_validados:
                precio_lista = it.get("_inv", {}).get("precio", 0)
                cant = it.get("cantidad", 1)
                proporcion = (precio_lista * cant) / suma_lista if suma_lista > 0 else 0
                it["precio"] = round((precio_total_dado * proporcion) / cant, 1) if cant > 0 else 0
    
    # Limpiar referencia interna
    for it in items_validados:
        it.pop("_inv", None)
    
    datos["items"] = items_validados
    
    # === SI HAY PROBLEMAS, INFORMAR ===
    if items_problemas:
        prob_txt = ""
        for prob in items_problemas:
            if prob["sugerencias"]:
                opts = "\n".join(f"  • {s}" for s in prob["sugerencias"])
                prob_txt += f"\n⚠️ *\"{prob['original']}\"* — ¿Te refieres a alguna de estas?\n{opts}\n"
            else:
                prob_txt += f"\n❌ *\"{prob['original']}\"* — No encontré nada similar en el inventario.\n"
        
        # Guardar sesión con items validados + pendientes
        datos["_items_pendientes"] = items_problemas
        crear_sesion(chat_id, "registrar_venta", datos)
        
        resumen = _resumen_parcial_venta(datos) if items_validados else ""
        extra = f"\n{resumen}\n" if resumen else ""
        await msg.edit_text(f"🛒 Venta parcial:{extra}\n{prob_txt}\nEscribe el nombre correcto de la(s) prenda(s) faltantes.", parse_mode="Markdown")
        return

    # === VALIDAR CLIENTE ===
    cliente_raw = datos.get("cliente", "")
    if cliente_raw and not datos.get("cliente_exacto", False):
        # Buscar coincidencias en la lista real
        cliente_lower = cliente_raw.lower()
        coincidencias = [c for c in clientes if cliente_lower in c.lower() or any(w in c.lower() for w in cliente_lower.split() if len(w) > 2)]
        
        candidatos_llm = datos.get("candidatos", [])
        if candidatos_llm:
            coincidencias = list(set(coincidencias + candidatos_llm))
        
        if len(coincidencias) == 1:
            datos["cliente"] = coincidencias[0]
            datos["cliente_exacto"] = True
        elif len(coincidencias) > 1:
            opts = "\n".join(f"  • {c}" for c in coincidencias[:6])
            datos["_cliente_pendiente"] = True
            crear_sesion(chat_id, "registrar_venta", datos)
            resumen = _resumen_parcial_venta(datos)
            await msg.edit_text(f"✉️ Entendí \"{cliente_raw}\". \u00bfTe refieres a alguna de estas clientas?\n{opts}\n\n_Escribe el nombre correcto o di 'nueva' para registrar una nueva clienta_", parse_mode="Markdown")
            return
        else:
            datos["_cliente_pendiente"] = True
            crear_sesion(chat_id, "registrar_venta", datos)
            await msg.edit_text(f"\u2753 No encontré \"{cliente_raw}\" en las clientas registradas.\n\n\u00bfQuieres registrarla como nueva clienta o corregir el nombre?", parse_mode="Markdown")
            return

    # Crear sesión con items validados
    crear_sesion(chat_id, "registrar_venta", datos)
    faltantes = campos_faltantes_venta(datos)
    
    if faltantes:
        faltantes_txt = _formatear_faltantes_venta(faltantes)
        resumen_parcial = _resumen_parcial_venta(datos)
        await msg.edit_text(f"✏️ Entendí:\n{resumen_parcial}\n\n{faltantes_txt}", parse_mode="Markdown")
    else:
        resumen = formatear_resumen_venta(datos)
        kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
               InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
        await msg.edit_text(f"{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


# ============================================================
# FLUJO: AGREGAR PRENDA
# ============================================================
async def _iniciar_prenda(update, context, msg, mensaje):
    chat_id = update.effective_chat.id
    await msg.edit_text("📦 Procesando prenda...")
    
    clientes, prendas, tiendas = await _cargar_contexto()
    datos = await extraer_datos("agregar_prenda", mensaje, clientes, prendas, tiendas)
    
    if datos.get("error"):
        await msg.edit_text("❌ Error al interpretar. Intenta de nuevo.")
        return
    
    crear_sesion(chat_id, "agregar_prenda", datos)
    faltantes = campos_faltantes_prenda(datos)

    if faltantes:
        faltantes_txt = _formatear_faltantes_prenda(faltantes)
        resumen_parcial = _resumen_parcial_prenda(datos)
        await msg.edit_text(f"✏️ Entendí:\n{resumen_parcial}\n\n❓ Me falta:\n{faltantes_txt}", parse_mode="Markdown")
    else:
        resumen = formatear_resumen_prenda(datos)
        kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
               InlineKeyboardButton("📸 Agregar foto", callback_data="ia_foto"),
               InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
        await msg.edit_text(f"{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


# ============================================================
# FLUJO: ACTUALIZAR PENDIENTE
# ============================================================
async def _iniciar_pendiente(update, context, msg, mensaje):
    chat_id = update.effective_chat.id
    await msg.edit_text("⏳ Buscando pendientes...")
    
    clientes, prendas, tiendas = await _cargar_contexto()
    datos = await extraer_datos("actualizar_pendiente", mensaje, clientes, prendas, tiendas)
    
    if datos.get("error") or not datos.get("cliente"):
        await msg.edit_text("❓ ¿De qué clienta quieres actualizar el pendiente?")
        crear_sesion(chat_id, "actualizar_pendiente", {})
        return
    
    # Buscar pendientes de esa clienta
    from notion_api import fetch_ventas_pendientes
    pendientes = await fetch_ventas_pendientes()
    cliente_nom = datos["cliente"]
    
    pend_cliente = [v for v in pendientes if v.get("cliente", "").lower() == cliente_nom.lower()]
    
    if not pend_cliente:
        await msg.edit_text(f"✅ {cliente_nom} no tiene pendientes registrados.")
        cerrar_sesion(chat_id)
        return
    
    items_txt = "\n".join(f"  {i+1}. {v.get('prenda','')} × {v.get('cantidad',1)} (S/{v.get('precio',0)*v.get('cantidad',1)})" for i, v in enumerate(pend_cliente))
    
    crear_sesion(chat_id, "confirmar_pendiente", {"cliente": cliente_nom, "pendientes": pend_cliente})
    kb = [[InlineKeyboardButton("✅ Completar todas", callback_data="ia_pend_all"),
           InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
    await msg.edit_text(f"📋 Pendientes de *{cliente_nom}*:\n{items_txt}\n\n¿Completar?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


# ============================================================
# FLUJO: CONSULTAS
# ============================================================
async def _procesar_consulta(update, context, msg, mensaje, intencion):
    clientes, prendas, tiendas = await _cargar_contexto()
    datos = await extraer_datos(intencion, mensaje, clientes, prendas, tiendas)
    
    prenda_buscar = datos.get("prenda", "")
    
    if intencion in ("consultar_stock", "consultar_precio"):
        if not prenda_buscar:
            await msg.edit_text("❓ ¿De qué prenda quieres saber? Dime el nombre.")
            return
        
        # Buscar en inventario
        matches = [p for p in prendas if prenda_buscar.lower() in p["nombre"].lower()]
        if not matches:
            # Búsqueda flexible por palabras
            palabras = prenda_buscar.lower().split()
            matches = [p for p in prendas if any(w in p["nombre"].lower() for w in palabras if len(w) > 2)]
        
        if not matches:
            await msg.edit_text(f"❌ No encontré \"{prenda_buscar}\" en el inventario.")
            return
        
        if len(matches) > 8:
            matches = matches[:8]
        
        header = f"🔍 *{len(matches)} resultado{'s' if len(matches)>1 else ''} para \"{prenda_buscar}\":*\n\n"
        resp = header
        for p in matches:
            estado = p.get("estado", "")
            resp += f"👗 *{p['nombre']}*\n  📦 Stock: {p.get('stock',0)} uds | {estado}\n  💰 Precio: S/{p.get('precio',0)} | Costo u.: S/{p.get('costo_u',0)}\n\n"
        await msg.edit_text(resp.strip(), parse_mode="Markdown")
    
    elif intencion == "consultar_pendientes":
        from notion_api import fetch_ventas_pendientes
        pendientes = await fetch_ventas_pendientes()
        if not pendientes:
            await msg.edit_text("✅ No hay ventas pendientes.")
            return
        total = sum(v.get("precio", 0) * v.get("cantidad", 1) for v in pendientes)
        resp = f"📋 *{len(pendientes)} ventas pendientes* (Total: S/{total})\n\n"
        for v in pendientes[:10]:
            resp += f"• {v.get('cliente','?')} — {v.get('prenda','')} × {v.get('cantidad',1)}\n"
        await msg.edit_text(resp.strip(), parse_mode="Markdown")
    
    else:
        # Consulta genérica - intentar responder si hay prenda
        if prenda_buscar:
            matches = [p for p in prendas if prenda_buscar.lower() in p["nombre"].lower()]
            if matches:
                resp = f"🔍 *Resultados para \"{prenda_buscar}\":*\n\n"
                for p in matches[:8]:
                    resp += f"👗 *{p['nombre']}*\n  📦 Stock: {p.get('stock',0)} | 💰 S/{p.get('precio',0)}\n\n"
                await msg.edit_text(resp.strip(), parse_mode="Markdown")
                return
        await msg.edit_text("🔍 No pude resolver la consulta. Intenta ser más específico o usa /menu")


# ============================================================
# CONTINUAR SESIÓN ACTIVA (datos parciales)
# ============================================================
async def _continuar_sesion(update, context, sesion, mensaje):
    chat_id = update.effective_chat.id
    tipo = sesion["tipo"]
    datos = sesion["datos"]
    
    # === DESAMBIGUACIÓN UNIVERSAL ===
    # Si hay candidatos pendientes, resolver primero
    if datos.get("_disambiguation"):
        disamb = datos["_disambiguation"]
        candidatos = disamb["candidatos"]
        resultado = _resolver_disambiguation(mensaje, candidatos)
        
        if resultado is None:
            # No se resolvió, volver a mostrar
            opts = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(candidatos))
            await update.message.reply_text(f"🤔 No entendí. Elige una opción:\n{opts}\n\n_Escribe el número, el nombre, o 'ninguna'_", parse_mode="Markdown")
            return
        
        if resultado == "__ninguna__":
            datos.pop("_disambiguation", None)
            cerrar_sesion(chat_id)
            await update.message.reply_text("❌ Operación cancelada.")
            return
        
        # Aplicar resultado
        campo = disamb["campo"]
        datos[campo] = resultado
        datos.pop("_disambiguation", None)
        sesion["datos"] = datos
        sesion["timestamp"] = __import__("time").time()
        
        # Continuar según tipo
        if tipo == "ver_foto":
            await _mostrar_foto_prenda(update, context, resultado, datos.get("_prendas_inv", []))
            cerrar_sesion(chat_id)
            return
        elif tipo == "consultar_detalle":
            prendas_inv = datos.get("_prendas_inv", [])
            match = [p for p in prendas_inv if p["nombre"] == resultado]
            if match:
                p = match[0]
                await update.message.reply_text(f"👗 *{p['nombre']}*\n📦 Stock: {p.get('stock',0)} uds | {p.get('estado','')}\n💰 Precio: S/{p.get('precio',0)} | Costo u.: S/{p.get('costo_u',0)}", parse_mode="Markdown")
            cerrar_sesion(chat_id)
            return
    
    # Cargar contexto
    clientes, prendas, tiendas = await _cargar_contexto()
    
    if tipo == "agregar_prenda":
        faltantes = campos_faltantes_prenda(datos)
        if not faltantes:
            return
        
        nuevos = await completar_datos("prenda nueva", mensaje, datos, faltantes, tiendas=tiendas)
        
        if nuevos.get("sin_sentido"):
            faltantes_txt = _formatear_faltantes_prenda(faltantes)
            await update.message.reply_text(f"🤔 No entendí. Aún necesito:\n{faltantes_txt}")
            return
        
        # Merge datos
        for k, v in nuevos.items():
            if v is not None and k != "sin_sentido":
                datos[k] = v
        sesion["datos"] = datos
        sesion["timestamp"] = __import__("time").time()
        
        faltantes = campos_faltantes_prenda(datos)
        if faltantes:
            faltantes_txt = _formatear_faltantes_prenda(faltantes)
            resumen = _resumen_parcial_prenda(datos)
            await update.message.reply_text(f"✏️ Actualizado:\n{resumen}\n\n❓ Aún falta:\n{faltantes_txt}", parse_mode="Markdown")
        else:
            resumen = formatear_resumen_prenda(datos)
            kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
                   InlineKeyboardButton("📸 Agregar foto", callback_data="ia_foto"),
                   InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
            await update.message.reply_text(f"{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    elif tipo == "registrar_venta":
        # ¿Estamos esperando resolución de cliente?
        if datos.get("_cliente_pendiente"):
            msg_lower = mensaje.strip().lower()
            if msg_lower == "nueva":
                # Registrar como nueva clienta
                datos["cliente_exacto"] = True
                datos.pop("_cliente_pendiente", None)
            else:
                # Buscar coincidencia exacta con lo que escribió
                match = [c for c in clientes if msg_lower in c.lower() or c.lower() in msg_lower]
                if len(match) == 1:
                    datos["cliente"] = match[0]
                    datos["cliente_exacto"] = True
                    datos.pop("_cliente_pendiente", None)
                elif len(match) > 1:
                    opts = "\n".join(f"  • {c}" for c in match[:6])
                    await update.message.reply_text(f"Aún hay varias opciones:\n{opts}\n\n_Escribe el nombre exacto_", parse_mode="Markdown")
                    return
                else:
                    datos["cliente"] = mensaje.strip()
                    datos["cliente_exacto"] = True
                    datos.pop("_cliente_pendiente", None)
            
            sesion["datos"] = datos
            sesion["timestamp"] = __import__("time").time()
        
        faltantes = campos_faltantes_venta(datos)
        if not faltantes and not datos.get("_cliente_pendiente"):
            resumen = formatear_resumen_venta(datos)
            kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
                   InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
            await update.message.reply_text(f"{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            return
        
        if not faltantes:
            return
        
        nuevos = await completar_datos("venta", mensaje, datos, faltantes, clientes=clientes, prendas=prendas)
        
        if nuevos.get("sin_sentido"):
            faltantes_txt = _formatear_faltantes_venta(faltantes)
            await update.message.reply_text(f"🤔 No entendí. Aún necesito:\n{faltantes_txt}")
            return
        
        for k, v in nuevos.items():
            if v is not None and k != "sin_sentido":
                datos[k] = v
        sesion["datos"] = datos
        sesion["timestamp"] = __import__("time").time()
        
        faltantes = campos_faltantes_venta(datos)
        if faltantes:
            faltantes_txt = _formatear_faltantes_venta(faltantes)
            resumen = _resumen_parcial_venta(datos)
            await update.message.reply_text(f"✏️ Actualizado:\n{resumen}\n\n{faltantes_txt}", parse_mode="Markdown")
        else:
            resumen = formatear_resumen_venta(datos)
            kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
                   InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
            await update.message.reply_text(f"{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    
    elif tipo == "actualizar_pendiente":
        nuevos = await completar_datos("pendiente", mensaje, datos, ["cliente"], clientes=clientes)
        if nuevos.get("cliente"):
            datos["cliente"] = nuevos["cliente"]
            msg = await update.message.reply_text("⏳ Buscando...")
            await _iniciar_pendiente(update, context, msg, f"pendientes de {datos['cliente']}")
        else:
            await update.message.reply_text("❓ ¿De qué clienta quieres actualizar el pendiente?")


# ============================================================
# HANDLER DE IMAGEN (sin contexto de ConversationHandler)
# ============================================================
async def handle_ia_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja fotos enviadas sin caption fuera de un ConversationHandler."""
    chat_id = update.effective_chat.id
    sesion = get_sesion(chat_id)
    
    # Subir foto a imgbb
    from notion_api import subir_imagen
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_bytes = await file.download_as_bytearray()
    foto_url = await subir_imagen(bytes(file_bytes))
    
    if not foto_url:
        await update.message.reply_text("❌ Error al subir la foto.")
        return
    
    if sesion and sesion["tipo"] == "agregar_prenda":
        # Dentro de sesión de registro → asignar foto
        sesion["datos"]["foto_url"] = foto_url
        sesion["timestamp"] = __import__("time").time()
        
        faltantes = campos_faltantes_prenda(sesion["datos"])
        if faltantes:
            faltantes_txt = _formatear_faltantes_prenda(faltantes)
            await update.message.reply_text(f"📸 Foto guardada ✅\n\n❓ Aún falta:\n{faltantes_txt}", parse_mode="Markdown")
        else:
            resumen = formatear_resumen_prenda(sesion["datos"])
            kb = [[InlineKeyboardButton("✅ Confirmar", callback_data="ia_confirm"),
                   InlineKeyboardButton("❌ Cancelar", callback_data="ia_cancel")]]
            await update.message.reply_text(f"📸 Foto guardada ✅\n\n{resumen}\n\n¿Confirmas?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        # Sin sesión → preguntar qué hacer
        kb = [[InlineKeyboardButton("📦 Registrar nueva prenda", callback_data="ia_foto_nueva"),
               InlineKeyboardButton("🔄 Actualizar foto existente", callback_data="ia_foto_update")]]
        # Guardar foto temporalmente
        context.user_data["ia_foto_temp"] = foto_url
        await update.message.reply_text("📸 Recibí la imagen. ¿Qué quieres hacer?", reply_markup=InlineKeyboardMarkup(kb))


# ============================================================
# CALLBACKS DE CONFIRMACIÓN
# ============================================================
async def handle_ia_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de confirmación/cancelación IA."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data
    
    if data == "ia_cancel":
        cerrar_sesion(chat_id)
        await query.edit_message_text("❌ Operación cancelada.")
        return
    
    if data == "ia_foto":
        await query.edit_message_text("📸 Envíame la foto de la prenda.")
        return
    
    if data == "ia_foto_nueva":
        foto_url = context.user_data.pop("ia_foto_temp", None)
        crear_sesion(chat_id, "agregar_prenda", {"foto_url": foto_url})
        await query.edit_message_text("📸 Foto guardada. Ahora dime los datos:\n❓ _Nombre, costo, precio, stock y tienda_\n\n(Puedes decirlo todo junto o de a poco)", parse_mode="Markdown")
        return
    
    if data == "ia_foto_update":
        foto_url = context.user_data.pop("ia_foto_temp", None)
        context.user_data["ia_foto_update_url"] = foto_url
        await query.edit_message_text("🔄 ¿De qué prenda quieres actualizar la foto?\n(Escribe el nombre)")
        crear_sesion(chat_id, "foto_update", {"foto_url": foto_url})
        return
    
    sesion = get_sesion(chat_id)
    if not sesion:
        await query.edit_message_text("⚠️ La sesión expiró. Vuelve a intentar.")
        return
    
    if data == "ia_confirm":
        await _ejecutar_confirmacion(update, context, sesion)
    
    elif data == "ia_pend_all":
        await _ejecutar_pendientes(update, context, sesion)


# ============================================================
# EJECUCIÓN DE ACCIONES
# ============================================================
async def _ejecutar_confirmacion(update, context, sesion):
    """Ejecuta la acción confirmada (crear prenda o registrar venta)."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    datos = sesion["datos"]
    tipo = sesion["tipo"]
    
    if tipo == "agregar_prenda":
        from notion_api import crear_prenda_notion
        from datetime import datetime, timezone
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        exito = await crear_prenda_notion(
            nombre=datos["nombre"],
            costo=datos["costo"],
            precio=datos["precio"],
            stock=datos["stock"],
            foto_url=datos.get("foto_url"),
            tienda=datos.get("tienda"),
            fecha_compra=fecha,
        )
        if exito:
            await query.edit_message_text(f"✅ *Prenda registrada:* {datos['nombre']}\n📦 {datos['stock']} uds | S/{datos['precio']} c/u", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Error al registrar en Notion.")
    
    elif tipo == "registrar_venta":
        from notion_api import crear_venta_notion, actualizar_stock_notion, buscar_prendas_notion, crear_boleto_notion
        from dashboard import _ventas_completadas_procesadas
        from datetime import datetime, timezone
        
        fecha = datos.get("fecha") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        estado = datos.get("estado", "Completado")
        cliente = datos.get("cliente", "")
        boletos_total = 0
        resultados = []
        
        for item in datos.get("items", []):
            prenda_nom = item.get("prenda", "")
            cantidad = item.get("cantidad", 1)
            precio = item.get("precio", 0)
            
            # Buscar prenda en Notion
            matches = await buscar_prendas_notion(prenda_nom)
            if not matches:
                resultados.append(f"❌ {prenda_nom}: no encontrada")
                continue
            
            p = matches[0]
            costo_u = p.get("costo_u", 0)
            ganancia = (precio * cantidad) - (costo_u * cantidad)
            
            result = await crear_venta_notion(
                prenda_id=p["id"], cantidad=cantidad,
                precio_final=precio, ganancia=ganancia,
                fecha_iso=fecha, cliente=cliente,
                descuento=0, estado=estado
            )
            if result:
                if estado == "Completado" and isinstance(result, str):
                    _ventas_completadas_procesadas.add(result)
                await actualizar_stock_notion(p["id"], p["stock"] - cantidad)
                resultados.append(f"✅ {cantidad}× {p['nombre']}")
                boletos_total += cantidad
            else:
                resultados.append(f"❌ Error: {prenda_nom}")
        
        # Boletos
        boleto_txt = ""
        if boletos_total > 0 and estado == "Completado" and cliente:
            await crear_boleto_notion(cliente=cliente, boletos=boletos_total, asunto="Venta por IA", fecha_iso=fecha)
            boleto_txt = f"\n🎟️ {boletos_total} boletos asignados"
        
        res_txt = "\n".join(resultados)
        await query.edit_message_text(f"🎉 *Venta registrada*\n👤 {cliente}\n{res_txt}{boleto_txt}", parse_mode="Markdown")
    
    cerrar_sesion(chat_id)


async def _ejecutar_pendientes(update, context, sesion):
    """Completa todas las ventas pendientes de una clienta."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    datos = sesion["datos"]
    
    from notion_api import actualizar_estado_venta, crear_boleto_notion
    from dashboard import _ventas_completadas_procesadas
    
    pendientes = datos.get("pendientes", [])
    count = 0
    boletos = 0
    for v in pendientes:
        if await actualizar_estado_venta(v["id"], "Completado"):
            _ventas_completadas_procesadas.add(v["id"])
            count += 1
            boletos += v.get("cantidad", 1)
    
    cliente = datos.get("cliente", "")
    if boletos > 0 and cliente:
        await crear_boleto_notion(cliente=cliente, boletos=boletos, asunto="Cobro de pendientes (IA)")
    
    await query.edit_message_text(f"✅ *{count} pendientes completados* de {cliente}\n🎟️ {boletos} boletos asignados", parse_mode="Markdown")
    cerrar_sesion(chat_id)


# ============================================================
# HELPERS DE FORMATO
# ============================================================
def _formatear_faltantes_prenda(faltantes):
    labels = {"nombre": "❓ Nombre de la prenda", "costo": "❓ Precio de costo (del lote)", "precio": "❓ Precio de venta (por unidad)", "stock": "❓ Cantidad de unidades", "tienda": "❓ De qué tienda"}
    return "\n".join(f"_{labels.get(f, f)}_" for f in faltantes)

def _formatear_faltantes_venta(faltantes):
    labels = {"cliente": "❓ ¿A qué clienta?", "prenda": "❓ ¿Qué prenda(s)?", "estado": "❓ ¿Pagó o queda pendiente?"}
    return "\n".join(f"_{labels.get(f, f)}_" for f in faltantes)

def _resumen_parcial_prenda(datos):
    parts = []
    if datos.get("nombre"): parts.append(f"👗 {datos['nombre']}")
    if datos.get("costo"): parts.append(f"💰 Costo: S/{datos['costo']}")
    if datos.get("precio"): parts.append(f"🏷️ Precio: S/{datos['precio']}")
    if datos.get("stock"): parts.append(f"📦 Stock: {datos['stock']} uds")
    if datos.get("tienda"): parts.append(f"🏪 {datos['tienda']}")
    return "\n".join(parts) if parts else "(sin datos aún)"

def _resumen_parcial_venta(datos):
    parts = []
    if datos.get("cliente"): parts.append(f"👤 {datos['cliente']}")
    if datos.get("items"):
        for it in datos["items"]:
            parts.append(f"  👗 {it.get('prenda','?')} × {it.get('cantidad',1)} (S/{it.get('precio',0)})")
    if datos.get("estado"): parts.append(f"📋 {datos['estado']}")
    if datos.get("fecha"): parts.append(f"📅 {datos['fecha']}")
    return "\n".join(parts) if parts else "(sin datos aún)"


# ============================================================
# DESAMBIGUACIÓN UNIVERSAL
# ============================================================
def _resolver_disambiguation(mensaje: str, candidatos: list) -> str | None:
    """
    Resuelve la respuesta del usuario contra una lista de candidatos.
    Soporta voz y texto. Whisper puede transcribir números como texto o dígitos.
    """
    msg = mensaje.strip().lower().rstrip(".")
    
    # Cancelar/ninguna
    if msg in ("ninguna", "cancelar", "ninguno", "no", "no ninguna", "nada", "déjalo", "dejalo"):
        return "__ninguna__"
    
    # Afirmativo → primer candidato
    afirmativos = ("sí", "si", "sí esa", "si esa", "esa", "esa misma", "la primera",
                   "la 1", "1", "correcto", "el primero", "el 1", "uno", "la uno",
                   "la primera opción", "primera", "primero", "el uno")
    if msg in afirmativos:
        return candidatos[0] if candidatos else None
    
    # Mapa de texto a número (lo que Whisper puede transcribir)
    texto_a_num = {
        "uno": 0, "una": 0, "primero": 0, "primera": 0,
        "dos": 1, "segundo": 1, "segunda": 1,
        "tres": 2, "tercero": 2, "tercera": 2,
        "cuatro": 3, "cuarto": 3, "cuarta": 3,
        "cinco": 4, "quinto": 4, "quinta": 4,
        "seis": 5, "sexto": 5, "sexta": 5,
        "siete": 6, "séptimo": 6, "séptima": 6, "septimo": 6,
        "ocho": 7, "octavo": 7, "octava": 7,
    }
    
    # Extraer número del mensaje (formatos: "3", "el 3", "la 3", "número 3", "opción 3", "el tres")
    import re
    
    # Primero intentar con dígitos
    digit_match = re.search(r'\b(\d)\b', msg)
    if digit_match:
        idx = int(digit_match.group(1)) - 1  # Convertir a 0-indexed
        if 0 <= idx < len(candidatos):
            return candidatos[idx]
    
    # Luego con texto numérico
    for palabra in msg.split():
        palabra = palabra.strip(".,;:!?")
        if palabra in texto_a_num:
            idx = texto_a_num[palabra]
            if 0 <= idx < len(candidatos):
                return candidatos[idx]
    
    # "no, es X" → extraer X y buscar coincidencia
    for prefix in ("no es ", "no, es ", "es ", "es la ", "es el "):
        if msg.startswith(prefix):
            busqueda = msg[len(prefix):].strip()
            for c in candidatos:
                if busqueda in c.lower() or c.lower() in busqueda:
                    return c
            return busqueda if len(busqueda) > 2 else None
    
    # Búsqueda directa por coincidencia parcial
    for c in candidatos:
        if msg in c.lower() or c.lower() in msg:
            return c
    
    # Búsqueda por palabras clave (al menos 2 palabras coinciden)
    palabras_msg = set(msg.split())
    for c in candidatos:
        palabras_c = set(c.lower().split())
        if len(palabras_msg & palabras_c) >= 2:
            return c
    
    return None


def _crear_disambiguation(sesion_datos: dict, campo: str, candidatos: list, prendas_inv: list = None):
    """Crea un estado de desambiguación en la sesión."""
    sesion_datos["_disambiguation"] = {
        "campo": campo,
        "candidatos": candidatos,
    }
    if prendas_inv:
        sesion_datos["_prendas_inv"] = prendas_inv


# ============================================================
# VER FOTO
# ============================================================
async def _iniciar_ver_foto(update, context, msg, mensaje):
    """Busca una prenda y muestra su foto."""
    chat_id = update.effective_chat.id
    clientes, prendas, tiendas = await _cargar_contexto()
    datos = await extraer_datos("consultar_stock", mensaje, clientes, prendas, tiendas)
    
    prenda_buscar = datos.get("prenda", "")
    if not prenda_buscar:
        await msg.edit_text("❓ ¿De qué prenda quieres ver la foto? Dime el nombre.")
        return
    
    # Buscar coincidencias
    matches = [p for p in prendas if prenda_buscar.lower() in p["nombre"].lower()]
    if not matches:
        palabras = prenda_buscar.lower().split()
        matches = [p for p in prendas if any(w in p["nombre"].lower() for w in palabras if len(w) > 2)]
    
    if not matches:
        await msg.edit_text(f"❌ No encontré \"{prenda_buscar}\" en el inventario.")
        return
    
    if len(matches) == 1:
        await msg.edit_text("📸 Buscando foto...")
        await _mostrar_foto_prenda(update, context, matches[0]["nombre"], prendas)
        try:
            await msg.delete()
        except:
            pass
    else:
        # Múltiples coincidencias → desambiguar
        nombres = [p["nombre"] for p in matches[:8]]
        opts = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(nombres))
        crear_sesion(chat_id, "ver_foto", {})
        sesion = get_sesion(chat_id)
        _crear_disambiguation(sesion["datos"], "prenda", nombres, prendas)
        await msg.edit_text(f"📸 ¿De cuál prenda quieres ver la foto?\n{opts}\n\n_Escribe el número o el nombre_", parse_mode="Markdown")


async def _mostrar_foto_prenda(update, context, nombre_prenda: str, prendas: list):
    """Muestra la foto de una prenda."""
    from notion_api import obtener_foto_url
    
    match = [p for p in prendas if p["nombre"] == nombre_prenda]
    if not match:
        match = [p for p in prendas if nombre_prenda.lower() in p["nombre"].lower()]
    
    if not match:
        await update.message.reply_text(f"❌ No encontré \"{nombre_prenda}\".")
        return
    
    p = match[0]
    foto_url = await obtener_foto_url(p["id"])
    
    if foto_url:
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=foto_url,
                caption=f"👗 *{p['nombre']}*\n📦 Stock: {p.get('stock',0)} | 💰 S/{p.get('precio',0)}",
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(f"👗 *{p['nombre']}*\n📸 [Ver foto]({foto_url})\n📦 Stock: {p.get('stock',0)} | 💰 S/{p.get('precio',0)}", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"👗 *{p['nombre']}*\n📸 Esta prenda no tiene foto registrada.\n📦 Stock: {p.get('stock',0)} | 💰 S/{p.get('precio',0)}", parse_mode="Markdown")

