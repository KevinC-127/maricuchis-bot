import re

with open('ia_gemini.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_buttons = '''        [
            InlineKeyboardButton("💰 Ganancias",          callback_data="menu_ganancias"),
            InlineKeyboardButton("💸 Gastos",             callback_data="menu_gasto"),
        ],
        [
            InlineKeyboardButton("🔄 Devolución",         callback_data="menu_devolucion"),
            InlineKeyboardButton("⚖️ Comparar prendas",   callback_data="menu_comparar"),
        ],'''

code = re.sub(
    r'        \[\s*InlineKeyboardButton\("💰 Ganancias",\s*callback_data="menu_ganancias"\),\s*InlineKeyboardButton\("⚖️ Comparar prendas",\s*callback_data="menu_comparar"\),\s*\],',
    new_buttons,
    code
)

with open('ia_gemini.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
