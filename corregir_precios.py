import os
import requests

def main():
    # Leer tokens del entorno
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
    NOTION_VENTAS_ID = os.environ.get("NOTION_VENTAS_ID")
    
    if not NOTION_TOKEN or not NOTION_VENTAS_ID:
        print("ERROR: Asegúrate de ejecutar este script en la misma consola/entorno donde corre tu bot, para que tenga acceso a NOTION_TOKEN.")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    
    print("Buscando ventas en Notion...")
    url = f"https://api.notion.com/v1/databases/{NOTION_VENTAS_ID}/query"
    
    # Paginar para revisar absolutamente todas las ventas
    ventas = []
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
            
        r = requests.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            print("Error API Notion:", r.text)
            return
            
        data = r.json()
        ventas.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
        print(f"Descargadas {len(ventas)} ventas...")
        
    corregidas = 0
    print(f"Analizando {len(ventas)} ventas en total...")
    
    for page in ventas:
        props = page["properties"]
        page_id = page["id"]
        
        prenda_n = props.get("Prenda", {}).get("rich_text", [])
        nombre = prenda_n[0]["text"]["content"] if prenda_n else "Desconocido"
        
        precio_venta = props.get("Precio Venta", {}).get("number") or 0.0
        descuento = props.get("Descuento", {}).get("number") or 0.0
        
        # Detectar el bug: un descuento que tiene parte decimal (ej. 0.50)
        # Esto ocurre porque el precio real era X.50 pero el bot registró X.00
        # Ej: Precio Original 12.50 -> Bot guardó Precio Venta 12.00, Descuento 0.50
        if descuento > 0 and round(descuento % 1, 2) != 0:
            falso_desc = round(descuento % 1, 2)
            
            nuevo_precio = round(precio_venta + falso_desc, 2)
            nuevo_desc = round(descuento - falso_desc, 2)
            
            print(f"\nCorrigiendo -> {nombre}")
            print(f"  Antes   : Precio = {precio_venta:.2f} | Desc = {descuento:.2f}")
            print(f"  Después : Precio = {nuevo_precio:.2f} | Desc = {nuevo_desc:.2f}")
            
            # Actualizar en Notion
            update_payload = {
                "properties": {
                    "Precio Venta": {"number": nuevo_precio},
                    "Descuento": {"number": nuevo_desc}
                }
            }
            res = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json=update_payload)
            if res.status_code == 200:
                print("  ✅ Actualizado correctamente.")
                corregidas += 1
            else:
                print("  ❌ Error al actualizar:", res.text)
                
    print(f"\n¡Proceso finalizado! Se corrigieron {corregidas} ventas.")

if __name__ == "__main__":
    main()
