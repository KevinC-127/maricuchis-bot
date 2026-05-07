# ============================================================
# MARICUCHIS STORE BOT v5.0 — MAIN.PY COMPLETO
# Versión: 4.23 | Mayo 2026
# Novedades: v5.0 Asíncrono, súper veloz, multi-admin
# ============================================================
import os
import logging
import warnings

warnings.filterwarnings("ignore", message=".*per_message.*", category=UserWarning)
warnings.filterwarnings('ignore', category=UserWarning, module='telegram')

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# VARIABLES DE ENTORNO
# ------------------------------------------------------------
TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN")
NOTION_TOKEN        = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VENTAS_ID   = os.getenv("NOTION_VENTAS_ID")
NOTION_GASTOS_ID   = os.getenv("NOTION_GASTOS_ID", "3563d6e7c6ee8040b93cd0d14b135551")
IMGBB_API_KEY       = os.environ.get("IMGBB_API_KEY")
ADMIN_CHAT_ID       = os.environ.get("ADMIN_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise ValueError("ERROR: TELEGRAM_TOKEN no encontrado en variables de entorno")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ------------------------------------------------------------
# ESTADOS DE CONVERSACION
# ------------------------------------------------------------
SINFOTO_NOMBRE, SINFOTO_DATOS                           = 10, 11
# Estados flujo nueva prenda guiado
NP_NOMBRE, NP_COSTO, NP_PRECIO, NP_STOCK_TIPO, NP_STOCK_DOCENAS, NP_STOCK_UNICA = 80,81,82,83,84,85
NP_TIENDA, NP_FECHA_MES, NP_FECHA_DIA, NP_FOTO                                  = 86,87,88,89
NP_EDIT_CAMPO, NP_EDIT_VALOR, NP_EDIT_FOTO                                       = 100,101,102
ADJFOTO_BUSCAR, ADJFOTO_CONFIRMAR, ADJFOTO_RECIBIR      = 20, 21, 22
VENTA_BUSCAR, VENTA_CONFIRMAR, VENTA_CANTIDAD, VENTA_PRECIO, VENTA_FECHA, VENTA_CLIENTE, VENTA_DESCUENTO = 30, 31, 32, 33, 34, 35, 36
ELIMINAR_VENTA_BUSCAR, ELIMINAR_VENTA_CONFIRMAR = 70, 71
STOCK_BUSCAR, STOCK_CONFIRMAR                           = 40, 41
EDITAR_BUSCAR, EDITAR_CONFIRMAR, EDITAR_CAMPO, EDITAR_VALOR = 50, 51, 52, 53
ELIMINAR_BUSCAR, ELIMINAR_CONFIRMAR                     = 60, 61
FOTO_BUSCAR, FOTO_CONFIRMAR                             = 80, 81
COMPARAR_BUSCAR                                         = 90
VENTA_MAS, VENTA_PAGO                                   = 37, 38

