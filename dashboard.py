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
from config import NOTION_HEADERS, NOTION_DATABASE_ID, NOTION_VENTAS_ID, NOTION_GASTOS_ID, NOTION_BOLETOS_ID, logger

PORT = int(os.environ.get("PORT", 8080))

# ============================================================
# AUTO-BOLETOS — Chequeo periódico de ventas completadas
# ============================================================
_ventas_completadas_procesadas = set()  # page_ids ya procesados
_boleto_checker_initialized = False

def _sync_check_new_completadas():
    """Busca ventas completadas recientes y asigna boletos si no se han asignado."""
    global _boleto_checker_initialized
    if not NOTION_VENTAS_ID:
        return []
    
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    payload = {
        "filter": {"property": "Estado", "select": {"equals": "Completado"}},
        "sorts": [{"property": "Fecha", "direction": "descending"}],
        "page_size": 100,
    }
    r = req.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return []
    
    nuevas = []
    all_ids = set()
    for page in r.json().get("results", []):
        pid = page["id"]
        all_ids.add(pid)
        
        if pid in _ventas_completadas_procesadas:
            continue
        
        if not _boleto_checker_initialized:
            # Primera ejecución: solo registrar IDs existentes, no crear boletos
            continue
        
        props = page["properties"]
        cliente_rt = props.get("Cliente", {}).get("rich_text", [])
        cliente = cliente_rt[0]["text"]["content"].strip() if cliente_rt else ""
        cantidad = props.get("Cantidad", {}).get("number", 0) or 1
        fecha_d = props.get("Fecha", {}).get("date") or {}
        fecha = fecha_d.get("start", "")
        prenda_n = props.get("Prenda", {}).get("rich_text", [])
        prenda = prenda_n[0]["text"]["content"] if prenda_n else "Prenda"
        
        if cliente and cliente.lower() not in ("sin cliente", "anonimo", "anónimo", ""):
            nuevas.append({
                "cliente": cliente,
                "cantidad": cantidad,
                "fecha": fecha,
                "prenda": prenda,
            })
    
    _ventas_completadas_procesadas.update(all_ids)
    
    if not _boleto_checker_initialized:
        _boleto_checker_initialized = True
        logger.info(f"🎟️ Auto-boletos: inicializado con {len(all_ids)} ventas completadas existentes")
    
    return nuevas

async def _boleto_checker_loop():
    """Loop cada 60s que detecta ventas recién completadas y asigna boletos."""
    from notion_api import _sync_crear_boleto_notion
    await asyncio.sleep(10)  # Esperar a que el bot arranque
    
    while True:
        try:
            nuevas = await asyncio.to_thread(_sync_check_new_completadas)
            if nuevas:
                # Agrupar por cliente
                por_cliente = {}
                for v in nuevas:
                    por_cliente[v["cliente"]] = por_cliente.get(v["cliente"], 0) + v["cantidad"]
                
                for cliente, bols in por_cliente.items():
                    await asyncio.to_thread(_sync_crear_boleto_notion,
                        cliente=cliente,
                        boletos=bols,
                        asunto="Auto-asignado al completar venta",
                    )
                    logger.info(f"🎟️ Auto-boletos: {cliente} +{bols} boletos")
        except Exception as e:
            logger.error(f"Auto-boletos error: {e}")
        
        await asyncio.sleep(60)

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
            
            tienda_rt = props.get("Tienda", {}).get("rich_text", [])
            tienda = tienda_rt[0]["text"]["content"] if tienda_rt else "Sin tienda"
            fecha_d = props.get("Fecha Compra", {}).get("date") or {}
            fecha = fecha_d.get("start", "1970-01-01")
            
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
            estado = "Disponible"
            if stock == 0: 
                stock_stats["Agotado"] += 1
                estado = "Agotado"
            elif stock <= 3: 
                stock_stats["Stock bajo"] += 1
                estado = "Stock bajo"
            else: 
                stock_stats["Disponible"] += 1

            total_stock += stock
            total_inversion += stock * costo_u
            top_inventario.append({
                "nombre": nombre, "stock": stock,
                "precio": precio, "costo_u": costo_u,
                "valor": round(stock * costo_u, 2),
                "tienda": tienda, "fecha": fecha, "estado": estado
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
    total_ganancia_pendiente = 0
    num_ventas = 0
    pendientes = 0
    ventas_por_mes = {}
    ventas_por_dia = {}
    prendas_vendidas = {}
    clientes_data = {}
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
                costo_linea = (costo_u * cantidad) if es_completada else 0
                ingreso_linea = (ganancia_efectiva + costo_linea) if es_completada else 0
                ingreso_total = ganancia + (costo_u * cantidad)
                
                total_precio_venta += ingreso_linea
                total_precio_costo += costo_linea
                total_uds_vendidas += cantidad if es_completada else 0
                total_descuentos += descuento if es_completada else 0
                num_ventas += 1
                if not es_completada:
                    pendientes += 1
                    total_ganancia_pendiente += ganancia
                if prenda_nom:
                    prendas_vendidas[prenda_nom] = prendas_vendidas.get(prenda_nom, 0) + cantidad
                if cliente_nom and cliente_nom != "Desconocido" and es_completada:
                    if cliente_nom not in clientes_data:
                        clientes_data[cliente_nom] = {"total_gastado": 0, "uds": 0, "compras": 0}
                    clientes_data[cliente_nom]["total_gastado"] += round(ingreso_linea, 2)
                    clientes_data[cliente_nom]["uds"] += cantidad
                    clientes_data[cliente_nom]["compras"] += 1
                
                if mes:
                    if mes not in ventas_por_mes:
                        ventas_por_mes[mes] = {"ingresos": 0, "costo": 0, "ganancia": 0, "uds": 0, "descuentos": 0, "ventas": 0}
                    ventas_por_mes[mes]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_mes[mes]["costo"] += round(costo_linea, 2)
                    ventas_por_mes[mes]["ganancia"] += round(ganancia_efectiva, 2)
                    ventas_por_mes[mes]["uds"] += (cantidad if es_completada else 0)
                    ventas_por_mes[mes]["descuentos"] += round((descuento if es_completada else 0), 2)
                    ventas_por_mes[mes]["ventas"] += (1 if es_completada else 0)
                
                if full_fecha:
                    if full_fecha not in ventas_por_dia:
                        ventas_por_dia[full_fecha] = {"ingresos": 0, "ingresos_estimados": 0, "ganancia": 0, "ganancia_estimada": 0, "uds": 0, "uds_pendientes": 0, "costo": 0, "ventas": 0, "detalle": []}
                    ventas_por_dia[full_fecha]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_dia[full_fecha]["ingresos_estimados"] += round(ingreso_total, 2)
                    ventas_por_dia[full_fecha]["ganancia"] += round(ganancia_efectiva, 2)
                    ventas_por_dia[full_fecha]["ganancia_estimada"] += round(ganancia, 2)
                    ventas_por_dia[full_fecha]["costo"] += round(costo_linea, 2)
                    ventas_por_dia[full_fecha]["uds"] += cantidad
                    ventas_por_dia[full_fecha]["ventas"] += 1
                    if not es_completada:
                        ventas_por_dia[full_fecha]["uds_pendientes"] += cantidad
                    if prenda_nom:
                        ventas_por_dia[full_fecha]["detalle"].append({
                            "nombre": prenda_nom,
                            "cliente": cliente_nom,
                            "uds": cantidad,
                            "estado": estado,
                            "fecha": full_fecha
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

    # ── BOLETOS ─────────────────────────────────────────────
    boletos_por_clienta = {}
    if NOTION_BOLETOS_ID:
        bol_url = f"https://api.notion.com/v1/databases/{NOTION_BOLETOS_ID}/query"
        cursor = None
        while True:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            r = req.post(bol_url, headers=NOTION_HEADERS, json=payload, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            for page in data.get("results", []):
                props = page["properties"]
                bols = props.get("Boletos", {}).get("number", 0) or 0
                nom_t = props.get("Clienta", {}).get("title", [])
                nombre = nom_t[0]["text"]["content"] if nom_t else "Desconocida"
                if nombre not in boletos_por_clienta:
                    boletos_por_clienta[nombre] = 0
                boletos_por_clienta[nombre] += bols
            cursor = data.get("next_cursor")
            if not cursor:
                break
    
    top_boletos = sorted(boletos_por_clienta.items(), key=lambda x: x[1], reverse=True)

    ganancia_bruta = total_precio_venta - total_precio_costo
    ganancia_neta  = ganancia_bruta - total_gastos

    meses_sorted = sorted(ventas_por_mes.keys())[-6:]
    dias_sorted = sorted(ventas_por_dia.keys())
    
    return {
        "precio_costo":     round(total_precio_costo, 2),
        "precio_venta":     round(total_precio_venta, 2),
        "ganancia_bruta":   round(ganancia_bruta, 2),
        "ganancia_pendiente":round(total_ganancia_pendiente, 2),
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
        "top_inventario":   top_inventario,
        "top_vendidas":     [{"nombre": n, "uds": u} for n, u in top_vendidas],
        "top_boletos":      [{"nombre": n, "boletos": b} for n, b in top_boletos],
        "gastos_lista":     gastos_lista[:10],
        "ventas_por_mes":   {m: ventas_por_mes[m] for m in meses_sorted},
        "ventas_por_dia":   {d: ventas_por_dia[d] for d in dias_sorted},
        "fotos_map":        fotos_map,
        "top_clientes":     sorted([{"nombre": n, **d} for n, d in clientes_data.items()], key=lambda x: x["total_gastado"], reverse=True)[:10],
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
# BOLETO — Token firmado con HMAC
# ============================================================
import hmac
import hashlib
import base64
import json
import time

_BOLETO_SECRET = (os.environ.get("TELEGRAM_TOKEN") or "maricuchis-secret").encode()
_BOLETO_EXPIRY = 3600  # 1 hora

def _sign_boleto(clienta: str, boletos: int) -> str:
    payload = json.dumps({"c": clienta, "b": boletos, "t": int(time.time())}, ensure_ascii=False)
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(_BOLETO_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload_b64}.{sig}"

def _verify_boleto(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None, "Token inválido"
        payload_b64, sig = parts
        expected_sig = hmac.new(_BOLETO_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected_sig):
            return None, "Token inválido"
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        elapsed = int(time.time()) - payload["t"]
        if elapsed > _BOLETO_EXPIRY:
            return None, "expired"
        return payload, None
    except Exception:
        return None, "Token inválido"

async def handle_boleto_link(request):
    clienta = request.query.get("clienta", "")
    boletos = int(request.query.get("boletos", "0"))
    if not clienta:
        return web.json_response({"error": "Falta clienta"}, status=400)
    token = _sign_boleto(clienta, boletos)
    return web.json_response({"token": token})

def _sync_fetch_boleto_history(clienta: str) -> list:
    """Busca todos los registros de boletos de una clienta en Notion."""
    if not NOTION_BOLETOS_ID:
        return []
    url = f"https://api.notion.com/v1/databases/{NOTION_BOLETOS_ID}/query"
    payload = {
        "filter": {"property": "Clienta", "title": {"equals": clienta}},
        "sorts": [{"property": "Fecha", "direction": "descending"}],
        "page_size": 50,
    }
    r = req.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
    if r.status_code != 200:
        return []
    historial = []
    for page in r.json().get("results", []):
        props = page["properties"]
        bols = props.get("Boletos", {}).get("number", 0) or 0
        asunto_rt = props.get("Asunto", {}).get("rich_text", [])
        asunto = asunto_rt[0]["text"]["content"] if asunto_rt else "Compra"
        fecha_d = props.get("Fecha", {}).get("date") or {}
        fecha = fecha_d.get("start", "")
        historial.append({"boletos": bols, "asunto": asunto, "fecha": fecha})
    return historial

async def handle_boleto_page(request):
    token = request.match_info.get("token", "")
    payload, error = _verify_boleto(token)
    if error == "expired":
        html = BOLETO_EXPIRED_HTML
    elif error:
        html = BOLETO_INVALID_HTML
    else:
        remaining = max(0, _BOLETO_EXPIRY - (int(time.time()) - payload["t"]))
        mins = remaining // 60
        # Fetch history
        historial = await asyncio.to_thread(_sync_fetch_boleto_history, payload["c"])
        hist_html = ""
        if historial:
            for h in historial:
                f_parts = h["fecha"].split("-") if h["fecha"] else []
                fecha_fmt = f"{f_parts[2]}/{f_parts[1]}/{f_parts[0]}" if len(f_parts) == 3 else "—"
                hist_html += f'<div class="tx"><div class="tx-left"><div class="tx-asunto">{h["asunto"]}</div><div class="tx-fecha">{fecha_fmt}</div></div><div class="tx-bols">+{h["boletos"]}</div></div>'
        else:
            hist_html = '<div style="text-align:center;color:rgba(255,255,255,0.3);font-size:0.8rem;padding:12px;">Sin registros</div>'
        html = (BOLETO_PAGE_HTML
            .replace("{{CLIENTA}}", payload["c"])
            .replace("{{BOLETOS}}", str(payload["b"]))
            .replace("{{MINS}}", str(mins))
            .replace("{{HISTORIAL}}", hist_html))
    return web.Response(text=html, content_type="text/html", charset="utf-8")

# ============================================================
# ARRANCAR SERVIDOR
# ============================================================
async def start_web_server():
    app_web = web.Application()
    app_web.router.add_get("/", handle_index)
    app_web.router.add_get("/api/stats", handle_stats)
    app_web.router.add_get("/api/boleto-link", handle_boleto_link)
    app_web.router.add_get("/boleto/{token}", handle_boleto_page)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Dashboard corriendo en puerto {PORT}")
    # Iniciar el chequeo automático de boletos
    asyncio.create_task(_boleto_checker_loop())

# ============================================================
# HTML — Cargar desde archivo externo
# ============================================================
_html_path = pathlib.Path(__file__).parent / "dashboard.html"
DASHBOARD_HTML = _html_path.read_text(encoding="utf-8")

# ============================================================
# BOLETO — Páginas HTML públicas
# ============================================================
BOLETO_PAGE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎟️ Boletos de {{CLIENTA}} — Maricuchis Store</title>
<meta property="og:title" content="🎟️ Boletos de {{CLIENTA}}">
<meta property="og:description" content="{{CLIENTA}} tiene {{BOLETOS}} boletos para el sorteo de Maricuchis Store 🌸">
<meta property="og:type" content="website">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px;
background:#0a0a0a;background-image:radial-gradient(circle at 50% 0%,rgba(139,92,246,0.2),transparent 60%);}
.card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:40px;max-width:420px;width:100%;backdrop-filter:blur(20px);text-align:center;animation:fadeIn 0.6s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.logo{font-size:2rem;margin-bottom:8px;}
.store{font-size:1.1rem;font-weight:700;background:linear-gradient(135deg,#f59e0b,#ec4899,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:24px;}
.divider{height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent);margin:20px 0;}
.name{font-size:1.3rem;font-weight:700;color:#fff;margin-bottom:6px;}
.label{font-size:0.8rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;}
.boletos-num{font-size:4rem;font-weight:800;background:linear-gradient(135deg,#f59e0b,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1;}
.boletos-label{font-size:1rem;color:rgba(255,255,255,0.5);margin-top:4px;}
.prizes{margin-top:24px;text-align:left;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px;border:1px solid rgba(255,255,255,0.06);}
.prizes h4{font-size:0.75rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;}
.prize{display:flex;align-items:center;gap:10px;padding:6px 0;font-size:0.85rem;color:rgba(255,255,255,0.7);}
.prize span{font-size:1.1rem;}
.history{margin-top:16px;text-align:left;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px;border:1px solid rgba(255,255,255,0.06);}
.history h4{font-size:0.75rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;}
.tx{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);}
.tx:last-child{border-bottom:none;}
.tx-left{display:flex;flex-direction:column;gap:2px;}
.tx-asunto{font-size:0.8rem;color:rgba(255,255,255,0.7);}
.tx-fecha{font-size:0.65rem;color:rgba(255,255,255,0.3);}
.tx-bols{font-size:0.9rem;font-weight:700;color:#10b981;white-space:nowrap;}
.footer{margin-top:24px;font-size:0.65rem;color:rgba(255,255,255,0.25);line-height:1.5;}
</style>
</head>
<body>
<div class="card">
    <div class="logo">🌸</div>
    <div class="store">Maricuchis Store</div>
    <div class="divider"></div>
    <div class="label">Boletos de</div>
    <div class="name">{{CLIENTA}}</div>
    <div class="divider"></div>
    <div class="boletos-num">{{BOLETOS}}</div>
    <div class="boletos-label">🎟️ boletos para el sorteo</div>
    <div class="prizes">
        <h4>🎁 Premios del sorteo</h4>
        <div class="prize"><span>🥇</span> Paquete de prendas por S/100</div>
        <div class="prize"><span>🥈</span> Paquete de prendas por S/50</div>
        <div class="prize"><span>🥉</span> Paquete de prendas por S/20</div>
    </div>
    <div class="history">
        <h4>📋 Historial de boletos</h4>
        {{HISTORIAL}}
    </div>
    <div class="footer">
        Este enlace es válido por {{MINS}} minutos más.<br>
        Sorteo: Domingo 10 de Mayo a las 7:00 PM 🎉
    </div>
</div>
</body>
</html>"""

BOLETO_EXPIRED_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Link Expirado</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0a0a0a;color:#fff;text-align:center;padding:20px;}
.card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:40px;max-width:380px;}
</style></head><body><div class="card">
<div style="font-size:3rem;margin-bottom:16px;">⏰</div>
<h2 style="margin-bottom:8px;">Link Expirado</h2>
<p style="color:rgba(255,255,255,0.5);font-size:0.9rem;">Este enlace ya no es válido. Solicita uno nuevo a Maricuchis Store.</p>
<div style="margin-top:20px;font-size:1.2rem;">🌸</div>
</div></body></html>"""

BOLETO_INVALID_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Link Inválido</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0a0a0a;color:#fff;text-align:center;padding:20px;}
.card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:40px;max-width:380px;}
</style></head><body><div class="card">
<div style="font-size:3rem;margin-bottom:16px;">❌</div>
<h2 style="margin-bottom:8px;">Link Inválido</h2>
<p style="color:rgba(255,255,255,0.5);font-size:0.9rem;">Este enlace no es válido.</p>
</div></body></html>"""
