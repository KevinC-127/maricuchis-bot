from config import *
from notion_api import *
# ============================================================
# IA — GEMINI FLASH INTEGRADO
# ============================================================

SYSTEM_PROMPT = """Eres la asistente de Maricuchis Store, una tienda de ropa al por menor en Lima, Perú.
Tu nombre es Maricuchis IA. La dueña se llama Maritza.

PUEDES HACER LO SIGUIENTE (responde SIEMPRE en JSON con la estructura indicada):

1. CONSULTAR datos del inventario o ventas → ya tienes los datos en el contexto
2. CALCULAR: márgenes, ganancias, ROI, proyecciones, precios sugeridos
3. ACTUALIZAR precio de una prenda → {"accion": "actualizar_precio", "prenda": "nombre", "precio": 99}
4. ACTUALIZAR stock de una prenda → {"accion": "actualizar_stock", "prenda": "nombre", "stock": 5}
5. REGISTRAR una venta → {"accion": "registrar_venta", "prenda": "nombre", "cantidad": 2, "precio": 35, "cliente": "opcional"}
6. CREAR prenda nueva → {"accion": "crear_prenda", "nombre": "...", "costo": 60, "precio": 90, "stock": 12, "tienda": "opcional"}
7. REDACTAR texto para WhatsApp → {"accion": "texto_whatsapp", "texto": "...mensaje listo para copiar..."}
8. RESPONDER preguntas → {"accion": "responder", "texto": "...tu respuesta..."}
9. SUGERIR precio → {"accion": "responder", "texto": "...recomendación con justificación..."}

ACCIONES EXTRA:
7. GENERAR gráfico de stock → {"accion": "generar_grafico", "tipo": "stock"}
8. CREAR prenda con foto (cuando recibes imagen) → {"accion": "crear_prenda_con_foto", "nombre": "...", "costo": 60, "precio": 90, "stock": 12, "tienda": "opcional"}
9. MOSTRAR prenda con foto → {"accion": "mostrar_prenda", "prenda": "nombre exacto o aproximado", "texto": "respuesta con datos"}
   Usa esta acción cuando: te pidan VER una prenda, consulten su precio/stock/detalle, o mencionen una prenda específica.
   SIEMPRE incluye el campo "texto" con los datos de la prenda (precio, stock, estado, etc.)

REGLAS:
- Responde SIEMPRE en JSON válido, sin texto adicional fuera del JSON
- Para acciones sobre prendas, usa el nombre más parecido que encuentres en el inventario
- MEMORIA: el historial de la conversación se incluye como turnos previos. Úsalo para resolver referencias como "el primero", "esa prenda", "la misma". Nunca ignores el contexto previo.
- Si no entiendes la solicitud, usa {"accion": "responder", "texto": "No entendí. ¿Puedes ser más específica?"}
- Si algo está fuera de tu alcance (no es del negocio), usa {"accion": "responder", "texto": "Solo puedo ayudarte con Maricuchis Store."}
- Usa soles peruanos (S/) siempre
- Sé breve y directa en las respuestas de texto
- Si te piden texto para WhatsApp, hazlo atractivo con emojis, menciona precio y disponibilidad
- Si recibes una imagen, descríbela y úsala para registrar la prenda con accion crear_prenda_con_foto"""

async def llamar_gemini(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_llamar_gemini, *args, **kwargs))

def _sync_llamar_gemini(mensaje_usuario: str, contexto_inventario: str,
                  historial: list = None, imagen_bytes: bytes = None) -> dict:
    """Llama a Gemini 2.5 Flash con historial multi-turn y soporte de imagen."""
    if not GEMINI_API_KEY:
        return {"accion": "responder", "texto": "GEMINI_API_KEY no configurada en Railway."}

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + GEMINI_API_KEY
    )

    # Turno inicial: sistema + inventario
    sistema_texto = SYSTEM_PROMPT + "\n\nINVENTARIO ACTUAL:\n" + contexto_inventario
    contents = [
        {"role": "user",  "parts": [{"text": sistema_texto}]},
        {"role": "model", "parts": [{"text": '{"accion":"responder","texto":"Entendido. Lista para ayudarte."}'}]},
    ]

    # Historial previo de la sesión
    for turno in (historial or []):
        contents.append({"role": "user",  "parts": [{"text": turno["usuario"]}]})
        contents.append({"role": "model", "parts": [{"text": turno["ia_raw"]}]})

    # Mensaje actual (con imagen opcional)
    partes = []
    if imagen_bytes:
        img_b64 = base64.b64encode(imagen_bytes).decode("utf-8")
        partes.append({"inline_data": {"mime_type": "image/jpeg", "data": img_b64}})
    partes.append({"text": mensaje_usuario})
    contents.append({"role": "user", "parts": partes})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code != 200:
            logger.error("Error Gemini %s: %s", r.status_code, r.text[:300])
            return {"accion": "responder", "texto": "Error al contactar la IA. Intenta de nuevo."}

        respuesta_raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if respuesta_raw.startswith("```"):
            respuesta_raw = respuesta_raw.split("```")[1]
            if respuesta_raw.startswith("json"):
                respuesta_raw = respuesta_raw[4:]
        resultado = json.loads(respuesta_raw)
        resultado["_raw"] = respuesta_raw
        return resultado

    except json.JSONDecodeError:
        return {"accion": "responder", "texto": respuesta_raw, "_raw": respuesta_raw}
    except Exception as e:
        logger.error("Error Gemini: %s", e)
        return {"accion": "responder", "texto": "Hubo un error con la IA. Intenta de nuevo.", "_raw": ""}

async def construir_contexto_inventario() -> str:
    """Construye un resumen del inventario para pasarle a Gemini como contexto."""
    prendas = await fetch_inventario_completo()
    if not prendas:
        return "Inventario vacío."

    lineas = [f"Total prendas: {len(prendas)}\n"]
    for p in prendas:
        lineas.append(
            f"- {p['nombre']} | stock: {p['stock']} | precio: S/{p['precio']} | "
            f"costo_u: S/{p['costo_u']:.2f} | vendidas: {p['vendidas']} | "
            f"ganancia_u: S/{p['ganancia_u']:.2f} | tienda: {p['tienda']} | estado: {p['estado']}"
        )

    total_invertido  = sum(p["costo"] for p in prendas)
    total_ganancia   = sum(p["ganancia_real"] for p in prendas)
    total_vendidas   = sum(p["vendidas"] for p in prendas)
    ganancia_pot     = sum(p["stock"] * p["ganancia_u"] for p in prendas)

    lineas.append(f"\nRESUMEN FINANCIERO:")
    lineas.append(f"- Total invertido: S/{total_invertido:.0f}")
    lineas.append(f"- Ganancia realizada: S/{total_ganancia:.0f}")
    lineas.append(f"- Unidades vendidas: {total_vendidas}")
    lineas.append(f"- Ganancia potencial (stock restante): S/{ganancia_pot:.0f}")

    return "\n".join(lineas)

async def ejecutar_accion_ia(accion_dict: dict, update: Update) -> str:
    """Ejecuta la acción que Gemini indicó y retorna el mensaje de respuesta."""
    accion = accion_dict.get("accion", "responder")

    # --- Solo responder ---
    if accion == "responder":
        return accion_dict.get("texto", "No tengo respuesta para eso.")

    # --- Texto para WhatsApp ---
    if accion == "texto_whatsapp":
        texto = accion_dict.get("texto", "")
        return f"📱 Texto listo para WhatsApp:\n\n{texto}"

    # --- Actualizar precio ---
    if accion == "actualizar_precio":
        nombre  = accion_dict.get("prenda", "")
        precio  = accion_dict.get("precio")
        if not nombre or precio is None:
            return "Falta el nombre de la prenda o el precio."
        prendas = await buscar_prendas_notion(nombre)
        if not prendas:
            return f"No encontré la prenda '{nombre}' en el inventario."
        prenda = prendas[0]
        exito  = await actualizar_prenda_notion(prenda["id"], {"Precio": {"number": float(precio)}})
        if exito:
            return f"✅ Precio de '{prenda['nombre']}' actualizado a S/{precio:.0f}"
        return f"❌ Error al actualizar el precio de '{prenda['nombre']}'."

    # --- Actualizar stock ---
    if accion == "actualizar_stock":
        nombre = accion_dict.get("prenda", "")
        stock  = accion_dict.get("stock")
        if not nombre or stock is None:
            return "Falta el nombre de la prenda o el stock."
        prendas = await buscar_prendas_notion(nombre)
        if not prendas:
            return f"No encontré la prenda '{nombre}' en el inventario."
        prenda = prendas[0]
        exito  = await actualizar_prenda_notion(prenda["id"], {"Stock": {"number": int(stock)}})
        if exito:
            return f"✅ Stock de '{prenda['nombre']}' actualizado a {stock} uds"
        return f"❌ Error al actualizar el stock de '{prenda['nombre']}'."

    # --- Registrar venta ---
    if accion == "registrar_venta":
        nombre   = accion_dict.get("prenda", "")
        cantidad = int(accion_dict.get("cantidad", 1))
        precio_v = float(accion_dict.get("precio", 0))
        cliente  = accion_dict.get("cliente", "")
        if not nombre or precio_v <= 0:
            return "Falta el nombre de la prenda o el precio de venta."
        prendas = await buscar_prendas_notion(nombre)
        if not prendas:
            return f"No encontré la prenda '{nombre}'."
        prenda = prendas[0]
        if prenda["stock"] < cantidad:
            return f"❌ Solo hay {prenda['stock']} uds de '{prenda['nombre']}'. No se puede registrar {cantidad}."
        costo_u  = prenda["costo_u"]
        descuento_ia = float(accion_dict.get("descuento", 0) or 0)
        ganancia = (precio_v - descuento_ia - costo_u) * cantidad
        nuevo_stock = prenda["stock"] - cantidad
        # Descontar stock
        await actualizar_prenda_notion(prenda["id"], {"Stock": {"number": nuevo_stock}})
        # Registrar en BD ventas
        await registrar_venta_notion(prenda["nombre"], cantidad, precio_v, costo_u, ganancia, cliente, descuento=descuento_ia)
        return (
            f"✅ Venta registrada!\n"
            f"Prenda: {prenda['nombre']}\n"
            f"Cantidad: {cantidad} uds\n"
            f"Precio: S/{precio_v:.0f}\n"
            f"Ganancia: S/{ganancia:.0f}\n"
            f"Stock restante: {nuevo_stock} uds"
        )

    # --- Crear prenda ---
    if accion == "crear_prenda":
        nombre = accion_dict.get("nombre", "")
        costo  = float(accion_dict.get("costo", 0))
        precio = float(accion_dict.get("precio", 0))
        stock  = int(accion_dict.get("stock", 0))
        tienda = accion_dict.get("tienda", None)
        if not nombre or costo <= 0 or precio <= 0 or stock <= 0:
            return "Faltan datos para crear la prenda (nombre, costo, precio, stock)."
        exito = await crear_prenda_notion(nombre, costo, precio, stock, tienda=tienda)
        if exito:
            costo_u  = round(costo / stock, 2)
            ganancia = precio - costo_u
            return (
                f"✅ Prenda creada!\n"
                f"Nombre: {nombre}\n"
                f"Costo unitario: S/{costo_u:.2f}\n"
                f"Precio: S/{precio:.0f}\n"
                f"Stock: {stock} uds\n"
                f"Ganancia/ud: S/{ganancia:.0f}"
            )
        return f"❌ Error al crear la prenda '{nombre}'."

    # --- Mostrar prenda con foto ---
    if accion == "mostrar_prenda":
        nombre = accion_dict.get("prenda", "")
        texto  = accion_dict.get("texto", "")
        if not nombre:
            return texto or "No se especificó la prenda."
        prendas = await buscar_prendas_notion(nombre)
        if not prendas:
            return texto or "No encontré esa prenda en el inventario."
        prenda   = prendas[0]
        foto_url = await obtener_foto_url(prenda["id"])
        # Devolver señal especial con datos para que ia_procesar_mensaje envíe la foto
        return "__MOSTRAR_FOTO__" + "|||" + (foto_url or "") + "|||" + (texto or nombre)

    # --- Generar grafico ---
    if accion == "generar_grafico":
        return "__GENERAR_GRAFICO__"

    # --- Crear prenda con foto (IA recibio imagen) ---
    if accion == "crear_prenda_con_foto":
        nombre   = accion_dict.get("nombre", "")
        costo    = float(accion_dict.get("costo", 0))
        precio   = float(accion_dict.get("precio", 0))
        stock    = int(accion_dict.get("stock", 0))
        tienda   = accion_dict.get("tienda", None)
        foto_url = accion_dict.get("_foto_url", None)
        if not nombre or costo <= 0 or precio <= 0 or stock <= 0:
            return "Faltan datos para crear la prenda (nombre, costo, precio, stock)."
        exito = await crear_prenda_notion(nombre, costo, precio, stock, foto_url=foto_url, tienda=tienda)
        if exito:
            costo_u = round(costo / stock, 2)
            ganancia_u = precio - costo_u
            con_foto = " con foto" if foto_url else " (sin foto)"
            return (
                "Prenda creada" + con_foto + "!\n"
                + "Nombre: " + nombre + "\n"
                + "Costo unitario: S/" + f"{costo_u:.2f}" + "\n"
                + "Precio: S/" + f"{precio:.0f}" + "\n"
                + "Stock: " + str(stock) + " uds\n"
                + "Ganancia/ud: S/" + f"{ganancia_u:.0f}"
            )
        return "Error al crear la prenda " + nombre + "."

    return "No entendi la accion. Intenta de nuevo."

# ============================================================
# HELPERS — INTERFAZ
# ============================================================
def teclado_lista_prendas(prendas: list, accion: str, pagina: int = 0, por_pagina: int = 10) -> InlineKeyboardMarkup:
    botones = []
    inicio = pagina * por_pagina
    fin = inicio + por_pagina
    pagina_prendas = prendas[inicio:fin]
    
    for p in pagina_prendas:
        label = f"{p['nombre']} (stock: {p['stock']})"
        botones.append([InlineKeyboardButton(label, callback_data=f"{accion}:{p['id']}")])
        
    nav_botones = []
    if pagina > 0:
        nav_botones.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"page_{accion}:{pagina-1}"))
    if fin < len(prendas):
        nav_botones.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"page_{accion}:{pagina+1}"))
        
    if nav_botones:
        botones.append(nav_botones)
        
    botones.append([InlineKeyboardButton("Cancelar", callback_data="cancelar")])
    return InlineKeyboardMarkup(botones)

def teclado_menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📸 Nueva prenda",    callback_data="menu_nueva_menu"),
            InlineKeyboardButton("💰 Registrar venta", callback_data="menu_venta"),
        ],
        [
            InlineKeyboardButton("🔍 Consultar prenda",callback_data="menu_stock"),
            InlineKeyboardButton("🔴 Ver agotados",    callback_data="menu_agotados"),
        ],
        [
            InlineKeyboardButton("✏️ Actualizar / Eliminar prenda", callback_data="menu_editar"),
        ],
        [
            InlineKeyboardButton("🗑️ Eliminar venta", callback_data="menu_eliminar_venta"),
        ],
        [
            InlineKeyboardButton("📋 Ver inventario",  callback_data="menu_inventario"),
            InlineKeyboardButton("📊 Gráfico stock",      callback_data="menu_graficostock"),
        ],
        [
            InlineKeyboardButton("💰 Ganancias",          callback_data="menu_ganancias"),
            InlineKeyboardButton("⚖️ Comparar prendas",   callback_data="menu_comparar"),
        ],
        [InlineKeyboardButton("🤖 Preguntarle a la IA",   callback_data="menu_ia")],
        [InlineKeyboardButton("❓ Ayuda",                  callback_data="menu_ayuda")],
    ])

def teclado_menu_nueva_prenda() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Sin foto",            callback_data="menu_sinfoto")],
        [InlineKeyboardButton("🖼️ Actualizar foto",    callback_data="menu_adjfoto")],
        [InlineKeyboardButton("✍️ Escribir nueva prenda", callback_data="menu_nueva_guiado")],
        [InlineKeyboardButton("⬅️ Volver",              callback_data="menu_inicio")]
    ])

def _texto_ayuda() -> str:
    return (
        "Guia de uso - Maricuchis Store Bot v5.0\n\n"
        "REGISTRAR PRENDAS\n"
        "/sinfoto - Registrar prenda sin foto (paso a paso)\n"
        "/adjfoto - Adjuntar foto a prenda ya registrada\n\n"
        "VENTAS Y STOCK\n"
        "/venta   - Registrar venta y descontar stock\n"
        "/prenda  - Consultar detalle de una prenda\n"
        "/agotados - Ver todas las prendas sin stock\n\n"
        "VER Y CONSULTAS\n"
        "/verfoto    - Ver la foto de una prenda\n"
        "/inventario - Ver todas las prendas del inventario\n\n"
        "FINANZAS\n"
        "/resumen    - Resumen financiero completo\n"
        "/comparar   - Comparar 2 o mas prendas\n"
        "/pormargen  - Ranking por rentabilidad\n"
        "/portienda  - Resumen agrupado por tienda\n\n"
        "🤖 IA INTEGRADA\n"
        "/ia - Activar modo conversacional con la IA\n"
        "      Ejemplos de lo que puedes decirle:\n"
        "      'Actualiza el precio de la blusa a S/35'\n"
        "      'Escríbeme texto para WhatsApp de la chompa'\n"
        "      '¿Cuáles prendas debo reponer?'\n"
        "      'Registra que vendí 2 blusas a S/30'\n"
        "      'Crea una prenda: blusa blanca, costo 60, precio 90, stock 12'\n"
        "      '¿Cuánto gané esta semana?'\n\n"
        "EDITAR INVENTARIO\n"
        "/actualizar - Editar datos de una prenda\n"
        "/eliminar   - Eliminar una prenda\n\n"
        "OTROS\n"
        "/menu     - Ver el menu con botones\n"
        "/chatid   - Ver tu Chat ID\n"
        "/cancelar - Cancelar lo que estes haciendo\n"
        "/ayuda    - Mostrar esta guia"
    )


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
