from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import pytz

from config import logger, _reply
from ia_gemini import teclado_menu_principal, teclado_lista_prendas
from notion_api import crear_gasto_notion, buscar_ventas_notion, eliminar_venta_notion, actualizar_stock_notion
from handlers import _formato_stock

# ESTADOS GASTOS
GASTO_NOMBRE = 500
GASTO_MONTO = 501
GASTO_FECHA = 502

# ESTADOS DEVOLUCION
DEV_BUSCAR = 600
DEV_CONFIRMAR = 601

timezone_lima = pytz.timezone('America/Lima')

# ============================================================
# HANDLER: GASTOS
# ============================================================
async def cmd_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _reply(update, "💸 *Registrar Gasto*\n\nEscribe el motivo o nombre del gasto (ej: Pasajes Gamarra):", parse_mode="Markdown")
    return GASTO_NOMBRE

async def gasto_recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 2:
        await update.message.reply_text("El nombre es muy corto.")
        return GASTO_NOMBRE
    context.user_data["gasto_nombre"] = nombre
    await update.message.reply_text("¿Cuál fue el monto total gastado? (ej: 15.50)")
    return GASTO_MONTO

async def gasto_recibir_monto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        monto = float(update.message.text.strip())
        assert monto > 0
    except:
        await update.message.reply_text("Por favor escribe un número válido mayor a 0.")
        return GASTO_MONTO
    
    context.user_data["gasto_monto"] = monto
    hoy = datetime.now(timezone_lima).strftime("%Y-%m-%d")
    context.user_data["gasto_fecha"] = hoy
    
    # Podriamos pedir fecha, pero para gastos asumimos que es hoy por agilidad.
    # Si quieren cambiarlo, seria como en ventas. Aquí lo hacemos directo:
    
    await update.message.reply_text("Guardando gasto...")
    exito = await crear_gasto_notion(context.user_data["gasto_nombre"], monto, hoy)
    
    if exito:
        await update.message.reply_text(
            f"✅ *Gasto Registrado*\n\nMotivo: {context.user_data['gasto_nombre']}\nMonto: S/{monto:.2f}\nFecha: {hoy}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al menú", callback_data="menu_inicio")]])
        )
    else:
        await update.message.reply_text("❌ Error al guardar en Notion.")
        
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================
# HANDLER: DEVOLUCION
# ============================================================
async def cmd_devolucion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _reply(update, "🔄 *Registrar Devolución*\n\nBusca la prenda de la venta que quieres devolver (escribe el nombre):", parse_mode="Markdown")
    return DEV_BUSCAR

async def devolucion_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termino = update.message.text.strip()
    if len(termino) < 2:
        await update.message.reply_text("Escribe al menos 2 letras.")
        return DEV_BUSCAR
    
    await update.message.reply_text("Buscando en ventas recientes...")
    ventas = await buscar_ventas_notion(termino)
    if not ventas:
        await update.message.reply_text("No encontré ventas con ese nombre.")
        return DEV_BUSCAR
        
    context.user_data["dev_ventas_encontradas"] = {v["id"]: v for v in ventas}
    
    # Usar un teclado simple o paginado
    botones = []
    for v in ventas[:10]:
        botones.append([InlineKeyboardButton(v["label"], callback_data=f"sel_dev:{v['id']}")])
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])
    
    await update.message.reply_text(
        f"Encontré {len(ventas[:10])} ventas recientes. ¿Cuál deseas devolver?",
        reply_markup=InlineKeyboardMarkup(botones)
    )
    return DEV_CONFIRMAR

async def devolucion_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancelar":
        await query.edit_message_text("Operación cancelada.")
        context.user_data.clear()
        return ConversationHandler.END
        
    page_id = query.data.replace("sel_dev:", "")
    venta = context.user_data.get("dev_ventas_encontradas", {}).get(page_id)
    if not venta:
        await query.edit_message_text("Error. Intenta de nuevo con /devolucion")
        return ConversationHandler.END
        
    # Eliminar la venta y restaurar stock automáticamente
    await query.edit_message_text("Procesando devolución y restaurando stock...")
    exito = await eliminar_venta_notion(page_id)
    
    if exito:
        await query.edit_message_text(
            f"✅ *Devolución Completada*\n\nSe eliminó la venta de:\n{venta['nombre']}\n\nEl stock de esta prenda ha aumentado +1 automáticamente.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al menú", callback_data="menu_inicio")]])
        )
    else:
        await query.edit_message_text("❌ Error al procesar la devolución en Notion.")
        
    context.user_data.clear()
    return ConversationHandler.END
