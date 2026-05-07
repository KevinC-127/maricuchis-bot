from config import *
from handlers import *
from dashboard import start_web_server
from handlers_venta import (
    cmd_vendi, venta_buscar_prenda, venta_confirmar_prenda, venta_recibir_cantidad,
    venta_recibir_precio, venta_recibir_precio_manual, venta_volver_cantidad,
    venta_mas_prendas, venta_pedir_cliente, venta_recibir_cliente, venta_recibir_fecha,
    venta_recibir_descuento, venta_finalizar,
    VENTA_BUSCAR, VENTA_CONFIRMAR, VENTA_CANTIDAD, VENTA_PRECIO,
    VENTA_MAS, VENTA_CLIENTE, VENTA_FECHA, VENTA_DESCUENTO, VENTA_PAGO
)
from handlers_gastos_devoluciones import (
    cmd_gasto, gasto_recibir_nombre, gasto_recibir_monto,
    GASTO_NOMBRE, GASTO_MONTO, GASTO_FECHA,
    cmd_devolucion, devolucion_buscar, devolucion_confirmar,
    DEV_BUSCAR, DEV_CONFIRMAR
)
# ============================================================
# MAIN — REGISTRO DE HANDLERS
# ============================================================
async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_CHAT_ID:
        user_id = str(update.effective_user.id) if update.effective_user else None
        chat_id = str(update.effective_chat.id) if update.effective_chat else None
        admin_ids = [i.strip() for i in ADMIN_CHAT_ID.split(",") if i.strip()]
        if user_id not in admin_ids and chat_id not in admin_ids:
            if update.callback_query:
                try:
                    await update.callback_query.answer("⛔ No estás autorizado para usar este bot.", show_alert=True)
                except:
                    pass
            elif update.message:
                await update.message.reply_text("⛔ No estás autorizado para usar este bot.")
            raise ApplicationHandlerStop

async def _post_init(application):
    """Arranca el dashboard web en el mismo event loop que el bot."""
    await start_web_server()

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(_post_init).build()


    # ConversationHandler — Nueva prenda guiado
    nueva_prenda_handler = ConversationHandler(
        entry_points=[
            CommandHandler("nueva", cmd_nueva_prenda),
            CommandHandler("sinfoto", cmd_sin_foto),
            CallbackQueryHandler(cmd_nueva_prenda, pattern="^menu_nueva_guiado$"),
            CallbackQueryHandler(cmd_sin_foto, pattern="^menu_sinfoto$"),
        ],
        states={
            NP_NOMBRE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, np_recibir_nombre)],
            NP_COSTO:        [MessageHandler(filters.TEXT & ~filters.COMMAND, np_recibir_costo)],
            NP_PRECIO:       [
                CallbackQueryHandler(np_recibir_precio_auto, pattern="^np_precio_auto$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, np_recibir_precio_manual),
            ],
            NP_STOCK_TIPO:   [
                CallbackQueryHandler(np_elegir_stock_tipo, pattern="^np_stock_"),
                CallbackQueryHandler(np_volver_precio, pattern="^np_volver_precio$"),
            ],
            NP_STOCK_DOCENAS:[
                CallbackQueryHandler(np_stock_docenas_btn, pattern="^np_doc_"),
                CallbackQueryHandler(np_volver_stock, pattern="^np_volver_stock$"),
            ],
            NP_STOCK_UNICA:  [MessageHandler(filters.TEXT & ~filters.COMMAND, np_stock_unidades_txt)],
            NP_TIENDA:       [
                CallbackQueryHandler(np_recibir_tienda_btn, pattern="^np_tienda"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, np_recibir_tienda_txt),
            ],
            NP_FECHA_MES:    [
                CallbackQueryHandler(np_elegir_mes, pattern="^np_mes_"),
                CallbackQueryHandler(np_volver_stock, pattern="^np_volver_stock$"),
            ],
            NP_FECHA_DIA:    [
                CallbackQueryHandler(np_recibir_fecha, pattern="^np_dia"),
                CallbackQueryHandler(np_volver_mes, pattern="^np_volver_mes$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, np_recibir_fecha),
            ],
            NP_FOTO:         [
                CallbackQueryHandler(np_elegir_foto, pattern="^np_foto_"),
                CallbackQueryHandler(np_volver_dia, pattern="^np_volver_dia$"),
                MessageHandler(filters.PHOTO, np_recibir_foto),
            ],
            NP_EDIT_CAMPO:   [
                CallbackQueryHandler(np_edit_elegir_campo, pattern="^np_edit_last$"),
                CallbackQueryHandler(np_edit_campo_seleccionado, pattern="^npe_"),
            ],
            NP_EDIT_VALOR:   [MessageHandler(filters.TEXT & ~filters.COMMAND, np_edit_recibir_valor)],
            NP_EDIT_FOTO:    [MessageHandler(filters.PHOTO, np_edit_recibir_foto)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Adjuntar foto
    adjfoto_handler = ConversationHandler(
        entry_points=[
            CommandHandler("adjfoto", cmd_adj_foto),
            CallbackQueryHandler(cmd_adj_foto, pattern="^menu_adjfoto$"),
        ],
        states={
            ADJFOTO_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, adjfoto_buscar_prenda)],
            ADJFOTO_CONFIRMAR: [CallbackQueryHandler(adjfoto_confirmar_prenda)],
            ADJFOTO_RECIBIR:   [MessageHandler(filters.PHOTO, adjfoto_recibir_foto)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Venta
    venta_handler = ConversationHandler(
        entry_points=[
            CommandHandler("venta", cmd_vendi),
            CallbackQueryHandler(cmd_vendi, pattern="^menu_venta$"),
        ],
        states={
            VENTA_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, venta_buscar_prenda)],
            VENTA_CONFIRMAR: [CallbackQueryHandler(venta_confirmar_prenda, pattern="^sel_venta:|^page_sel_venta:|^cancelar$")],
            VENTA_CANTIDAD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, venta_recibir_cantidad)],
            VENTA_PRECIO:    [
                CallbackQueryHandler(venta_recibir_precio, pattern="^precio_venta_"),
                CallbackQueryHandler(venta_volver_cantidad, pattern="^volver_cantidad$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, venta_recibir_precio_manual),
            ],
            VENTA_MAS:       [CallbackQueryHandler(venta_mas_prendas, pattern="^mas_si$|^mas_no$")],
            VENTA_CLIENTE:   [
                CallbackQueryHandler(venta_recibir_cliente, pattern="^cliente_sin_nombre$"),
                CallbackQueryHandler(venta_recibir_cliente, pattern="^cliente_nueva$"),
                CallbackQueryHandler(venta_recibir_cliente, pattern="^cliente_prev_"),
                CallbackQueryHandler(venta_recibir_cliente, pattern="^page_cliente:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, venta_recibir_cliente),
            ],
            VENTA_FECHA:     [
                CallbackQueryHandler(venta_recibir_fecha, pattern="^fecha_venta_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, venta_recibir_fecha),
            ],
            VENTA_DESCUENTO: [
                CallbackQueryHandler(venta_recibir_descuento, pattern="^descuento_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, venta_recibir_descuento),
            ],
            VENTA_PAGO:      [
                CallbackQueryHandler(venta_finalizar, pattern="^pago_"),
            ]
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Consultar prenda
    stock_handler = ConversationHandler(
        entry_points=[
            CommandHandler("prenda", cmd_stock),
            CallbackQueryHandler(cmd_stock, pattern="^menu_stock$"),
        ],
        states={
            STOCK_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_buscar_prenda)],
            STOCK_CONFIRMAR: [CallbackQueryHandler(stock_confirmar_prenda)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Editar
    editar_handler = ConversationHandler(
        entry_points=[
            CommandHandler("actualizar", cmd_editar),
            CallbackQueryHandler(cmd_editar, pattern="^menu_editar$"),
        ],
        states={
            EDITAR_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_buscar)],
            EDITAR_CONFIRMAR: [CallbackQueryHandler(editar_confirmar)],
            EDITAR_CAMPO:     [CallbackQueryHandler(editar_campo)],
            EDITAR_VALOR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, editar_valor)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Eliminar
    eliminar_handler = ConversationHandler(
        entry_points=[
            CommandHandler("eliminar", cmd_eliminar),
            CallbackQueryHandler(cmd_eliminar, pattern="^menu_eliminar$"),
        ],
        states={
            ELIMINAR_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, eliminar_buscar)],
            ELIMINAR_CONFIRMAR: [CallbackQueryHandler(eliminar_confirmar)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Ver foto
    verfoto_handler = ConversationHandler(
        entry_points=[
            CommandHandler("verfoto", cmd_ver_foto),
            CallbackQueryHandler(cmd_ver_foto, pattern="^menu_verfoto$"),
        ],
        states={
            FOTO_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, verfoto_buscar)],
            FOTO_CONFIRMAR: [CallbackQueryHandler(verfoto_confirmar)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # ConversationHandler — Comparar
    comparar_handler = ConversationHandler(
        entry_points=[
            CommandHandler("comparar", cmd_comparar),
            CallbackQueryHandler(cmd_comparar, pattern="^menu_comparar$"),
        ],
        states={
            COMPARAR_BUSCAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, comparar_buscar)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )

    # Registrar todos los handlers
    
    # ConversationHandler - Gastos
    gasto_handler = ConversationHandler(
        entry_points=[CommandHandler("gasto", cmd_gasto), CallbackQueryHandler(cmd_gasto, pattern="^menu_gasto$")],
        states={
            GASTO_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, gasto_recibir_nombre)],
            GASTO_MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gasto_recibir_monto)]
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar), CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$")],
        per_message=False
    )
    app.add_handler(gasto_handler)

    # ConversationHandler - Devolucion
    devolucion_handler = ConversationHandler(
        entry_points=[CommandHandler("devolucion", cmd_devolucion), CallbackQueryHandler(cmd_devolucion, pattern="^menu_devolucion$")],
        states={
            DEV_BUSCAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, devolucion_buscar)],
            DEV_CONFIRMAR: [CallbackQueryHandler(devolucion_confirmar, pattern="^sel_dev:|^cancelar$")]
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar), CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$")],
        per_message=False
    )
    app.add_handler(devolucion_handler)


    app.add_handler(nueva_prenda_handler)
    app.add_handler(adjfoto_handler)
    app.add_handler(venta_handler)
    app.add_handler(stock_handler)
    app.add_handler(editar_handler)
    app.add_handler(eliminar_handler)
    app.add_handler(verfoto_handler)
    app.add_handler(comparar_handler)

    # ConversationHandler — Eliminar Venta
    eliminar_venta_handler = ConversationHandler(
        entry_points=[
            CommandHandler("eliminar_venta", cmd_eliminar_venta),
            CallbackQueryHandler(cmd_eliminar_venta, pattern="^menu_eliminar_venta$"),
        ],
        states={
            ELIMINAR_VENTA_BUSCAR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, eliminar_venta_buscar)],
            ELIMINAR_VENTA_CONFIRMAR: [CallbackQueryHandler(eliminar_venta_confirmar)],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )
    app.add_handler(eliminar_venta_handler)

    # ConversationHandler — Actualizar Pendiente
    pendiente_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cmd_actualizar_pendiente, pattern="^menu_actualizar_pendiente$"),
        ],
        states={
            PENDIENTE_CONFIRMAR: [CallbackQueryHandler(pendiente_confirmar, pattern="^pend_")],
        },
        fallbacks=[
            CommandHandler("cancelar", cmd_cancelar),
            CallbackQueryHandler(fallback_menu_inicio, pattern="^menu_inicio$"),
        ],
        per_message=False,
    )
    app.add_handler(pendiente_handler)

    # Registrar middleware de seguridad global
    app.add_handler(TypeHandler(Update, auth_middleware), group=-1)

    # Comandos simples
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("menu",        cmd_menu))
    app.add_handler(CommandHandler("ayuda",       cmd_ayuda))
    app.add_handler(CommandHandler("cancelar",    cmd_cancelar))
    app.add_handler(CommandHandler("agotados",    cmd_agotados))
    app.add_handler(CommandHandler("limitadas",   cmd_limitadas))
    app.add_handler(CommandHandler("ganancia",    cmd_ganancia))
    app.add_handler(CommandHandler("inventario",  cmd_inventario))
    app.add_handler(CommandHandler("resumen",     cmd_resumen))
    app.add_handler(CommandHandler("pormargen",   cmd_por_margen))
    app.add_handler(CommandHandler("portienda",   cmd_por_tienda))
    app.add_handler(CommandHandler("chatid",      cmd_chatid))
    app.add_handler(CommandHandler("auditarventas", cmd_auditar_ventas))

    # Handler genérico para fotos con caption
    app.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, recibir_foto_nueva))

    # CallbackQuery para el menú principal
    app.add_handler(CallbackQueryHandler(manejar_menu, pattern="^menu_"))
    app.add_handler(CallbackQueryHandler(manejar_menu, pattern="^fin_"))
    app.add_handler(CallbackQueryHandler(manejar_menu, pattern="^sel_inv_"))

    # Handler global para callbacks perdidos/reiniciados
    async def callback_invalido(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            await update.callback_query.answer("⚠️ La sesión expiró o el bot se reinició. Vuelve a iniciar la acción.", show_alert=True)
            try:
                await update.callback_query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
    
    app.add_handler(CallbackQueryHandler(callback_invalido))

    logger.info("Bot Maricuchis Store v6.0 iniciado")
    app.run_polling()

if __name__ == "__main__":
    main()
