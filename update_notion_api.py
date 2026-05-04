import re

with open('notion_api.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Update async def
code = re.sub(
    r'async def crear_venta_notion\(prenda_id: str, cantidad: int, precio_final: float, ganancia: float, fecha_iso: str, cliente: str = "", descuento: float = 0\.0\) -> bool:',
    'async def crear_venta_notion(prenda_id: str, cantidad: int, precio_final: float, ganancia: float, fecha_iso: str, cliente: str = "", descuento: float = 0.0, estado: str = "Completado") -> bool:',
    code
)

code = re.sub(
    r'return await asyncio\.to_thread\(functools\.partial\(_sync_crear_venta_notion, prenda_id, cantidad, precio_final, ganancia, fecha_iso, cliente, descuento\)\)',
    'return await asyncio.to_thread(functools.partial(_sync_crear_venta_notion, prenda_id, cantidad, precio_final, ganancia, fecha_iso, cliente, descuento, estado))',
    code
)

# Update sync def
code = re.sub(
    r'def _sync_crear_venta_notion\(prenda_id: str, cantidad: int, precio_final: float, ganancia: float, fecha_iso: str, cliente: str = "", descuento: float = 0\.0\) -> bool:',
    'def _sync_crear_venta_notion(prenda_id: str, cantidad: int, precio_final: float, ganancia: float, fecha_iso: str, cliente: str = "", descuento: float = 0.0, estado: str = "Completado") -> bool:',
    code
)

# Update payload
new_payload = '''"properties": {
            "Prenda": {"relation": [{"id": prenda_id}]},
            "Cantidad": {"number": cantidad},
            "Precio Total": {"number": precio_final},
            "Ganancia Neta": {"number": ganancia},
            "Fecha": {"date": {"start": fecha_iso}},
            "Cliente": {"rich_text": [{"text": {"content": cliente}}]},
            "Descuento Aplicado": {"number": descuento},
            "Estado": {"select": {"name": estado}},
            "Tipo": {"select": {"name": "Venta"}}
        }'''

# Replace properties in _sync_crear_venta_notion
# We use a naive approach since it's the only one with this exact signature
code = re.sub(
    r'"properties": \{[\s\S]*?"Descuento Aplicado": \{"number": descuento\}\s*\}',
    new_payload,
    code
)

with open('notion_api.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("done")
