from config import *
# ============================================================
# HELPERS — LOGICA DE NEGOCIO
# ============================================================
def calcular_estado(stock: int) -> str:
    if stock <= 0:
        return "Agotado"
    elif stock <= 3:
        return "Stock limitado"
    return "Disponible"

def _parsear_resultados_notion(pages: list) -> list:
    resultados = []
    seen_ids = set()
    for page in pages:
        if page["id"] in seen_ids:
            continue
        seen_ids.add(page["id"])
        props     = page["properties"]
        titulo    = props.get("Prenda", {}).get("title", [])
        nombre    = titulo[0]["text"]["content"] if titulo else ""
        tienda_rt = props.get("Tienda", {}).get("rich_text", [])
        fecha_d   = props.get("Fecha Compra", {}).get("date") or {}
        _stock     = props.get("Stock",          {}).get("number", 0) or 0
        _stock_ini = props.get("Stock Inicial",  {}).get("number", 0) or _stock
        _costo     = props.get("Costo",          {}).get("number", 0) or 0
        _costo_u   = props.get("Costo Unitario", {}).get("number", 0) or 0
        # Si Costo Unitario está vacío, calcularlo desde Costo / Stock Inicial
        if _costo_u == 0 and _costo > 0 and _stock_ini > 0:
            _costo_u = round(_costo / _stock_ini, 2)
        resultados.append({
            "id":            page["id"],
            "nombre":        nombre,
            "stock":         _stock,
            "stock_inicial": _stock_ini,
            "precio":        props.get("Precio", {}).get("number", 0) or 0,
            "costo":         _costo,
            "costo_u":       _costo_u,
            "tienda":        tienda_rt[0]["text"]["content"] if tienda_rt else "",
            "fecha":         fecha_d.get("start", ""),
        })
    return resultados

async def buscar_prendas_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_buscar_prendas_notion, *args, **kwargs))

def _sync_buscar_prendas_notion(termino: str) -> list:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    variantes = list(dict.fromkeys([
        termino, termino.lower(), termino.upper(), termino.capitalize(), termino.title(),
    ]))
    todas_pages = []
    for variante in variantes:
        payload = {
            "filter": {"property": "Prenda", "title": {"contains": variante}},
            "page_size": 15,
        }
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if r.status_code == 200:
            todas_pages.extend(r.json().get("results", []))
    return _parsear_resultados_notion(todas_pages)

async def actualizar_stock_notion(page_id: str, nuevo_stock: int) -> bool:
    import asyncio, functools
    return await asyncio.to_thread(_sync_actualizar_prenda_notion, page_id, {"Stock": {"number": nuevo_stock}})


async def actualizar_prenda_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_actualizar_prenda_notion, *args, **kwargs))

def _sync_actualizar_prenda_notion(page_id: str, cambios: dict) -> bool:
    if "Stock" in cambios:
        nuevo_stock = cambios["Stock"]["number"]
        cambios["Estado"] = {"select": {"name": calcular_estado(nuevo_stock)}}
    payload = {"properties": cambios}
    if "Foto" in cambios:
        foto_url = cambios["Foto"].get("url")
        if foto_url:
            payload["cover"] = {"type": "external", "external": {"url": foto_url}}
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json=payload
    , timeout=15)
    if r.status_code != 200:
        print(f"ERROR NOTION actualizar {r.status_code}: {r.text}")
    return r.status_code == 200

async def crear_prenda_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_crear_prenda_notion, *args, **kwargs))

def _sync_crear_prenda_notion(nombre, costo, precio, stock,
                        foto_url=None, tienda=None, fecha_compra=None) -> bool:
    costo_unitario = round(costo / stock, 2) if stock > 0 else 0
    props = {
        "Prenda":         {"title": [{"text": {"content": nombre}}]},
        "Costo":          {"number": costo},
        "Costo Unitario": {"number": costo_unitario},
        "Precio":         {"number": precio},
        "Stock":          {"number": stock},
        "Stock Inicial":  {"number": stock},
        "Estado":         {"select": {"name": calcular_estado(stock)}},
    }
    if foto_url:
        props["Foto"] = {"url": foto_url}
    if tienda:
        props["Tienda"] = {"rich_text": [{"text": {"content": tienda}}]}
    if fecha_compra:
        props["Fecha Compra"] = {"date": {"start": fecha_compra}}
    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": props}
    if foto_url:
        payload["cover"] = {"type": "external", "external": {"url": foto_url}}
    r = requests.post("https://api.notion.com/v1/pages", headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        print(f"ERROR NOTION crear {r.status_code}: {r.text}")
        return None
    return r.json().get("id")

async def subir_imagen(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_subir_imagen, *args, **kwargs))

def _sync_subir_imagen(image_bytes: bytes):
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    r = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": encoded}
    , timeout=15)
    if r.status_code == 200:
        return r.json()["data"]["url"]
    print(f"ERROR ImgBB {r.status_code}: {r.text}")
    return None

async def obtener_foto_url(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_obtener_foto_url, *args, **kwargs))

def _sync_obtener_foto_url(page_id: str):
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    props = r.json().get("properties", {})
    foto  = props.get("Foto", {}).get("url")
    if foto:
        return foto
    cover = r.json().get("cover") or {}
    if cover.get("type") == "external":
        return cover["external"].get("url")
    return None

def calcular_precio_sugerido(costo: float) -> float:
    if costo <= 5:
        margen = 1.00
    elif costo <= 10:
        margen = 0.70
    elif costo <= 20:
        margen = 0.60
    else:
        margen = 0.50
    return round(costo * (1 + margen), 1)

def parsear_caption(caption: str):
    partes = [p.strip() for p in caption.split(",")]
    if len(partes) < 4:
        return None
    try:
        nombre = partes[0]
        costo  = float(partes[1])
        precio = None if partes[2].strip() == "-" else float(partes[2])
        stock  = int(partes[3])
        tienda = partes[4] if len(partes) > 4 else None
        fecha  = None
        if len(partes) > 5:
            try:
                fecha = datetime.strptime(partes[5].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                fecha = None
        return nombre, costo, precio, stock, tienda, fecha
    except (ValueError, IndexError):
        return None

def resumen_prenda(nombre, costo, precio, stock, tienda=None, fecha=None) -> str:
    ganancia   = precio - (costo / stock) if stock > 0 else 0
    costo_unit = round(costo / stock, 2) if stock > 0 else 0
    margen     = (ganancia / costo_unit * 100) if costo_unit > 0 else 0
    estado     = calcular_estado(stock)
    partes = [
        "Guardado en Notion!",
        "",
        f"Prenda: {nombre}",
        f"Costo total: S/{costo:.0f}",
        f"Costo unitario: S/{costo_unit:.2f}",
        f"Precio venta: S/{precio:.0f}",
        f"Stock inicial: {stock} unidades",
        f"Estado: {estado}",
        f"Ganancia por unidad: S/{ganancia:.0f} ({margen:.0f}%)",
    ]
    if tienda:
        partes.append(f"Tienda: {tienda}")
    if fecha:
        fecha_fmt = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
        partes.append(f"Fecha de compra: {fecha_fmt}")
    return "\n".join(partes)

async def fetch_tiendas_registradas() -> list:
    """Devuelve lista de tiendas únicas que ya existen en el inventario."""
    prendas = await fetch_inventario_completo()
    if not prendas:
        return []
    tiendas = sorted({p.get("tienda","").strip() for p in prendas if p.get("tienda","").strip()})
    return tiendas

async def fetch_resumen_ventas_real(*args, **kwargs):
    import asyncio, functools
    return await asyncio.to_thread(functools.partial(_sync_fetch_resumen_ventas_real, *args, **kwargs))

def _sync_fetch_resumen_ventas_real() -> dict:
    """Consulta la BD de Ventas real para obtener ingresos, ganancias y unidades REALES."""
    if not NOTION_VENTAS_ID:
        return {"uds": 0, "ingresos": 0, "ganancia": 0}
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    total_uds = 0
    total_ingresos = 0
    total_ganancia = 0
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        for page in data.get("results", []):
            props = page["properties"]
            cantidad = props.get("Cantidad", {}).get("number", 0) or 0
            ganancia = props.get("Ganancia", {}).get("number", 0) or 0
            costo_u_v = props.get("Costo unitario", {}).get("number", 0) or 0
            # Calcular ingresos reales desde ganancia + costo (fiable siempre)
            total_uds += cantidad
            total_ingresos += ganancia + (costo_u_v * cantidad)
            total_ganancia += ganancia
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return {
        "uds": total_uds,
        "ingresos": round(total_ingresos, 2),
        "ganancia": round(total_ganancia, 2),
    }

async def fetch_inventario_completo(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_fetch_inventario_completo, *args, **kwargs))

def _sync_fetch_inventario_completo():
    url     = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {"sorts": [{"property": "Prenda", "direction": "ascending"}]}
    pages   = []
    prendas = []
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        for page in data.get("results", []):
            props      = page["properties"]
            titulo     = props.get("Prenda", {}).get("title", [])
            nombre     = titulo[0]["text"]["content"] if titulo else "Sin nombre"
            stock      = props.get("Stock",          {}).get("number", 0) or 0
            stock_ini  = props.get("Stock Inicial",  {}).get("number", 0) or stock
            precio     = props.get("Precio",         {}).get("number", 0) or 0
            costo      = props.get("Costo",          {}).get("number", 0) or 0
            costo_u    = props.get("Costo Unitario", {}).get("number", 0) or 0
            # Fallback: calcular costo_u si el campo está vacío
            if costo_u == 0 and costo > 0 and stock_ini > 0:
                costo_u = round(costo / stock_ini, 2)
            tienda_rt  = props.get("Tienda",         {}).get("rich_text", [])
            tienda     = tienda_rt[0]["text"]["content"] if tienda_rt else ""
            fecha_d    = props.get("Fecha Compra",   {}).get("date") or {}
            fecha      = fecha_d.get("start", "")
            estado     = calcular_estado(stock)
            vendidas   = max(0, stock_ini - stock)
            ganancia_u = precio - costo_u
            margen     = round(ganancia_u / costo_u * 100, 1) if costo_u > 0 else 0
            ingreso_real   = vendidas * precio
            ganancia_real  = vendidas * ganancia_u
            valor_restante = stock * precio
            inversion_rest = stock * costo_u
            prendas.append({
                "id": page["id"], "nombre": nombre, "stock": stock,
                "stock_ini": stock_ini, "vendidas": vendidas, "precio": precio,
                "costo": costo, "costo_u": costo_u, "ganancia_u": ganancia_u,
                "margen": margen, "ingreso_real": ingreso_real,
                "ganancia_real": ganancia_real, "valor_restante": valor_restante,
                "inversion_rest": inversion_rest, "tienda": tienda, "fecha": fecha,
                "estado": estado,
            })
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]
    return prendas

async def historial_ventas_prenda(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_historial_ventas_prenda, *args, **kwargs))

def _sync_historial_ventas_prenda(nombre_prenda: str) -> dict:
    if not NOTION_VENTAS_ID:
        return {}
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {
        "filter": {"property": "Prenda", "rich_text": {"contains": nombre_prenda[:20]}},
        "sorts": [{"property": "Fecha", "direction": "ascending"}],
        "page_size": 100
    }
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return {}
    resultados = r.json().get("results", [])
    ventas = []
    for page in resultados:
        props = page.get("properties", {})
        try:
            prenda_r = props.get("Prenda", {}).get("rich_text", [])
            nombre_v = prenda_r[0]["text"]["content"] if prenda_r else ""
            if nombre_prenda.lower() not in nombre_v.lower():
                continue
            fecha_d  = props.get("Fecha", {}).get("date") or {}
            fecha    = fecha_d.get("start", "")[:10]
            cantidad = props.get("Cantidad",    {}).get("number") or 0
            precio_r = props.get("Precio Venta", {}).get("number") or 0
            ganancia = props.get("Ganancia",    {}).get("number") or 0
            cliente  = ""
            cliente_r = props.get("Cliente", {}).get("rich_text", [])
            if cliente_r:
                cliente = cliente_r[0]["text"]["content"]
            ventas.append({"fecha": fecha, "cantidad": cantidad,
                           "precio_real": precio_r, "ganancia": ganancia, "cliente": cliente})
        except Exception:
            continue
    total_uds      = sum(v["cantidad"] for v in ventas)
    total_ganancia = sum(v["ganancia"] for v in ventas)
    clientes_unicos = len({v["cliente"] for v in ventas if v["cliente"]})
    return {
        "ventas": ventas, "total_uds": total_uds,
        "total_ganancia": total_ganancia, "clientes_unicos": clientes_unicos,
        "num_transacciones": len(ventas),
    }

async def crear_venta_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_crear_venta_notion, *args, **kwargs))

def _sync_crear_venta_notion(prenda_id, cantidad, precio_final, ganancia, 
                            cliente="", fecha_iso=None, descuento=0.0, estado="Completado") -> bool:
    if not NOTION_VENTAS_ID:
        return True
    
    # Obtener nombre de la prenda (para el título de la fila)
    r_prenda = requests.get(f"https://api.notion.com/v1/pages/{prenda_id}", headers=NOTION_HEADERS, timeout=15)
    nombre_prenda = "Prenda"
    costo_u = 0
    if r_prenda.status_code == 200:
        props_p = r_prenda.json().get("properties", {})
        tit = props_p.get("Prenda", {}).get("title", [])
        if tit: nombre_prenda = tit[0]["text"]["content"]
        costo_u = props_p.get("Costo Unitario", {}).get("number", 0) or 0

    from datetime import datetime, timezone
    fecha = fecha_iso or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    url  = "https://api.notion.com/v1/pages"
    data = {
        "parent": {"database_id": NOTION_VENTAS_ID},
        "properties": {
            "Venta":         {"title": [{"text": {"content": f"Venta {nombre_prenda}"}}]},
            "Fecha":         {"date": {"start": fecha}},
            "Prenda":        {"rich_text": [{"text": {"content": nombre_prenda}}]},
            "Cantidad":      {"number": cantidad},
            "Precio Venta":  {"number": precio_final},
            "Costo unitario":{"number": round(costo_u, 2)},
            "Descuento":     {"number": round(descuento, 2)},
            "Ganancia":      {"number": round(ganancia, 2)},
            "Cliente":       {"rich_text": [{"text": {"content": cliente}}]},
            "Estado":        {"select": {"name": estado}},
        }
    }
    r = requests.post(url, headers=NOTION_HEADERS, json=data, timeout=15)
    if r.status_code not in (200, 201):
        logger.error(f"Error Notion Ventas {r.status_code}: {r.text[:300]}")
        return False
    return True

async def obtener_clientes_previos():
    import asyncio, functools
    return await asyncio.to_thread(_sync_obtener_clientes_previos)

def _sync_obtener_clientes_previos() -> list:
    if not NOTION_VENTAS_ID: return []
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {"page_size": 100}
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200: return []
    
    clientes = set()
    for res in r.json().get("results", []):
        c_rt = res["properties"].get("Cliente", {}).get("rich_text", [])
        if c_rt:
            clientes.add(c_rt[0]["text"]["content"].strip())
    return sorted(list(clientes))


async def eliminar_venta_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_eliminar_venta_notion, *args, **kwargs))

def _sync_eliminar_venta_notion(page_id: str) -> bool:
    """Elimina un registro de venta de Notion y restaura el stock de la prenda."""
    # Primero obtener datos de la venta para restaurar stock
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS, timeout=15)
    if r.status_code != 200:
        return False
    props    = r.json().get("properties", {})
    prenda_n = props.get("Prenda", {}).get("rich_text", [])
    cantidad = props.get("Cantidad", {}).get("number", 0) or 0
    nombre   = prenda_n[0]["text"]["content"] if prenda_n else ""
    # Archivar (eliminar) la venta en Notion
    r2 = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=NOTION_HEADERS,
        json={"archived": True}
    , timeout=15)
    if r2.status_code != 200:
        return False
    # Restaurar stock en inventario
    if nombre and cantidad > 0:
        prendas = _sync_buscar_prendas_notion(nombre)
        if prendas:
            stock_actual = prendas[0]["stock"]
            _sync_actualizar_prenda_notion(prendas[0]["id"], {"Stock": {"number": stock_actual + cantidad}})
    return True

async def buscar_ventas_notion(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_buscar_ventas_notion, *args, **kwargs))

def _sync_buscar_ventas_notion(termino: str) -> list:
    """Busca ventas recientes en la BD de ventas por nombre de prenda."""
    if not NOTION_VENTAS_ID:
        return []
    url     = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {
        "sorts": [{"property": "Fecha", "direction": "descending"}],
        "page_size": 20,
    }
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return []
    resultados = []
    for page in r.json().get("results", []):
        props    = page["properties"]
        prenda_n = props.get("Prenda", {}).get("rich_text", [])
        nombre   = prenda_n[0]["text"]["content"] if prenda_n else ""
        if termino.lower() in nombre.lower() or not termino:
            cantidad = props.get("Cantidad", {}).get("number", 0) or 0
            precio   = props.get("Precio Venta", {}).get("number", 0) or 0
            fecha_d  = props.get("Fecha", {}).get("date") or {}
            fecha    = fecha_d.get("start", "")
            resultados.append({
                "id":       page["id"],
                "nombre":   nombre,
                "cantidad": cantidad,
                "precio":   precio,
                "fecha":    fecha,
                "label":    f"{nombre} | {cantidad}ud x S/{precio:.0f} | {fecha}",
            })
    return resultados

async def fetch_ventas_pendientes(*args, **kwargs):
    import asyncio, functools
    return await asyncio.to_thread(functools.partial(_sync_fetch_ventas_pendientes, *args, **kwargs))

def _sync_fetch_ventas_pendientes() -> list:
    """Busca ventas con Estado = Pendiente."""
    if not NOTION_VENTAS_ID:
        return []
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {
        "filter": {"property": "Estado", "select": {"equals": "Pendiente"}},
        "sorts": [{"property": "Fecha", "direction": "descending"}],
        "page_size": 50,
    }
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return []
    resultados = []
    for page in r.json().get("results", []):
        props    = page["properties"]
        prenda_n = props.get("Prenda", {}).get("rich_text", [])
        nombre   = prenda_n[0]["text"]["content"] if prenda_n else ""
        cantidad = props.get("Cantidad", {}).get("number", 0) or 0
        precio   = props.get("Precio Venta", {}).get("number", 0) or 0
        fecha_d  = props.get("Fecha", {}).get("date") or {}
        fecha    = fecha_d.get("start", "")
        cliente_rt = props.get("Cliente", {}).get("rich_text", [])
        cliente    = cliente_rt[0]["text"]["content"] if cliente_rt else ""
        resultados.append({
            "id":       page["id"],
            "nombre":   nombre,
            "cantidad": cantidad,
            "precio":   precio,
            "fecha":    fecha,
            "cliente":  cliente,
            "label":    f"{nombre} | {cantidad}ud x S/{precio:.0f} | {fecha}" + (f" | {cliente}" if cliente else ""),
        })
    return resultados

async def actualizar_estado_venta(*args, **kwargs):
    import asyncio, functools
    return await asyncio.to_thread(functools.partial(_sync_actualizar_estado_venta, *args, **kwargs))

def _sync_actualizar_estado_venta(page_id: str, nuevo_estado: str = "Completado") -> bool:
    """Actualiza el campo Estado de una venta en Notion."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    data = {"properties": {"Estado": {"select": {"name": nuevo_estado}}}}
    r = requests.patch(url, headers=NOTION_HEADERS, json=data, timeout=15)
    if r.status_code != 200:
        logger.error(f"Error actualizando estado venta {r.status_code}: {r.text[:300]}")
        return False
    return True

async def _formato_stock(prenda: dict) -> str:
    estado      = calcular_estado(prenda["stock"])
    stock_ini   = prenda.get("stock_inicial", 0) or prenda["stock"]
    vendidas    = max(0, stock_ini - prenda["stock"])
    pct_vendido = round(vendidas / stock_ini * 100) if stock_ini > 0 else 0
    costo_u     = prenda.get("costo_u", 0) or 0
    costo_total = prenda.get("costo", 0) or 0
    ganancia_u  = prenda["precio"] - costo_u if costo_u > 0 else 0
    margen      = round(ganancia_u / costo_u * 100) if costo_u > 0 else 0
    tienda      = prenda.get("tienda", "") or ""
    fecha       = prenda.get("fecha", "") or ""
    lineas = [
        f"📦 {prenda['nombre']}", "",
        f"Stock actual:    {prenda['stock']} uds",
        f"Stock inicial:   {stock_ini} uds",
        f"Vendidas:        {vendidas} uds ({pct_vendido}%)",
        f"Estado:          {estado}", "",
        f"Precio venta:    S/{prenda['precio']:.0f}",
        f"Costo unitario:  S/{costo_u:.2f}",
        f"Costo total:     S/{costo_total:.0f}",
        f"Ganancia/ud:     S/{ganancia_u:.0f} ({margen}%)",
    ]
    if tienda:
        lineas.append(f"Tienda:          {tienda}")
    if fecha:
        lineas.append(f"Fecha compra:    {fecha}")
    hist = await historial_ventas_prenda(prenda["nombre"])
    if hist and hist.get("num_transacciones", 0) > 0:
        lineas += ["", "─── Historial de ventas ───",
                   f"Transacciones:   {hist['num_transacciones']}",
                   f"Uds vendidas:    {hist['total_uds']}"]
        if hist.get("clientes_unicos", 0) > 0:
            lineas.append(f"Clientes únicos: {hist['clientes_unicos']}")
            nombres = sorted({v["cliente"] for v in hist["ventas"] if v["cliente"]})
            if nombres:
                lineas.append("Compradoras:     " + ", ".join(nombres))
        lineas.append(f"Ganancia total:  S/{hist['total_ganancia']:.0f}")
        if hist['total_uds'] > 0:
            gan_prom = hist['total_ganancia'] / hist['total_uds']
            lineas.append(f"Ganancia/ud:     S/{gan_prom:.0f}")
        lineas.append("")
        for v in hist["ventas"]:
            fecha_fmt  = v["fecha"][5:7] + "/" + v["fecha"][8:10] + "/" + v["fecha"][:4]
            cliente_str = f" — {v['cliente']}" if v["cliente"] else ""
            lineas.append(f"  {fecha_fmt}  {v['cantidad']} ud  S/{v['precio_real']:.0f}  +S/{v['ganancia']:.0f}{cliente_str}")
    else:
        lineas += ["", "Sin ventas registradas aún."]
    return "\n".join(lineas)

async def _texto_agotados(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync__texto_agotados, *args, **kwargs))

def _sync__texto_agotados() -> str:
    url     = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {"page_size": 50}
    r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return f"Error al consultar Notion ({r.status_code})."
    resultados = r.json().get("results", [])
    agotadas = []
    for page in resultados:
        props  = page["properties"]
        stock  = props.get("Stock",  {}).get("number")
        estado = props.get("Estado", {}).get("select") or {}
        nombre_data = props.get("Prenda", {}).get("title", [])
        nombre = nombre_data[0]["text"]["content"] if nombre_data else "Sin nombre"
        precio = props.get("Precio", {}).get("number", 0) or 0
        es_agotada = (stock is None or stock == 0 or estado.get("name") == "Agotado")
        if es_agotada:
            agotadas.append({"nombre": nombre, "precio": precio})
    if not agotadas:
        return "Todo bien! No hay prendas agotadas ahora mismo."
    lineas = [f"Prendas agotadas ({len(agotadas)}):\n"]
    for p in agotadas:
        lineas.append(f"- {p['nombre']} - S/{p['precio']:.0f}")
    return "\n".join(lineas)

# ============================================================
# GRÁFICOS
# ============================================================
async def generar_grafico_stock(*args, **kwargs):
    import asyncio
    import functools
    return await asyncio.to_thread(functools.partial(_sync_generar_grafico_stock, *args, **kwargs))

def _sync_generar_grafico_stock() -> io.BytesIO | None:
    prendas = _sync_fetch_inventario_completo()
    if not prendas:
        return None
    prendas = sorted(prendas, key=lambda p: p["stock"], reverse=True)
    nombres = [p["nombre"][:22] + "…" if len(p["nombre"]) > 22 else p["nombre"] for p in prendas]
    stocks  = [p["stock"] for p in prendas]
    estados = [calcular_estado(p["stock"]) for p in prendas]
    colores_map = {"Disponible": "#2e7d32", "Stock limitado": "#f9a825", "Agotado": "#c62828"}
    colores = [colores_map.get(e, "#999") for e in estados]
    alto = max(4, len(prendas) * 0.45)
    fig, ax = plt.subplots(figsize=(9, alto))
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")
    bars = ax.barh(nombres, stocks, color=colores, edgecolor="white", height=0.65)
    for bar, val in zip(bars, stocks):
        x_pos = bar.get_width()
        ax.text(x_pos + 0.15, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=9, color="#333", fontweight="bold")
    ax.set_xlabel("Unidades en stock", fontsize=10, color="#555")
    ax.set_title("Stock actual por prenda — Maricuchis Store", fontsize=13, fontweight="bold", color="#222")
    ax.invert_yaxis()
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    leyenda = [
        mpatches.Patch(color="#2e7d32", label="Disponible"),
        mpatches.Patch(color="#f9a825", label="Stock limitado (1–3)"),
        mpatches.Patch(color="#c62828", label="Agotado"),
    ]
    ax.legend(handles=leyenda, loc="lower right", fontsize=8, framealpha=0.6)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


async def crear_gasto_notion(nombre: str, monto: float, fecha_iso: str) -> bool:
    import asyncio, functools
    return await asyncio.to_thread(functools.partial(_sync_crear_gasto_notion, nombre, monto, fecha_iso))

def _sync_crear_gasto_notion(nombre: str, monto: float, fecha_iso: str) -> bool:
    import requests
    from config import NOTION_HEADERS, NOTION_GASTOS_ID
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_GASTOS_ID},
        "properties": {
            "Nombre": {"title": [{"text": {"content": nombre}}]},
            "Monto": {"number": monto},
            "Fecha": {"date": {"start": fecha_iso}}
        }
    }
    try:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False
