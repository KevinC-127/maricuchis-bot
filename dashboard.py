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
    total_prendas = 0
    stock_stats = {"Disponible": 0, "Stock bajo": 0, "Agotado": 0}
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
            total_prendas += 1
            
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
    ventas_por_mes = {}
    ventas_por_dia = {}
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
                precio_venta = props.get("Precio Venta", {}).get("number", 0) or 0
                costo_u = props.get("Costo unitario", {}).get("number", 0) or 0
                ganancia = props.get("Ganancia", {}).get("number", 0) or 0
                fecha_d = (props.get("Fecha", {}).get("date") or {})
                full_fecha = fecha_d.get("start", "")
                mes = full_fecha[:7]
                
                # Ingresos = ganancia + costo total (siempre fiable)
                # Esto funciona igual sin importar si Precio Venta es por unidad o total
                ingreso_linea = ganancia + (costo_u * cantidad)
                costo_linea = costo_u * cantidad
                
                total_precio_venta += ingreso_linea
                total_precio_costo += costo_linea
                total_uds_vendidas += cantidad
                
                if mes:
                    if mes not in ventas_por_mes:
                        ventas_por_mes[mes] = {"ingresos": 0, "costo": 0, "ganancia": 0, "uds": 0}
                    ventas_por_mes[mes]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_mes[mes]["costo"] += round(costo_linea, 2)
                    ventas_por_mes[mes]["ganancia"] += round(ganancia, 2)
                    ventas_por_mes[mes]["uds"] += cantidad
                
                # Para el gráfico diario: ingresos Y ganancia por separado
                if full_fecha and full_fecha >= fecha_limite:
                    if full_fecha not in ventas_por_dia:
                        ventas_por_dia[full_fecha] = {"ingresos": 0, "ganancia": 0, "uds": 0}
                    ventas_por_dia[full_fecha]["ingresos"] += round(ingreso_linea, 2)
                    ventas_por_dia[full_fecha]["ganancia"] += round(ganancia, 2)
                    ventas_por_dia[full_fecha]["uds"] += cantidad

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
        "inversion":        round(total_inversion, 2),
        "inventario_uds":   total_stock,
        "total_prendas":    total_prendas,
        "uds_vendidas":     total_uds_vendidas,
        "stock_stats":      stock_stats,
        "top_inventario":   top_inventario[:8],
        "gastos_lista":     gastos_lista[:10],
        "ventas_por_mes":   {m: ventas_por_mes[m] for m in meses_sorted},
        "ventas_por_dia":   {d: ventas_por_dia[d] for d in dias_sorted},
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
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--gold:#f59e0b;--green:#10b981;--red:#ef4444;--blue:#3b82f6;--purple:#8b5cf6;--pink:#ec4899;--bg:#050505;--card:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;background-color:var(--bg);background-image:radial-gradient(circle at 50% 0%, rgba(139,92,246,0.15) 0%, transparent 50%);min-height:100vh;color:#fff;padding:20px;line-height:1.5}
.container{max-width:1400px;margin:0 auto}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;flex-wrap:wrap;gap:15px}
.header-left h1{font-size:2rem;font-weight:800;background:linear-gradient(135deg,#f59e0b,#ec4899,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header-left p{color:rgba(255,255,255,0.5);font-size:.9rem}
.last-update{background:rgba(255,255,255,0.05);padding:6px 12px;border-radius:30px;font-size:.75rem;border:1px solid var(--border);color:rgba(255,255,255,0.6)}

.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:25px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:20px;backdrop-filter:blur(20px);transition:all .3s cubic-bezier(0.4,0,0.2,1);position:relative}
.card:hover{transform:translateY(-5px);border-color:rgba(255,255,255,0.2);background:rgba(255,255,255,0.05)}
.card .lbl{font-size:.65rem;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin-bottom:6px}
.card .val{font-size:1.5rem;font-weight:700;margin-bottom:3px}
.card .sub{font-size:.7rem;color:rgba(255,255,255,0.3)}

.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-bottom:20px}
@media(max-width:1100px){.grid-2{grid-template-columns:1fr}}
@media(max-width:900px){.grid-3{grid-template-columns:1fr}}

.panel{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:25px;backdrop-filter:blur(20px)}
.panel h3{font-size:1rem;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:10px;color:rgba(255,255,255,0.9)}
.panel .desc{font-size:.72rem;color:rgba(255,255,255,0.35);margin-bottom:18px;line-height:1.4}

.chart-container{position:relative;width:100%;height:260px}

table{width:100%;border-collapse:separate;border-spacing:0 6px}
th{text-align:left;font-size:.63rem;color:rgba(255,255,255,0.4);text-transform:uppercase;padding:0 10px 8px}
td{background:rgba(255,255,255,0.02);padding:10px;font-size:.82rem}
td:first-child{border-radius:10px 0 0 10px}
td:last-child{border-radius:0 10px 10px 0;text-align:right}
.tag{padding:3px 9px;border-radius:7px;font-size:.68rem;font-weight:700}
.tag-green{background:rgba(16,185,129,0.1);color:var(--green)}
.tag-red{background:rgba(239,68,68,0.1);color:var(--red)}
.tag-gold{background:rgba(245,158,11,0.1);color:var(--gold)}
.tag-blue{background:rgba(59,130,246,0.1);color:var(--blue)}

.loading-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:var(--bg);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1000}
.spinner{width:40px;height:40px;border:3px solid rgba(255,255,255,0.05);border-top-color:var(--purple);border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div id="loading" class="loading-overlay"><div class="spinner"></div><p style="margin-top:20px;color:rgba(255,255,255,0.5)">Sincronizando con Notion...</p></div>

<div class="container">
  <div class="header">
    <div class="header-left">
      <h1>🌸 Maricuchis Store</h1>
      <p>Dashboard Financiero en Tiempo Real</p>
    </div>
    <div class="last-update" id="lastUpdate">Actualizando...</div>
  </div>

  <div id="metrics" class="metrics"></div>

  <div class="grid-2">
    <div class="panel">
      <h3>📈 Ventas Diarias</h3>
      <p class="desc">Ingresos brutos (azul) y ganancia neta (verde) por día en los últimos 30 días. Los ingresos son el total cobrado; la ganancia es lo que queda después de descontar el costo unitario.</p>
      <div class="chart-container"><canvas id="lineChart"></canvas></div>
    </div>
    <div class="panel">
      <h3>🍩 Salud del Stock</h3>
      <p class="desc">Cantidad de prendas según su disponibilidad. Disponible = más de 3 unidades. Stock bajo = 1 a 3 unidades. Agotado = 0 unidades.</p>
      <div class="chart-container" style="height:200px"><canvas id="stockDonut"></canvas></div>
      <div id="stockLegend" style="margin-top:15px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px"></div>
    </div>
  </div>

  <div class="grid-3">
    <div class="panel">
      <h3>💰 Flujo Mensual</h3>
      <p class="desc">Comparación de ingresos por ventas vs costos de mercadería vendida por mes. La diferencia es tu ganancia bruta mensual.</p>
      <div class="chart-container" style="height:200px"><canvas id="barChart"></canvas></div>
    </div>
    <div class="panel">
      <h3>📦 Top Inventario</h3>
      <p class="desc">Prendas con mayor inversión activa (stock actual × costo unitario). Muestra dónde está tu dinero inmovilizado.</p>
      <table>
        <thead><tr><th>Prenda</th><th>Stock</th><th>Inversión</th></tr></thead>
        <tbody id="invTable"></tbody>
      </table>
    </div>
    <div class="panel">
      <h3>💸 Gastos Registrados</h3>
      <p class="desc">Gastos operativos registrados (pasajes, envíos, etc.). Se descuentan de la ganancia bruta para obtener la ganancia neta.</p>
      <table>
        <thead><tr><th>Concepto</th><th>Monto</th></tr></thead>
        <tbody id="gastosTable"></tbody>
      </table>
      <div id="gastosTotal" style="margin-top:10px;text-align:right;font-size:.8rem;color:rgba(255,255,255,0.4)"></div>
    </div>
  </div>
</div>

<script>
const S = n => 'S/ ' + Number(n).toLocaleString('es-PE', {minimumFractionDigits:2, maximumFractionDigits:2});
let charts = {};

async function loadData() {
  try {
    const res = await fetch('/api/stats');
    const d = await res.json();
    updateUI(d);
    document.getElementById('loading').style.display = 'none';
  } catch(e) { console.error(e); }
}

function updateUI(d) {
  document.getElementById('lastUpdate').textContent = 'Actualizado: ' + new Date().toLocaleTimeString('es-PE');
  
  // METRICS
  const gn = d.ganancia_neta;
  const gb = d.ganancia_bruta;
  const margen = d.precio_venta > 0 ? ((gb / d.precio_venta) * 100).toFixed(1) : 0;
  const metrics = [
    {lbl:'Ingresos por Ventas', val:S(d.precio_venta), sub:'Total cobrado a clientes', color:'var(--blue)'},
    {lbl:'Costo de Ventas', val:S(d.precio_costo), sub:'Costo de mercadería vendida', color:'var(--gold)'},
    {lbl:'Ganancia Bruta', val:S(gb), sub:'Margen: ' + margen + '%', color:gb>=0?'var(--green)':'var(--red)'},
    {lbl:'Gastos Operativos', val:S(d.gastos), sub:'Pasajes, envíos, etc.', color:'var(--pink)'},
    {lbl:'Ganancia Neta', val:S(gn), sub:'Bruta − Gastos', color:gn>=0?'var(--green)':'var(--red)'},
    {lbl:'Inversión en Stock', val:S(d.inversion), sub:d.inventario_uds + ' uds en ' + d.total_prendas + ' prendas', color:'var(--purple)'},
  ];
  document.getElementById('metrics').innerHTML = metrics.map(m => `
    <div class="card">
      <div class="lbl">${m.lbl}</div>
      <div class="val" style="color:${m.color}">${m.val}</div>
      <div class="sub">${m.sub}</div>
    </div>`).join('');

  // LINE CHART (Daily Sales — Ingresos + Ganancia)
  const days = Object.keys(d.ventas_por_dia);
  renderChart('lineChart', 'line', {
    labels: days.map(day => {
      const p = day.split('-');
      return p[2] + '/' + p[1];
    }),
    datasets: [
      {
        label: 'Ingresos (cobrado)',
        data: days.map(day => d.ventas_por_dia[day].ingresos),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.08)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#3b82f6'
      },
      {
        label: 'Ganancia (neta x venta)',
        data: days.map(day => d.ventas_por_dia[day].ganancia),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.08)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#10b981'
      }
    ]
  }, {
    scales: {
      y: { beginAtZero: true, ticks: { callback: v => 'S/'+v } }
    },
    plugins: {
      tooltip: {
        callbacks: {
          afterBody: function(ctx) {
            const day = days[ctx[0].dataIndex];
            const uds = d.ventas_por_dia[day].uds;
            return 'Unidades: ' + uds;
          }
        }
      }
    }
  });

  // STOCK DONUT
  const s = d.stock_stats;
  const stockLabels = ['Disponible', 'Stock bajo', 'Agotado'];
  const stockData = [s.Disponible, s["Stock bajo"], s.Agotado];
  const stockColors = ['#10b981', '#f59e0b', '#ef4444'];
  renderChart('stockDonut', 'doughnut', {
    labels: stockLabels,
    datasets: [{
      data: stockData,
      backgroundColor: stockColors,
      borderWidth: 0,
      cutout: '75%'
    }]
  }, { plugins: { legend: { display: false } } });
  
  document.getElementById('stockLegend').innerHTML = stockLabels.map((l,i) => `
    <div style="font-size:0.75rem; color:rgba(255,255,255,0.6); display:flex; align-items:center; gap:6px">
      <div style="width:8px; height:8px; border-radius:50%; background:${stockColors[i]}"></div>
      ${l}: <b>${stockData[i]}</b>
    </div>`).join('');

  // BAR CHART (Monthly)
  const months = Object.keys(d.ventas_por_mes);
  renderChart('barChart', 'bar', {
    labels: months.map(m => {
      const p = m.split('-');
      return p[1] + '/' + p[0];
    }),
    datasets: [
      { label: 'Ingresos', data: months.map(m => d.ventas_por_mes[m].ingresos), backgroundColor: '#3b82f6', borderRadius: 5 },
      { label: 'Costos', data: months.map(m => d.ventas_por_mes[m].costo), backgroundColor: '#f59e0b', borderRadius: 5 }
    ]
  }, { scales: { y: { ticks: { display: false }, grid: { display: false } }, x: { grid: { display: false } } } });

  // TABLE — Top Inventario
  document.getElementById('invTable').innerHTML = d.top_inventario.map(p => `
    <tr>
      <td>${p.nombre}</td>
      <td><b>${p.stock}</b></td>
      <td><span class="tag tag-gold">${S(p.valor)}</span></td>
    </tr>`).join('');

  // TABLE — Gastos
  if (d.gastos_lista && d.gastos_lista.length > 0) {
    document.getElementById('gastosTable').innerHTML = d.gastos_lista.map(g => `
      <tr>
        <td>${g.nombre}</td>
        <td><span class="tag tag-red">${S(g.monto)}</span></td>
      </tr>`).join('');
    document.getElementById('gastosTotal').innerHTML = '<b>Total: ' + S(d.gastos) + '</b>';
  } else {
    document.getElementById('gastosTable').innerHTML = '<tr><td colspan="2" style="text-align:center;color:rgba(255,255,255,0.3)">Sin gastos registrados</td></tr>';
  }
}

function renderChart(id, type, data, options = {}) {
  if(charts[id]) charts[id].destroy();
  const ctx = document.getElementById(id).getContext('2d');
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: 'rgba(255,255,255,0.6)', font: { family: 'Outfit', size: 11 } } } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } } },
      y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } } }
    }
  };
  charts[id] = new Chart(ctx, { type, data, options: { ...baseOptions, ...options } });
}

loadData();
setInterval(loadData, 60000);
</script>
</body>
</html>"""
