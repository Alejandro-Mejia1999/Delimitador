"""
descargar_dynamic_world.py — Descarga la imagen más reciente de Dynamic World
(Google Earth Engine) con bajo % de nubosidad, para las mismas coordenadas
que se usó en la máscara ESA WorldCover anterior.

Requiere:
    pip install earthengine-api rasterio requests

Autenticación (una sola vez por máquina):
    1. Corré: earthengine authenticate
       (o dejá que el script lo dispare solo la primera vez)
    2. Se abrirá una URL en el navegador -> iniciá sesión con tu cuenta Google
    3. Si te pide "Cloud Project", registrá uno NUEVO como "noncommercial"
       en https://signup.earthengine.google.com -> esto NO debería pedir tarjeta.
    4. Reemplazá GEE_PROJECT abajo con el ID de ese proyecto.
"""
import datetime
from pathlib import Path
import ee
import rasterio
import requests
import numpy as np

GEE_PROJECT = "ee-alemejia477"  # tu Project ID de Earth Engine

RUTA_IMAGEN = Path(__file__).parent / "data" / "images" / "Sample" / "sentinel2_rgb_completa.tif"
RUTA_SALIDA = Path(__file__).parent / "data" / "masks" / "Sample.tif"  # OJO: "Sample" con S mayúscula

DIAS_HACIA_ATRAS = 180      # ventana de búsqueda hacia el pasado
NUBOSIDAD_MAXIMA = 20       # % máximo de nubes aceptado en la escena Sentinel-2


def obtener_bounds_desde_imagen(ruta_imagen):
    with rasterio.open(ruta_imagen) as src:
        if src.crs and src.crs.to_string() != "EPSG:4326":
            from rasterio.warp import transform_bounds
            bounds_4326 = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        else:
            bounds_4326 = src.bounds
    print(f"  Bounds (EPSG:4326): west={bounds_4326[0]:.4f}, south={bounds_4326[1]:.4f}, "
          f"east={bounds_4326[2]:.4f}, north={bounds_4326[3]:.4f}")
    return bounds_4326


def descargar_dynamic_world(bounds_4326, ruta_salida):
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    print("Inicializando Earth Engine...")
    try:
        ee.Initialize(project=GEE_PROJECT)
    except Exception:
        print("No autenticado todavía, abriendo flujo de autenticación...")
        ee.Authenticate()
        ee.Initialize(project=GEE_PROJECT)

    west, south, east, north = bounds_4326
    aoi = ee.Geometry.Rectangle([west, south, east, north])

    fin = ee.Date(datetime.datetime.utcnow().strftime("%Y-%m-%d"))
    inicio = fin.advance(-DIAS_HACIA_ATRAS, "day")

    s2 = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
          .filterBounds(aoi)
          .filterDate(inicio, fin)
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", NUBOSIDAD_MAXIMA)))

    dw = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
          .filterBounds(aoi)
          .filterDate(inicio, fin))

    join = ee.Join.simple()
    filtro = ee.Filter.equals(leftField="system:index", rightField="system:index")
    dw_baja_nubosidad = ee.ImageCollection(join.apply(dw, s2, filtro))

    n = dw_baja_nubosidad.size().getInfo()
    print(f"Escenas encontradas con <{NUBOSIDAD_MAXIMA}% de nubes en los últimos {DIAS_HACIA_ATRAS} días: {n}")
    if n == 0:
        raise RuntimeError(
            "No se encontraron escenas suficientemente despejadas. "
            "Probá subiendo NUBOSIDAD_MAXIMA o DIAS_HACIA_ATRAS."
        )

    # MOSAICO: ordena de más reciente a más vieja, y rellena huecos con la
    # siguiente disponible en vez de dejar vacíos sin dato
    coleccion_ordenada = dw_baja_nubosidad.select("label").sort("system:time_start", False)
    mosaico = coleccion_ordenada.mosaic().clip(aoi)

    # 99 = "sin dato real" (no confundir con clase 0 = Agua)
    label_final = mosaico.unmask(99).toByte()

    print(f"Descargando máscara a {ruta_salida}...")
    url = label_final.getDownloadURL({
        "region": aoi,
        "scale": 10,
        "crs": "EPSG:4326",
        "format": "GEO_TIFF",
    })
    resp = requests.get(url)
    resp.raise_for_status()
    ruta_salida.write_bytes(resp.content)

    # Fijar el nodata correcto en los metadatos del archivo descargado
    with rasterio.open(ruta_salida, "r+") as dst:
        dst.nodata = 99

    with rasterio.open(ruta_salida) as src:
        band = src.read(1)
        vals, counts = np.unique(band, return_counts=True)
        total = band.size
        print("Clases presentes:")
        for v, c in zip(vals, counts):
            etiqueta = "SIN DATO" if v == 99 else str(v)
            print(f"  {etiqueta}: {100*c/total:.2f}%")
    print("  0=Agua 1=Árboles 2=Pasto 3=Veg.inundada 4=Cultivos 5=Arbustos 6=Urbano 7=Suelo desnudo 8=Nieve/hielo")


if __name__ == "__main__":
    print("=== Generador de máscara LCLU (Dynamic World, mosaico reciente con baja nubosidad) ===")
    print(f"Imagen: {RUTA_IMAGEN}")
    if not RUTA_IMAGEN.exists():
        print(f"ERROR: No existe {RUTA_IMAGEN}")
        exit(1)
    bounds = obtener_bounds_desde_imagen(RUTA_IMAGEN)
    descargar_dynamic_world(bounds, RUTA_SALIDA)
    print("¡Listo! Ahora ajustá mask_info en conf_sample.yaml:")
    print("  range: 101")
    print("  filter_classes: [6]   # urbano")
    print("  clip_classes: [0]     # agua")
    print("Y corré:")
    print("  python delineate.py -b batch_sample.yaml")