from telegram import InlineKeyboardButton, InlineKeyboardMarkup
# ============================================================
# UI — TECLADOS Y HELPERS DE INTERFAZ
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
            InlineKeyboardButton("📸 Registrar", callback_data="menu_nueva_menu"),
            InlineKeyboardButton("💰 Ventas",    callback_data="menu_ventas_sub"),
        ],
        [
            InlineKeyboardButton("🔍 Consultar", callback_data="menu_stock"),
            InlineKeyboardButton("📋 Inventario", callback_data="menu_inventario_sub"),
        ],
        [
            InlineKeyboardButton("💰 Ganancias",  callback_data="menu_ganancias"),
            InlineKeyboardButton("💸 Gastos",     callback_data="menu_gasto"),
        ],
        [
            InlineKeyboardButton("⚖️ Comparar",   callback_data="menu_comparar"),
            InlineKeyboardButton("🎫 Sorteo",     callback_data="menu_boletos"),
        ],
        [InlineKeyboardButton("❓ Ayuda",         callback_data="menu_ayuda")],
    ])

def teclado_submenu_ventas() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Registrar venta",       callback_data="menu_venta")],
        [InlineKeyboardButton("🔄 Actualizar pendiente",  callback_data="menu_actualizar_pendiente")],
        [InlineKeyboardButton("↩️ Devolución",            callback_data="menu_devolucion")],
        [InlineKeyboardButton("🗑️ Eliminar venta",       callback_data="menu_eliminar_venta")],
        [InlineKeyboardButton("⬅️ Volver",               callback_data="menu_inicio")],
    ])

def teclado_submenu_inventario() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ver inventario",       callback_data="menu_inventario")],
        [InlineKeyboardButton("🔴 Ver agotados",         callback_data="menu_agotados")],
        [InlineKeyboardButton("🏪 Por tienda",           callback_data="menu_inv_tienda")],
        [InlineKeyboardButton("📅 Por fecha de compra",  callback_data="menu_inv_fecha")],
        [InlineKeyboardButton("⬅️ Volver",               callback_data="menu_inicio")],
    ])

def teclado_menu_nueva_prenda() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Sin foto",               callback_data="menu_sinfoto")],
        [InlineKeyboardButton("🖼️ Actualizar foto",       callback_data="menu_adjfoto")],
        [InlineKeyboardButton("✍️ Escribir nueva prenda",  callback_data="menu_nueva_guiado")],
        [InlineKeyboardButton("✏️ Actualizar / Eliminar prenda", callback_data="menu_editar")],
        [InlineKeyboardButton("⬅️ Volver",                 callback_data="menu_inicio")],
    ])

def _texto_ayuda() -> str:
    return (
        "Guia de uso - Maricuchis Store Bot v6.0\n\n"
        "REGISTRAR PRENDAS\n"
        "/sinfoto - Registrar prenda sin foto (paso a paso)\n"
        "/adjfoto - Adjuntar foto a prenda ya registrada\n\n"
        "VENTAS Y STOCK\n"
        "/venta   - Registrar venta (carrito, separaciones)\n"
        "/prenda  - Consultar detalle de una prenda\n"
        "/devolucion - Devolver venta y restaurar stock\n"
        "/gasto   - Registrar gasto (pasajes, empaque, etc.)\n"
        "/agotados - Lista prendas sin stock\n\n"
        "VER Y CONSULTAS\n"
        "/verfoto    - Ver la foto de una prenda\n"
        "/inventario - Ver todas las prendas del inventario\n\n"
        "FINANZAS\n"
        "/resumen    - Resumen financiero completo\n"
        "/comparar   - Comparar 2 o mas prendas\n"
        "/pormargen  - Ranking por rentabilidad\n"
        "/portienda  - Resumen agrupado por tienda\n\n"
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

def teclado_lista_clientes(clientes: list, pagina: int = 0, por_pagina: int = 30) -> InlineKeyboardMarkup:
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
