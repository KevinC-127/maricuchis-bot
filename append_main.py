import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

import_statement = '''from handlers_gastos_devoluciones import (
    cmd_gasto, gasto_recibir_nombre, gasto_recibir_monto,
    GASTO_NOMBRE, GASTO_MONTO, GASTO_FECHA,
    cmd_devolucion, devolucion_buscar, devolucion_confirmar,
    DEV_BUSCAR, DEV_CONFIRMAR
)
'''

if 'from handlers_gastos_devoluciones' not in code:
    code = code.replace('from handlers import (', import_statement + 'from handlers import (')

handlers_code = '''
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
'''

if 'gasto_handler =' not in code:
    code = code.replace('app.add_handler(ia_handler)', handlers_code + '\n    app.add_handler(ia_handler)')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("done")
