"""
dashboard.py — Maricuchis Store Dashboard Financiero
Servidor web ligero que corre junto al bot de Telegram.
Accesible en: https://<tu-railway-url>/
"""
import os
import asyncio
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
    top_inventario = []
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
    ventas_por_mes = {}
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
                precio_real = props.get("Precio real", {}).get("number", 0) or 0
                costo_u = props.get("Costo unitario", {}).get("number", 0) or 0
                fecha_d = (props.get("Fecha", {}).get("date") or {})
                mes = fecha_d.get("start", "")[:7]
                total_precio_venta += precio_real * cantidad
                total_precio_costo += costo_u * cantidad
                if mes:
                    if mes not in ventas_por_mes:
                        ventas_por_mes[mes] = {"ingresos": 0, "costo": 0}
                    ventas_por_mes[mes]["ingresos"] += round(precio_real * cantidad, 2)
                    ventas_por_mes[mes]["costo"] += round(costo_u * cantidad, 2)
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

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
                total_gastos += monto
                gastos_lista.append({"nombre": nombre, "monto": round(monto, 2)})
    gastos_lista.sort(key=lambda x: x["monto"], reverse=True)

    ganancia_bruta = total_precio_venta - total_precio_costo
    ganancia_neta  = ganancia_bruta - total_gastos

    meses_sorted = sorted(ventas_por_mes.keys())[-6:]
    return {
        "precio_costo":     round(total_precio_costo, 2),
        "precio_venta":     round(total_precio_venta, 2),
        "ganancia_bruta":   round(ganancia_bruta, 2),
        "ganancia_neta":    round(ganancia_neta, 2),
        "gastos":           round(total_gastos, 2),
        "inversion":        round(total_inversion, 2),
        "inventario_uds":   total_stock,
        "top_inventario":   top_inventario[:8],
        "gastos_lista":     gastos_lista[:8],
        "ventas_por_mes":   {m: ventas_por_mes[m] for m in meses_sorted},
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
# HTML — Dashboard completo
# ============================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🌸 Maricuchis Store — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--gold:#f59e0b;--green:#10b981;--red:#ef4444;--blue:#60a5fa;--purple:#a78bfa;--orange:#fb923c;--bg1:#0a0416;--bg2:#0d1b2a;--card:rgba(255,255,255,0.05);--border:rgba(255,255,255,0.08)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Poppins',sans-serif;background:linear-gradient(135deg,var(--bg1) 0%,var(--bg2) 100%);min-height:100vh;color:#fff;padding:20px}
.header{text-align:center;margin-bottom:28px}
.header h1{font-size:clamp(1.4rem,4vw,2.2rem);font-weight:800;background:linear-gradient(135deg,#f59e0b,#ec4899,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.header p{color:rgba(255,255,255,0.45);font-size:.85rem;margin-top:4px}
.last-update{color:rgba(255,255,255,0.3);font-size:.72rem;margin-top:6px}
.loading{text-align:center;padding:40px;color:rgba(255,255,255,0.4);font-size:.9rem}
.spinner{width:36px;height:36px;border:3px solid rgba(255,255,255,0.1);border-top-color:#8b5cf6;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}

/* Metric Cards */
.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:22px}
@media(max-width:900px){.metrics{grid-template-columns:repeat(2,1fr)}}
@media(max-width:480px){.metrics{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px 16px;backdrop-filter:blur(12px);transition:transform .2s;position:relative;overflow:hidden}
.card:hover{transform:translateY(-3px)}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:14px 14px 0 0}
.c-gold::before{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.c-blue::before{background:linear-gradient(90deg,#3b82f6,#60a5fa)}
.c-green::before{background:linear-gradient(90deg,#059669,#10b981)}
.c-orange::before{background:linear-gradient(90deg,#ea580c,#fb923c)}
.c-purple::before{background:linear-gradient(90deg,#7c3aed,#a78bfa)}
.card .icon{font-size:1.3rem;margin-bottom:6px}
.card .lbl{font-size:.68rem;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.card .val{font-size:1.5rem;font-weight:700;margin-top:3px;line-height:1.2}
.c-gold .val{color:var(--gold)}
.c-blue .val{color:var(--blue)}
.c-green .val{color:var(--green)}
.c-orange .val{color:var(--orange)}
.c-purple .val{color:var(--purple)}
.card .sub{font-size:.68rem;color:rgba(255,255,255,0.3);margin-top:4px}

/* Charts */
.charts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:20px}
@media(max-width:768px){.charts{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px;backdrop-filter:blur(12px)}
.panel h3{font-size:.9rem;font-weight:600;color:rgba(255,255,255,0.75);margin-bottom:18px;display:flex;align-items:center;gap:8px}
.donut-wrap{position:relative;max-width:260px;margin:0 auto}
.donut-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;pointer-events:none}
.donut-center .big{font-size:1.3rem;font-weight:700;color:#fff}
.donut-center .small{font-size:.65rem;color:rgba(255,255,255,0.4)}
.legend{margin-top:18px;display:flex;flex-direction:column;gap:8px}
.legend-item{display:flex;align-items:center;gap:10px;font-size:.78rem}
.legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}

/* Tables */
.tables{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:768px){.tables{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:.78rem}
thead th{color:rgba(255,255,255,0.4);font-weight:500;text-transform:uppercase;font-size:.66rem;letter-spacing:.05em;padding:6px 8px;border-bottom:1px solid var(--border);text-align:left}
tbody td{padding:8px;border-bottom:1px solid rgba(255,255,255,0.04);color:rgba(255,255,255,0.8)}
tbody tr:last-child td{border-bottom:none}
.tag{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.65rem;font-weight:600}
.tag-green{background:rgba(16,185,129,.15);color:#10b981}
.tag-red{background:rgba(239,68,68,.15);color:#ef4444}
</style>
</head>
<body>
<div class="header">
  <h1>🌸 Maricuchis Store</h1>
  <p>Dashboard Financiero</p>
  <div class="last-update" id="lastUpdate">Cargando datos...</div>
</div>

<div id="app">
  <div class="loading"><div class="spinner"></div>Conectando con Notion...</div>
</div>

<script>
const S = n => `S/ ${Number(n).toLocaleString('es-PE', {minimumFractionDigits:2, maximumFractionDigits:2})}`;
const UDS = n => `${n} uds`;
let donutChart = null, barChart = null;

async function loadData() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Error al conectar');
    const d = await res.json();
    renderDashboard(d);
    document.getElementById('lastUpdate').textContent = 'Actualizado: ' + new Date().toLocaleTimeString('es-PE');
  } catch(e) {
    document.getElementById('app').innerHTML = `<div class="loading" style="color:#ef4444">❌ Error al cargar datos: ${e.message}</div>`;
  }
}

function renderDashboard(d) {
  const ganancia = d.ganancia_neta;
  const esNegativo = ganancia < 0;

  document.getElementById('app').innerHTML = `
  <!-- MÉTRICAS -->
  <div class="metrics">
    <div class="card c-gold">
      <div class="icon">💰</div>
      <div class="lbl">Precio Costo</div>
      <div class="val">${S(d.precio_costo)}</div>
      <div class="sub">Lo que pagaste por lo vendido</div>
    </div>
    <div class="card c-blue">
      <div class="icon">💵</div>
      <div class="lbl">Precio Venta</div>
      <div class="val">${S(d.precio_venta)}</div>
      <div class="sub">Total cobrado a clientes</div>
    </div>
    <div class="card ${esNegativo ? 'c-red' : 'c-green'}" style="${esNegativo?'--green:#ef4444':''}">
      <div class="icon">${esNegativo ? '📉' : '📈'}</div>
      <div class="lbl">Ganancia Neta</div>
      <div class="val" style="color:${esNegativo?'#ef4444':'#10b981'}">${S(ganancia)}</div>
      <div class="sub">Después de gastos operativos</div>
    </div>
    <div class="card c-orange">
      <div class="icon">💛</div>
      <div class="lbl">Inversión Activa</div>
      <div class="val">${S(d.inversion)}</div>
      <div class="sub">Dinero en ropa sin vender</div>
    </div>
    <div class="card c-purple">
      <div class="icon">📦</div>
      <div class="lbl">Inventario</div>
      <div class="val">${UDS(d.inventario_uds)}</div>
      <div class="sub">Prendas en stock</div>
    </div>
  </div>

  <!-- GRÁFICOS -->
  <div class="charts">
    <div class="panel">
      <h3>🍩 Distribución de Ingresos</h3>
      <div class="donut-wrap">
        <canvas id="donutChart"></canvas>
        <div class="donut-center">
          <div class="big">${S(d.precio_venta)}</div>
          <div class="small">Total vendido</div>
        </div>
      </div>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div><span>Precio Costo: ${S(d.precio_costo)}</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div><span>Gastos Operativos: ${S(d.gastos)}</span></div>
        <div class="legend-item"><div class="legend-dot" style="background:#10b981"></div><span>Ganancia Neta: ${S(ganancia)}</span></div>
      </div>
    </div>
    <div class="panel">
      <h3>📅 Ventas por Mes (últimos 6)</h3>
      <canvas id="barChart" height="220"></canvas>
    </div>
  </div>

  <!-- TABLAS -->
  <div class="tables">
    <div class="panel">
      <h3>📦 Inventario con mayor inversión</h3>
      <table>
        <thead><tr><th>Prenda</th><th>Stock</th><th>P. Costo</th><th>Inversión</th></tr></thead>
        <tbody id="invTable"></tbody>
      </table>
    </div>
    <div class="panel">
      <h3>💸 Gastos Operativos</h3>
      <table>
        <thead><tr><th>Concepto</th><th>Monto</th></tr></thead>
        <tbody id="gastosTable"></tbody>
      </table>
    </div>
  </div>`;

  // Donut
  const donutCtx = document.getElementById('donutChart').getContext('2d');
  const costo = d.precio_costo;
  const gastos = d.gastos;
  const gananciaPositiva = Math.max(0, ganancia);
  const perdida = ganancia < 0 ? Math.abs(ganancia) : 0;
  donutChart = new Chart(donutCtx, {
    type: 'doughnut',
    data: {
      labels: ['Precio Costo', 'Gastos Operativos', 'Ganancia', 'Pérdida'],
      datasets: [{
        data: [costo, gastos, gananciaPositiva, perdida],
        backgroundColor: ['#f59e0b', '#ef4444', '#10b981', '#7f1d1d'],
        borderColor: 'transparent', borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      cutout: '68%', responsive: true,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` ${ctx.label}: S/ ${ctx.parsed.toFixed(2)}` }
      }}
    }
  });

  // Bar
  const meses = Object.keys(d.ventas_por_mes);
  const barCtx = document.getElementById('barChart').getContext('2d');
  barChart = new Chart(barCtx, {
    type: 'bar',
    data: {
      labels: meses.map(m => m.slice(5) + '/' + m.slice(0,4)),
      datasets: [
        { label: 'Precio Venta', data: meses.map(m => d.ventas_por_mes[m].ingresos), backgroundColor: 'rgba(96,165,250,0.7)', borderRadius: 6 },
        { label: 'Precio Costo', data: meses.map(m => d.ventas_por_mes[m].costo), backgroundColor: 'rgba(245,158,11,0.7)', borderRadius: 6 },
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: 'rgba(255,255,255,0.6)', font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: 'rgba(255,255,255,0.5)' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { color: 'rgba(255,255,255,0.5)', callback: v => 'S/'+v }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });

  // Tabla Inventario
  const invT = document.getElementById('invTable');
  d.top_inventario.forEach(p => {
    invT.innerHTML += `<tr>
      <td>${p.nombre}</td>
      <td>${p.stock}</td>
      <td>S/${p.costo_u.toFixed(2)}</td>
      <td><span class="tag tag-${p.valor>0?'green':'red'}">S/${p.valor.toFixed(2)}</span></td>
    </tr>`;
  });

  // Tabla Gastos
  const gasT = document.getElementById('gastosTable');
  if (d.gastos_lista.length === 0) {
    gasT.innerHTML = '<tr><td colspan="2" style="color:rgba(255,255,255,0.3);text-align:center;padding:16px">Sin gastos registrados</td></tr>';
  } else {
    d.gastos_lista.forEach(g => {
      gasT.innerHTML += `<tr><td>${g.nombre}</td><td><span class="tag tag-red">S/${g.monto.toFixed(2)}</span></td></tr>`;
    });
  }
}

loadData();
setInterval(loadData, 120000); // Refresca cada 2 minutos
</script>
</body>
</html>"""
