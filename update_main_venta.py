import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update import for venta_handler
new_imports = '''from handlers_venta import (
    cmd_vendi, venta_buscar_prenda, venta_confirmar_prenda, venta_recibir_cantidad,
    venta_recibir_precio, venta_recibir_precio_manual, venta_volver_cantidad,
    venta_mas_prendas, venta_pedir_cliente, venta_recibir_cliente, venta_recibir_fecha,
    venta_recibir_descuento, venta_finalizar,
    VENTA_BUSCAR, VENTA_CONFIRMAR, VENTA_CANTIDAD, VENTA_PRECIO,
    VENTA_MAS, VENTA_CLIENTE, VENTA_FECHA, VENTA_DESCUENTO, VENTA_PAGO
)
'''
if 'from handlers_venta import' not in code:
    code = code.replace('from handlers import (', new_imports + 'from handlers import (')

# Rewrite venta_handler in main.py
new_venta_handler = '''    # ConversationHandler — Venta
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
    )'''

code = re.sub(
    r'    # ConversationHandler — Venta.*?per_message=False,\n    \)',
    new_venta_handler,
    code,
    flags=re.DOTALL
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("done")
