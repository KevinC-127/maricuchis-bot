"""
dashboard.py — Maricuchis Store Dashboard Financiero
Servidor web ligero que corre junto al bot de Telegram.
Accesible en: https://<tu-railway-url>/
"""
import os
import asyncio
import pathlib
import requests as req
from aiohttp import web
from config import NOTION_HEADERS, NOTION_DATABASE_ID, NOTION_VENTAS_ID, NOTION_GASTOS_ID, logger

PORT = int(os.environ.get("PORT", 8080))

# ============================================================
# DATOS — Leer de las 3 bases de datos de Notion
# ============================================================
def _sync_get_stats() -> dict:
    # ── INVENTARIO ──────────────────────────────────────────
    total_inversion = 0
    total_stock = 0
    total_prendas = 0
    stock_stats = {"Disponible": 0, "Stock bajo": 0, "Agotado": 0}
    top_inventario = []
    fotos_map = {}
    inv_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = req.post(inv_url, headers=NOTION_HEADERS, json=payload, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        for page in data.get("results", []):
            props = page["properties"]
            tit = props.get("Prenda", {}).get("title", [])
            nombre = tit[0]["text"]["content"] if tit else "Sin nombre"
            stock = props.get("Stock", {}).get("number", 0) or 0
            costo_u = props.get("Costo Unitario", {}).get("number", 0) or 0
            precio = props.get("Precio", {}).get("number", 0) or 0
            total_prendas += 1
            
            foto_url = ""
            foto_files = props.get("Foto", {}).get("files", [])
            if foto_files:
                if foto_files[0].get("file"): foto_url = foto_files[0]["file"]["url"]
                elif foto_files[0].get("external"): foto_url = foto_files[0]["external"]["url"]
            if not foto_url and page.get("cover"):
                cover = page["cover"]
                if cover.get("file"): foto_url = cover["file"]["url"]
                elif cover.get("external"): foto_url = cover["external"]["url"]
                
            fotos_map[nombre] = foto_url
            
            # Stock Status
            if stock == 0: stock_stats["Agotado"] += 1
            elif stock <= 3: stock_stats["Stock bajo"] += 1
            else: stock_stats["Disponible"] += 1

            total_stock += stock
            total_inversion += stock * costo_u
            top_inventario.append({
                "nombre": nombre, "stock": stock,
                "precio": precio, "costo_u": costo_u,
                "valor": round(stock * costo_u, 2)
            })
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    top_inventario.sort(key=lambda x: x["valor"], reverse=True)

    # ── VENTAS ──────────────────────────────────────────────
    total_precio_venta = 0
    total_precio_costo = 0
    total_uds_vendidas = 0
    total_descuentos = 0
    num_ventas = 0
    pendientes = 0
    ventas_por_mes = {}
    ventas_por_dia = {}
    prendas_vendidas = {}
    from datetime import datetime, timedelta
    fecha_limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    if NOTION_VENTAS_ID:
        ven_url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
        cursor = None
        while True:
            payload = {"page_size": 100, "sorts": [{"property": "Fecha", "direction": "descending"}]}
            if cursor:
                payload["start_cursor"] = cursor
            r = req.post(ven_url, headers=NOTION_HEADERS, json=payload, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            for page in data.get("results", []):
                props = page["properties"]
                cantidad = props.get("Cantidad", {}).get("number", 0) or 0
                # precio_venta not used currently
                costo_u = props.get("Costo unitario", {}).get("number", 0) or 0
                ganancia = props.get("Ganancia", {}).get("number", 0) or 0
                descuento = props.get("Descuento", {}).get("number", 0) or 0
                estado_sel = props.get("Estado", {}).get("select") or {}
                estado = estado_sel.get("name", "Completado")
                fecha_d = (props.get("Fecha", {}).get("date") or {})
                full_fecha = fecha_d.get("start", "")
                mes = full_fecha[:7]
                prenda_rt = props.get("Prenda", {}).get("rich_text", [])
                prenda_nom = prenda_rt[0]["text"]["content"] if prenda_rt else ""
                cliente_rt = props.get("Cliente", {}).get("rich_text", [])
                cliente_nom = cliente_rt[0]["text"]["content"] if cliente_rt else "Desconocido"
                
                es_completada = estado != "Pendiente"
                ganancia_efectiva = ganancia if es_completada else 0
                ingreso_linea = (ganancia_efectiva + (costo_u * cantidad)) if es_completada else 0
                costo_linea = costo_u * cantidad
                
                total_precio_venta += ingreso_linea
                total_precio_costo += costo_linea if es_completada else 0
                total_uds_vendidas += cantidad
                total_descuentos += descuento
                num_ventas += 1
                if not es_completada:
                    pendientes += 1
                if prenda_nom:
                    prendas_vendidas[prenda_nom] = prendas_vendidas.get(prenda_nom, 0) + cantidad
                
                if mes:
                    if mes not in ventas_por_mes:
                        ventas_por_mes[mes] = {"ingresos": 0, "costo": 0, "ganancia": 0, "uds": 0, "descuentos": 0, "ventas": 0}
                    ventas_por_mes[mes]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_mes[mes]["costo"] += round(costo_linea, 2)
                    ventas_por_mes[mes]["ganancia"] += round(ganancia_efectiva, 2)
                    ventas_por_mes[mes]["uds"] += cantidad
                    ventas_por_mes[mes]["descuentos"] += round(descuento, 2)
                    ventas_por_mes[mes]["ventas"] += 1
                
                if full_fecha:
                    if full_fecha not in ventas_por_dia:
                        ventas_por_dia[full_fecha] = {"ingresos": 0, "ganancia": 0, "uds": 0, "costo": 0, "ventas": 0, "detalle": []}
                    ventas_por_dia[full_fecha]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_dia[full_fecha]["ganancia"] += round(ganancia_efectiva, 2)
                    ventas_por_dia[full_fecha]["costo"] += round(costo_linea, 2)
                    ventas_por_dia[full_fecha]["uds"] += cantidad
                    ventas_por_dia[full_fecha]["ventas"] += 1
                    if prenda_nom:
                        ventas_por_dia[full_fecha]["detalle"].append({
                            "nombre": prenda_nom,
                            "cliente": cliente_nom,
                            "uds": cantidad
                        })

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    # Top vendidas
    top_vendidas = sorted(prendas_vendidas.items(), key=lambda x: x[1], reverse=True)[:8]

    # ── GASTOS ──────────────────────────────────────────────
    total_gastos = 0
    gastos_lista = []
    if NOTION_GASTOS_ID:
        gas_url = f"https://api.notion.com/v1/databases/{NOTION_GASTOS_ID}/query"
        r = req.post(gas_url, headers=NOTION_HEADERS, json={"page_size": 100}, timeout=15)
        if r.status_code == 200:
            for page in r.json().get("results", []):
                props = page["properties"]
                monto = props.get("Monto", {}).get("number", 0) or 0
                nom_t = props.get("Nombre", {}).get("title", [])
                nombre = nom_t[0]["text"]["content"] if nom_t else "Gasto"
                fecha_g = (props.get("Fecha", {}).get("date") or {}).get("start", "")
                total_gastos += monto
                gastos_lista.append({"nombre": nombre, "monto": round(monto, 2), "fecha": fecha_g})
    gastos_lista.sort(key=lambda x: x["monto"], reverse=True)

    ganancia_bruta = total_precio_venta - total_precio_costo
    ganancia_neta  = ganancia_bruta - total_gastos

    meses_sorted = sorted(ventas_por_mes.keys())[-6:]
    dias_sorted = sorted(ventas_por_dia.keys())
    
    return {
        "precio_costo":     round(total_precio_costo, 2),
        "precio_venta":     round(total_precio_venta, 2),
        "ganancia_bruta":   round(ganancia_bruta, 2),
        "ganancia_neta":    round(ganancia_neta, 2),
        "gastos":           round(total_gastos, 2),
        "descuentos":       round(total_descuentos, 2),
        "inversion":        round(total_inversion, 2),
        "inventario_uds":   total_stock,
        "total_prendas":    total_prendas,
        "uds_vendidas":     total_uds_vendidas,
        "num_ventas":       num_ventas,
        "pendientes":       pendientes,
        "stock_stats":      stock_stats,
        "top_inventario":   top_inventario[:8],
        "top_vendidas":     [{"nombre": n, "uds": u} for n, u in top_vendidas],
        "gastos_lista":     gastos_lista[:10],
        "ventas_por_mes":   {m: ventas_por_mes[m] for m in meses_sorted},
        "ventas_por_dia":   {d: ventas_por_dia[d] for d in dias_sorted},
        "fotos_map":        fotos_map,
    }

# ============================================================
# ENDPOINTS
# ============================================================
async def handle_stats(request):
    try:
        data = await asyncio.to_thread(_sync_get_stats)
        return web.json_response(data)
    except Exception as e:
        logger.error(f"Dashboard API error: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_index(request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html", charset="utf-8")

# ============================================================
# ARRANCAR SERVIDOR
# ============================================================
async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get("/", handle_index)
    app_web.router.add_get("/api/stats", handle_stats)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Dashboard corriendo en puerto {PORT}")

# ============================================================
# HTML — Cargar desde archivo externo
# ============================================================
_html_path = pathlib.Path(__file__).parent / "dashboard.html"
DASHBOARD_HTML = _html_path.read_text(encoding="utf-8")
