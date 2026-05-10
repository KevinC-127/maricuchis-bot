from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import pytz

from handlers import _reply
from ui import teclado_lista_prendas, teclado_lista_clientes
from notion_api import buscar_prendas_notion, crear_venta_notion, actualizar_stock_notion, obtener_clientes_previos

# ESTADOS
VENTA_BUSCAR    = 30
VENTA_CONFIRMAR = 31
VENTA_CANTIDAD  = 32
VENTA_PRECIO    = 33
VENTA_MAS       = 37
VENTA_CLIENTE   = 35
VENTA_FECHA     = 34
VENTA_DESCUENTO = 36
VENTA_PAGO      = 38
VENTA_BOLETOS   = 39

timezone_lima = pytz.timezone('America/Lima')

async def cmd_vendi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["carrito"] = []
    await _reply(update, "🛒 *Registrar Venta*\n\nEscribe el nombre (o parte) de la primera prenda:", parse_mode="Markdown")
    return VENTA_BUSCAR

async def venta_buscar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return VENTA_BUSCAR
    
    await update.message.reply_text(f"Buscando '{termino}'...")
    prendas = await buscar_prendas_notion(termino)
    
    if not prendas:
        await update.message.reply_text("No encontré prendas con ese nombre.")
        return VENTA_BUSCAR
        
    # Mostrar todas las prendas (incluyendo agotadas con advertencia)
    context.user_data["prendas_encontradas"] = {p["id"]: p for p in prendas}
    
    # Advertir si hay agotadas
    agotadas = [p for p in prendas if p["stock"] <= 0]
    msg_extra = ""
    if agotadas:
        nombres_agotadas = ", ".join(p["nombre"] for p in agotadas[:3])
        msg_extra = f"\n⚠️ _Algunas tienen stock 0: {nombres_agotadas}_"
    
    await update.message.reply_text(
        f"Encontré {len(prendas)} prendas. ¿Cuál agregas al carrito?{msg_extra}",
        reply_markup=teclado_lista_prendas(prendas, "sel_venta"),
        parse_mode="Markdown"
    )
    return VENTA_CONFIRMAR

async def venta_confirmar_prenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("page_sel_venta:"):
        pagina = int(query.data.split(":")[1])
        prendas_dict = context.user_data.get("prendas_encontradas", {})
        await query.edit_message_reply_markup(reply_markup=teclado_lista_prendas(list(prendas_dict.values()), "sel_venta", pagina))
        return VENTA_CONFIRMAR
        
    if query.data == "cancelar":
        await query.edit_message_text("Operación cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
        
    page_id = query.data.replace("sel_venta:", "")
    prenda = context.user_data.get("prendas_encontradas", {}).get(page_id)
    if not prenda:
        await query.edit_message_text("Error. Intenta de nuevo.")
        return ConversationHandler.END
        
    context.user_data["item_actual"] = {"prenda": prenda}
    await query.edit_message_text(f"Seleccionada: {prenda['nombre']}\nStock: {prenda['stock']} | Precio: S/{prenda['precio']:.0f}\n\n¿Cuántas unidades vendiste de esta prenda?")
    return VENTA_CANTIDAD

async def venta_recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = context.user_data["item_actual"]
    prenda = item["prenda"]
    try:
        cant = int(update.message.text.strip())
        assert 1 <= cant <= prenda["stock"]
    except:
        await update.message.reply_text(f"Escribe un número entre 1 y {prenda['stock']}.")
        return VENTA_CANTIDAD
        
    item["cantidad"] = cant
    
    # Generar 10 botones de descuento (1 a 10 soles)
    filas_descuentos = []
    current_row = []
    for d in range(1, 11):
        btn = InlineKeyboardButton(f"- S/{d}", callback_data=f"precio_venta_{prenda['precio'] - d:.0f}")
        current_row.append(btn)
        if len(current_row) == 5: # 5 botones por fila
            filas_descuentos.append(current_row)
            current_row = []
    
    botones = [
        [InlineKeyboardButton(f"Sin descuento (S/ {prenda['precio']:.0f})", callback_data=f"precio_venta_{prenda['precio']:.0f}")],
        *filas_descuentos,
        [InlineKeyboardButton("⬅️ Volver", callback_data="volver_cantidad")]
    ]
    await update.message.reply_text("¿Aplicarás algún descuento a esta prenda? (Elige un botón o escribe el precio unitario final):", reply_markup=InlineKeyboardMarkup(botones))
    return VENTA_PRECIO


async def venta_volver_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item = context.user_data["item_actual"]
    await query.edit_message_text(f"Seleccionada: {item['prenda']['nombre']}\nStock: {item['prenda']['stock']}\n\n¿Cuántas unidades vendiste?")
    return VENTA_CANTIDAD

async def venta_recibir_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    precio = float(query.data.replace("precio_venta_", ""))
    context.user_data["item_actual"]["precio_final"] = precio
    return await _preguntar_mas_prendas(query.message, context)

async def venta_recibir_precio_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio = float(update.message.text.strip())
        assert precio >= 0
    except:
        await update.message.reply_text("Ingresa un precio numérico válido.")
        return VENTA_PRECIO
    context.user_data["item_actual"]["precio_final"] = precio
    return await _preguntar_mas_prendas(update.message, context)

async def _preguntar_mas_prendas(msg_obj, context):
    item = context.user_data["item_actual"]
    context.user_data["carrito"].append(item)
    del context.user_data["item_actual"]
    
    carrito = context.user_data["carrito"]
    resumen = "\n".join([f"- {i['cantidad']}x {i['prenda']['nombre']} (S/ {i['precio_final']:.2f} c/u)" for i in carrito])
    total = sum(i["cantidad"] * i["precio_final"] for i in carrito)
    
    texto = f"🛒 *Carrito Actual:*\n{resumen}\n\n*Total Parcial:* S/ {total:.2f}\n\n¿Deseas agregar otra prenda a esta venta o finalizar?"
    botones = [
        [InlineKeyboardButton("➕ Agregar otra prenda", callback_data="mas_si")],
        [InlineKeyboardButton("✅ Finalizar y Cobrar", callback_data="mas_no")]
    ]
    try:
        await msg_obj.edit_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception:
        await msg_obj.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    return VENTA_MAS

async def venta_mas_prendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "mas_si":
        await query.edit_message_text("Escribe el nombre de la siguiente prenda a buscar:")
        return VENTA_BUSCAR
    else:
        await venta_pedir_cliente(query.message, context)
        return VENTA_CLIENTE

async def venta_pedir_cliente(msg_obj, context, pagina=0):
    clientes_prev = context.user_data.get("clientes_previos")
    if not clientes_prev:
        clientes_prev = await obtener_clientes_previos()
        context.user_data["clientes_previos"] = clientes_prev
        
    teclado = teclado_lista_clientes(clientes_prev, pagina)
    texto = "👤 *¿A quién le vendiste todo esto?*"
    if hasattr(msg_obj, "edit_text"):
        try:
            await msg_obj.edit_text(texto, reply_markup=teclado, parse_mode="Markdown")
        except:
            await msg_obj.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")
    else:
        await msg_obj.reply_text(texto, reply_markup=teclado, parse_mode="Markdown")

async def venta_recibir_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        data = query.data
        if data.startswith("page_cliente:"):
            await venta_pedir_cliente(query.message, context, pagina=int(data.split(":")[1]))
            return VENTA_CLIENTE
        elif data == "cliente_sin_nombre":
            context.user_data["venta_cliente"] = ""
        elif data == "cliente_nueva":
            await query.edit_message_text("Escribe el nombre del nuevo cliente:")
            return VENTA_CLIENTE
        elif data.startswith("cliente_prev_"):
            context.user_data["venta_cliente"] = data.replace("cliente_prev_", "")
        return await venta_pedir_fecha(query.message, context)
    else:
        context.user_data["venta_cliente"] = update.message.text.strip()
        return await venta_pedir_fecha(update.message, context)

async def venta_pedir_fecha(msg_obj, context):
    from datetime import timedelta
    ahora = datetime.now(timezone_lima)
    fechas = []
    etiquetas = ["📅 Hoy", "⏪ Ayer", "⏪ Hace 2 días", "⏪ Hace 3 días", "⏪ Hace 4 días"]
    for i, etq in enumerate(etiquetas):
        dia_obj = ahora - timedelta(days=i)
        dia_iso = dia_obj.strftime("%Y-%m-%d")
        dia_visual = dia_obj.strftime("%d-%m-%Y")
        fechas.append(InlineKeyboardButton(f"{etq} ({dia_visual})", callback_data=f"fecha_venta_{dia_iso}"))
    botones = [
        [fechas[0]],
        [fechas[1], fechas[2]],
        [fechas[3], fechas[4]],
    ]
    texto = "📅 *¿Qué día fue la venta?*\nElige una opción o escribe la fecha (DD-MM-AAAA):"
    try:
        await msg_obj.edit_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception:
        await msg_obj.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    return VENTA_FECHA

async def venta_recibir_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data["venta_fecha"] = query.data.replace("fecha_venta_", "")
        return await venta_pedir_descuento(query.message, context)
    else:
        texto = update.message.text.strip()
        # Convertir DD-MM-AAAA a AAAA-MM-DD para Notion
        import re
        if re.match(r"^\d{2}-\d{2}-\d{4}$", texto):
            partes = texto.split("-")
            texto = f"{partes[2]}-{partes[1]}-{partes[0]}"
        context.user_data["venta_fecha"] = texto
        return await venta_pedir_descuento(update.message, context)

async def venta_pedir_descuento(msg_obj, context):
    total = sum(i["cantidad"] * i["precio_final"] for i in context.user_data["carrito"])
    botones = [
        [InlineKeyboardButton("Sin descuento (0)", callback_data="descuento_0")],
        [InlineKeyboardButton("S/ 5", callback_data="descuento_5"), InlineKeyboardButton("S/ 10", callback_data="descuento_10")]
    ]
    texto = f"💸 *Descuento Global*\nTotal del carrito: S/ {total:.2f}\n¿Hiciste algún descuento adicional al total? (Escribe el monto o elige):"
    try:
        await msg_obj.edit_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception:
        await msg_obj.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    return VENTA_DESCUENTO

async def venta_recibir_descuento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        context.user_data["venta_descuento"] = float(query.data.replace("descuento_", ""))
        return await venta_pedir_pago(query.message, context)
    else:
        try:
            context.user_data["venta_descuento"] = float(update.message.text.strip())
        except:
            await update.message.reply_text("Ingresa un número válido.")
            return VENTA_DESCUENTO
        return await venta_pedir_pago(update.message, context)

async def venta_pedir_pago(msg_obj, context):
    botones = [
        [InlineKeyboardButton("✅ Completado (Pagado)", callback_data="pago_Completado")],
        [InlineKeyboardButton("⏳ Pendiente (Separado)", callback_data="pago_Pendiente")]
    ]
    texto = "💳 *Estado del Pago*\n¿El cliente ya te pagó todo o es un pedido/separación pendiente?"
    try:
        await msg_obj.edit_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except Exception:
        await msg_obj.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    return VENTA_PAGO

async def venta_recibir_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    estado_pago = query.data.replace("pago_", "")
    context.user_data["venta_pago"] = estado_pago
    
    cliente = context.user_data["venta_cliente"]
    carrito = context.user_data["carrito"]
    
    # Calcular boletos automáticos sugeridos (1 por prenda)
    boletos_sugeridos = sum(item["cantidad"] for item in carrito)
    context.user_data["boletos_sugeridos"] = boletos_sugeridos
    
    if cliente.lower() == "anonimo":
        # Si es anonimo, no se puede asignar boletos
        context.user_data["venta_boletos"] = 0
        return await venta_guardar(query.message, context)
        
    botones = [
        [InlineKeyboardButton(f"Automático ({boletos_sugeridos} boletos)", callback_data=f"boletos_auto")],
        [InlineKeyboardButton("No asignar (0)", callback_data="boletos_0")]
    ]
    texto = f"🎫 *Asignación de Boletos*\n\n¿Cuántos boletos deseas asignar a {cliente} por esta compra?\n\nPuedes elegir Automático ({boletos_sugeridos} boletos por las {boletos_sugeridos} prendas), 0, o simplemente **escribe el número exacto** en el chat:"
    
    try:
        await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    except:
        await query.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(botones), parse_mode="Markdown")
    return VENTA_BOLETOS

async def venta_recibir_boletos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        opcion = query.data.replace("boletos_", "")
        if opcion == "auto":
            context.user_data["venta_boletos"] = context.user_data.get("boletos_sugeridos", 0)
        else:
            context.user_data["venta_boletos"] = int(opcion)
        return await venta_guardar(query.message, context)
    else:
        try:
            context.user_data["venta_boletos"] = int(update.message.text.strip())
            return await venta_guardar(update.message, context)
        except ValueError:
            await update.message.reply_text("Ingresa un número de boletos válido.")
            return VENTA_BOLETOS

async def venta_guardar(msg_obj, context: ContextTypes.DEFAULT_TYPE):
    estado_pago = context.user_data["venta_pago"]
    carrito = context.user_data["carrito"]
    cliente = context.user_data["venta_cliente"]
    fecha = context.user_data["venta_fecha"]
    descuento_global = context.user_data["venta_descuento"]
    boletos_asignados = context.user_data.get("venta_boletos", 0)
    
    try:
        await msg_obj.edit_message_text("Procesando carrito y actualizando Notion...")
    except:
        await msg_obj.reply_text("Procesando carrito y actualizando Notion...")
    
    # Repartir descuento global proporcionalmente
    desc_por_item = descuento_global / len(carrito) if len(carrito) > 0 else 0
    
    mensajes = []
    from notion_api import crear_boleto_notion
    
    for item in carrito:
        p = item["prenda"]
        c = item["cantidad"]
        pf = item["precio_final"]
        
        precio_base_unitario = p["precio"]
        descuento_unitario = precio_base_unitario - pf
        if descuento_unitario < 0: descuento_unitario = 0
        
        # Descuento total de la fila = (descuento individual * cantidad) + parte del descuento global
        descuento_total_fila = (descuento_unitario * c) + desc_por_item
        
        costo_u = p["costo_u"]
        ganancia = (pf * c) - (costo_u * c) - desc_por_item
        
        # En Notion Ventas DB (requiere que la DB soporte Estado)
        exito = await crear_venta_notion(
            prenda_id=p["id"],
            cantidad=c,
            precio_final=pf,  # Precio por unidad (Precio Venta)
            ganancia=ganancia,
            fecha_iso=fecha,
            cliente=cliente,
            descuento=descuento_total_fila,
            estado=estado_pago
        )
        if exito:
            # Registrar en tracker del dashboard para evitar boletos duplicados
            if estado_pago == "Completado" and isinstance(exito, str):
                try:
                    from dashboard import _ventas_completadas_procesadas
                    _ventas_completadas_procesadas.add(exito)
                except: pass
            await actualizar_stock_notion(p["id"], p["stock"] - c)
            mensajes.append(f"✅ {c}x {p['nombre']} (-S/{descuento_total_fila:.1f} desc)")
        else:
            mensajes.append(f"❌ Error en {p['nombre']}")
            
    # Asignar boletos una sola vez por toda la venta
    boleto_msg = ""
    if boletos_asignados > 0 and estado_pago != "Pendiente":
        await crear_boleto_notion(
            cliente=cliente,
            boletos=boletos_asignados,
            asunto=f"Compra de {len(carrito)} modelos diferentes",
            fecha_iso=fecha
        )
        boleto_msg = f"\n🎟️ *Boletos asignados:* {boletos_asignados}"
    elif boletos_asignados > 0 and estado_pago == "Pendiente":
        boleto_msg = f"\n🎟️ *Boletos guardados:* {boletos_asignados} (Se asignarán cuando el pago se complete)"
        # Podrías implementar lógica para guardar boletos pendientes si quieres, 
        # pero por ahora no los registramos en la BD.
            
    resumen_final = "\n".join(mensajes)
    await msg_obj.reply_text(
        f"🎉 *Venta Registrada con Éxito*\nEstado: {estado_pago}\nCliente: {cliente}{boleto_msg}\n\n{resumen_final}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_inicio")]])
    )
    context.user_data.clear()
    return ConversationHandler.END
