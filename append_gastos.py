import os

code = '''
async def crear_gasto_notion(nombre: str, monto: float, fecha_iso: str) -> bool:
    import asyncio, functools
    return await asyncio.to_thread(functools.partial(_sync_crear_gasto_notion, nombre, monto, fecha_iso))

def _sync_crear_gasto_notion(nombre: str, monto: float, fecha_iso: str) -> bool:
    import requests
    from config import NOTION_HEADERS, NOTION_GASTOS_ID
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_GASTOS_ID},
        "properties": {
            "Nombre": {"title": [{"text": {"content": nombre}}]},
            "Monto": {"number": monto},
            "Fecha": {"date": {"start": fecha_iso}}
        }
    }
    try:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=15)
        return r.status_code == 200
    except:
        return False
'''

with open('notion_api.py', 'a', encoding='utf-8') as f:
    f.write(code)

print("done")
