"""
ia_brain.py — Cerebro IA de Maricuchis Store
Clasificación de intención + Extracción de datos usando Groq LLama 3.3
"""
import os
import json
import time
import asyncio
import requests
from config import GROQ_API_KEY, logger

# ============================================================
# CONFIGURACIÓN
# ============================================================
GROQ_LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
SESSION_TIMEOUT = 600  # 10 minutos

# ============================================================
# SESIONES DE USUARIO
# ============================================================
_sesiones = {}  # chat_id -> sesion

def get_sesion(chat_id: int) -> dict | None:
    """Obtiene la sesión activa de un usuario, o None si no hay/expiró."""
    s = _sesiones.get(chat_id)
    if s and (time.time() - s["timestamp"]) > SESSION_TIMEOUT:
        del _sesiones[chat_id]
        return None
    return s

def crear_sesion(chat_id: int, tipo: str, datos: dict = None) -> dict:
    """Crea una nueva sesión IA para el usuario."""
    s = {
        "activa": True,
        "tipo": tipo,
        "datos": datos or {},
        "timestamp": time.time(),
        "esperando": [],
        "foto_url": None,
    }
    _sesiones[chat_id] = s
    return s

def actualizar_sesion(chat_id: int, **kwargs):
    """Actualiza campos de la sesión."""
    s = _sesiones.get(chat_id)
    if s:
        s.update(kwargs)
        s["timestamp"] = time.time()

def cerrar_sesion(chat_id: int):
    """Cierra y elimina la sesión."""
    _sesiones.pop(chat_id, None)


# ============================================================
# LLAMADA A GROQ LLM
# ============================================================
def _sync_llamar_llm(system_prompt: str, user_message: str, temperature: float = 0.1) -> str:
    """Llamada síncrona a Groq LLM."""
    if not GROQ_API_KEY:
        return '{"error": "No hay GROQ_API_KEY"}'
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
    }
    
    r = requests.post(GROQ_LLM_URL, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        logger.error(f"Groq LLM error {r.status_code}: {r.text[:300]}")
        return '{"error": "Error API"}'
    
    content = r.json()["choices"][0]["message"]["content"]
    return content

async def llamar_llm(system_prompt: str, user_message: str, temperature: float = 0.1) -> dict:
    """Llamada asíncrona a Groq LLM. Retorna dict parseado."""
    raw = await asyncio.to_thread(_sync_llamar_llm, system_prompt, user_message, temperature)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"LLM respuesta no-JSON: {raw[:200]}")
        return {"error": "Respuesta no válida"}


# ============================================================
# CLASIFICADOR DE INTENCIÓN (prompt ligero)
# ============================================================
SYSTEM_CLASIFICAR = """Eres el asistente de inventario de Maricuchis Store (tienda de ropa).
Clasifica la intención del usuario en UNA de estas categorías:

INTENCIONES:
- registrar_venta: quiere registrar una venta (compró, vendí, separó, llevó, se llevó)
- agregar_prenda: quiere agregar inventario nuevo (llegó, traje, compré mercadería, registrar prenda nueva)
- actualizar_pendiente: quiere marcar un pendiente como pagado/completado (ya pagó, ya cobré)
- cancelar: quiere cancelar la operación actual (cancela, olvídalo, ya no, no nada, dejalo)
- consultar_stock: pregunta por stock de una prenda específica (cuánto stock tiene, cuántas quedan)
- consultar_precio: pregunta por precio o costo de una prenda (cuánto cuesta, qué precio tiene)
- consultar_pendientes: pregunta por ventas pendientes (cuántos pendientes, qué falta cobrar)
- consultar_inventario: quiere ver qué prendas se agregaron en cierta fecha
- consultar_ventas: pregunta por ventas de una fecha o periodo
- sin_sentido: el mensaje no tiene relación con el negocio o es incoherente
- no_entendido: se entiende que habla del negocio pero falta contexto para saber qué quiere

REGLAS:
- Si el mensaje es incoherente o no tiene relación con ropa/ventas/inventario → "sin_sentido"
- Si el mensaje sí habla del negocio pero no hay contexto suficiente → "no_entendido"
- Extrae cualquier dato mencionado (nombre de prenda, cliente, cantidades, precios, fechas)
- Los números pueden venir como texto ("dos") o dígitos ("2"), siempre devuélvelos como dígitos
- Si mencionan una fecha como "ayer", "hoy", "el viernes", conviértela al formato apropiado

Responde SOLO en JSON:
{"intencion": "...", "datos": {"prenda": "...", "cliente": "...", "cantidad": N, "precio": N, "costo": N, "stock": N, "tienda": "...", "fecha": "...", "estado": "..."}}
Usa null para los datos no mencionados."""


async def clasificar_intencion(mensaje: str) -> dict:
    """Clasifica la intención del mensaje del usuario."""
    return await llamar_llm(SYSTEM_CLASIFICAR, mensaje)


# ============================================================
# EXTRACTOR CON CONTEXTO (prompt completo)
# ============================================================
def build_extraction_prompt(intencion: str, clientes: list, prendas: list, tiendas: list) -> str:
    """Construye el prompt con contexto de la BD para extracción precisa."""
    
    clientes_str = "\n".join(f"- {c}" for c in clientes[:60]) if clientes else "- (sin clientas registradas)"
    
    prendas_str = "\n".join(
        f"- {p['nombre']} (S/{p.get('precio',0)}, stock: {p.get('stock',0)}, costo_u: S/{p.get('costo_u',0)})"
        for p in prendas[:80]
    ) if prendas else "- (sin prendas)"
    
    tiendas_str = "\n".join(f"- {t}" for t in tiendas) if tiendas else "- Gamarra\n- Ambulante"
    
    if intencion == "registrar_venta":
        return f"""Eres el asistente de Maricuchis Store. Extrae los datos de una VENTA.

CLIENTAS REGISTRADAS (usa el nombre EXACTO más cercano):
{clientes_str}

PRENDAS EN INVENTARIO (usa el nombre EXACTO más cercano):
{prendas_str}

REGLAS DE MATCHING INTELIGENTE:
- Usa DEDUCCIÓN para coincidir nombres parciales con la lista existente:
  Ejemplo: "Brenda pilates" → "Brenda (P)" porque P = Pilates
  Ejemplo: "Dafne escuela mini" → "Dafne (E.M.)" porque E.M. = Escuela Mini
- Si hay varias posibles coincidencias, pon "cliente_exacto": false y "candidatos": [lista]
- Si el cliente es completamente nuevo, ponlo tal cual con "cliente_exacto": false
- Para prendas, busca la coincidencia más cercana en la lista
- Si una prenda NO coincide con nada, pon "prenda_exacta": false

REGLAS DE PRECIOS:
- Si el usuario da un TOTAL GLOBAL (ej: "a 54 soles"), distribuye usando precios del inventario:
  Ejemplo: 2 polos (S/10 c/u) + 1 pantalón (S/34) = S/54 total → cada item con su precio de lista
  En ese caso pon "precio_total_dado": 54
- Si el usuario da precio POR UNIDAD (ej: "a 22 cada una"), úsalo como precio de cada item
- Si no mencionó precio, usa el precio de la lista
- Si mencionó un precio diferente al de lista para una prenda → es descuento

REGLAS DE DATOS:
- Si no mencionó cantidad, asume 1
- Si no dijo si pagó o no, pon estado null (se preguntará)
- Si dijo "separó", "fió", "queda debiendo" → estado = "Pendiente"
- Si dijo "pagó", "completo", "al contado" → estado = "Completado"
- Si mencionó fecha ("ayer", "hace 2 días"), ponla; si no, pon null
- Los números en texto ("dos") conviértelos a dígitos (2)

Responde SOLO en JSON:
{{"cliente": "...", "cliente_exacto": true/false, "candidatos": [], "items": [{{"prenda": "...", "prenda_exacta": true/false, "cantidad": N, "precio": N}}], "precio_total_dado": N o null, "estado": "Completado"/"Pendiente"/null, "fecha": "YYYY-MM-DD" o null}}"""

    elif intencion == "agregar_prenda":
        return f"""Eres el asistente de Maricuchis Store. Extrae los datos de una NUEVA PRENDA.

TIENDAS REGISTRADAS (usa el nombre EXACTO más cercano):
{tiendas_str}

CAMPOS REQUERIDOS:
- nombre: nombre de la prenda
- costo: precio total que costó el lote (NO unitario)
- precio: precio de venta por unidad
- stock: cantidad de unidades
- tienda: de dónde se compró

REGLAS DE MATCHING INTELIGENTE:
- Usa DEDUCCIÓN para coincidir tiendas parciales con la lista:
  Ejemplo: "tienda juanita piso 4" → "Tienda juanita P.4" (P.4 = piso 4)
  Ejemplo: "de ale" → "Ale Masías"
  Ejemplo: "mayoristas" → "G. Mayoristas Coral"
- Si dicen "docena" = 12 unidades, "media docena" = 6
- Los números en texto conviértelos a dígitos
- Si faltan datos, ponlos como null

Responde SOLO en JSON:
{{"nombre": "...", "costo": N, "precio": N, "stock": N, "tienda": "...", "campos_faltantes": ["campo1", "campo2"]}}"""

    elif intencion == "actualizar_pendiente":
        return f"""Eres el asistente de Maricuchis Store. Identifica qué pendiente quiere completar.

CLIENTAS REGISTRADAS:
{clientes_str}

PRENDAS EN INVENTARIO:
{prendas_str}

Extrae el cliente y opcionalmente la prenda mencionada.

Responde SOLO en JSON:
{{"cliente": "...", "cliente_exacto": true/false, "prenda": "..." o null}}"""

    else:  # consultas
        return f"""Eres el asistente de Maricuchis Store. Responde la consulta del usuario.

PRENDAS EN INVENTARIO:
{prendas_str}

Extrae los datos relevantes de la consulta.

Responde SOLO en JSON:
{{"prenda": "..." o null, "fecha": "..." o null, "tipo_consulta": "stock/precio/pendientes/inventario/ventas"}}"""


async def extraer_datos(intencion: str, mensaje: str, clientes: list, prendas: list, tiendas: list) -> dict:
    """Extrae datos con contexto completo de la BD."""
    system = build_extraction_prompt(intencion, clientes, prendas, tiendas)
    return await llamar_llm(system, mensaje)


# ============================================================
# COMPLETAR DATOS PARCIALES (sesión activa)
# ============================================================
def build_completion_prompt(tipo_sesion: str, datos_actuales: dict, campos_faltantes: list, 
                            clientes: list = None, prendas: list = None, tiendas: list = None) -> str:
    """Prompt para extraer datos faltantes de un mensaje de seguimiento."""
    
    datos_str = json.dumps(datos_actuales, ensure_ascii=False, indent=2)
    faltantes_str = ", ".join(campos_faltantes)
    
    extra_context = ""
    if tiendas and "tienda" in campos_faltantes:
        tiendas_str = ", ".join(tiendas)
        extra_context += f"\nTIENDAS VÁLIDAS: {tiendas_str}"
    if clientes and "cliente" in campos_faltantes:
        clientes_str = ", ".join(clientes[:30])
        extra_context += f"\nCLIENTAS: {clientes_str}"
    if prendas and "prenda" in campos_faltantes:
        prendas_str = ", ".join(p["nombre"] for p in prendas[:40])
        extra_context += f"\nPRENDAS: {prendas_str}"
    
    return f"""Eres el asistente de Maricuchis Store. Estás en medio de un registro de {tipo_sesion}.

DATOS YA REGISTRADOS:
{datos_str}

DATOS QUE FALTAN: {faltantes_str}
{extra_context}

El usuario está respondiendo con los datos faltantes. Extrae SOLO los datos que faltan.
Si mencionan una tienda o clienta, usa DEDUCCIÓN para coincidir con la lista:
  Ejemplo: "Brenda pilates" → "Brenda (P)", "piso 4" → "P.4", "escuela mini" → "E.M."
Los números en texto conviértelos a dígitos.
Si el mensaje NO contiene datos útiles o es incoherente, responde: {{"sin_sentido": true}}

Responde SOLO en JSON con los campos extraídos (solo los que faltaban):
{{"campo1": valor1, "campo2": valor2}}"""


async def completar_datos(tipo_sesion: str, mensaje: str, datos_actuales: dict, 
                          campos_faltantes: list, **context_kwargs) -> dict:
    """Extrae datos faltantes de un mensaje de seguimiento."""
    system = build_completion_prompt(tipo_sesion, datos_actuales, campos_faltantes, **context_kwargs)
    return await llamar_llm(system, mensaje)


# ============================================================
# UTILIDADES
# ============================================================
def campos_faltantes_prenda(datos: dict) -> list:
    """Retorna lista de campos obligatorios que faltan para registrar prenda."""
    requeridos = ["nombre", "costo", "precio", "stock", "tienda"]
    return [c for c in requeridos if not datos.get(c)]

def campos_faltantes_venta(datos: dict) -> list:
    """Retorna campos obligatorios faltantes para registrar venta."""
    faltantes = []
    if not datos.get("cliente"):
        faltantes.append("cliente")
    if not datos.get("items") or len(datos["items"]) == 0:
        faltantes.append("prenda")
    if datos.get("estado") is None:
        faltantes.append("estado")
    return faltantes

def formatear_resumen_prenda(datos: dict) -> str:
    """Formatea un resumen bonito para confirmar registro de prenda."""
    foto = "✅ Con foto" if datos.get("foto_url") else "📸 Sin foto"
    costo = datos.get("costo", 0)
    precio = datos.get("precio", 0)
    stock = datos.get("stock", 0)
    costo_u = round(costo / stock, 2) if stock > 0 else 0
    margen = round(((precio - costo_u) / costo_u) * 100) if costo_u > 0 else 0
    
    return (
        f"📦 *Nueva prenda:*\n"
        f"👗 {datos.get('nombre', '?')}\n"
        f"💰 Costo: S/{costo} (S/{costo_u} c/u) → Precio: S/{precio} (margen {margen}%)\n"
        f"📦 Stock: {stock} uds\n"
        f"🏪 {datos.get('tienda', '?')}\n"
        f"{foto}"
    )

def formatear_resumen_venta(datos: dict) -> str:
    """Formatea un resumen bonito para confirmar venta."""
    items_str = ""
    total = 0
    total_boletos = 0
    for i, item in enumerate(datos.get("items", []), 1):
        cant = item.get("cantidad", 1)
        precio = item.get("precio", 0)
        subtotal = cant * precio
        total += subtotal
        total_boletos += cant
        items_str += f"  {i}. {item.get('prenda', '?')} × {cant} → S/{subtotal}\n"
    
    estado = datos.get("estado", "Completado")
    estado_emoji = "✅" if estado == "Completado" else "⏳"
    boleto_str = f"\n🎟️ {total_boletos} boletos" if estado == "Completado" else ""
    
    return (
        f"🛒 *Venta:*\n"
        f"👤 {datos.get('cliente', '?')}\n"
        f"{items_str}"
        f"💰 Total: S/{total}\n"
        f"{estado_emoji} Estado: {estado}"
        f"{boleto_str}"
    )
