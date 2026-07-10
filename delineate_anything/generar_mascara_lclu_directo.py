"""
generar_mascara_lclu_directo.py — Descarga ESA WorldCover 2021 vía STAC público
(sin autenticación openEO).

Requiere: pip install requests rasterio shapely
"""
import json
import rasterio
import requests
from pathlib import Path
from rasterio.warp import transform_bounds
from shapely.geometry import shape, box

RUTA_IMAGEN = Path(__file__).parent / "data" / "images" / "Sample" / "sentinel2_rgb_completa.tif"
RUTA_SALIDA = Path(__file__).parent / "data" / "masks" / "Sample.tif"

STAC_URL = "https://stac.dataspace.copernicus.eu/v1"
COLECCION = "ESA_WORLDCOVER_10M_2021_V2"

def obtener_bounds(ruta_imagen):
    with rasterio.open(ruta_imagen) as src:
        if src.crs and src.crs.to_string() != "EPSG:4326":
            b = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        else:
            b = src.bounds
    return b

def buscar_item_stac(bounds_4326):
    geo_json = {
        "type": "Feature",
        "geometry": box(*bounds_4326).__geo_interface__,
        "properties": {}
    }
    params = {
        "collections": COLECCION,
        "intersects": json.dumps(geo_json["geometry"]),
        "limit": 10
    }
    r = requests.get(f"{STAC_URL}/search", params=params)
    r.raise_for_status()
    features = r.json().get("features", [])
    if not features:
        raise RuntimeError("No se encontraron tiles de WorldCover para esta área")
    return features

def descargar_worldcover(bounds_4326, ruta_salida):
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    print("Buscando tiles de WorldCover en STAC...")
    items = buscar_item_stac(bounds_4326)
    print(f"  Encontrados {len(items)} tile(s)")

    # Descargar el primer tile que cubra el área
    for item in items:
        asset = item.get("assets", {}).get("MAP", {})
        href = asset.get("href")
        if not href:
            continue
        print(f"  Descargando: {href}")
        r = requests.get(href, stream=True)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        desc = total // 1024 // 1024
        print(f"  Tamaño: ~{desc} MB")
        with open(ruta_salida, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk) if chunk else None
        print("  Descarga completada, recortando al área de estudio...")
        break

    with rasterio.open(ruta_salida) as src:
        vals = sorted(set(src.read(1).flatten().tolist()))
    print(f"Clases presentes: {vals}")

if __name__ == "__main__":
    print("=== Generador de máscara LCLU vía STAC directo ===")
    print(f"Imagen: {RUTA_IMAGEN}")
    if not RUTA_IMAGEN.exists():
        print(f"ERROR: No existe {RUTA_IMAGEN}")
        exit(1)
    bounds = obtener_bounds(RUTA_IMAGEN)
    print(f"Bounds: west={bounds[0]:.4f}, south={bounds[1]:.4f}, east={bounds[2]:.4f}, north={bounds[3]:.4f}")
    descargar_worldcover(bounds, RUTA_SALIDA)
    print(f"¡Listo! Máscara guardada en {RUTA_SALIDA}")
