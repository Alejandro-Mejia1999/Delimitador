"""
generar_mascara_ndvi.py — Descarga imágenes Sentinel-2 recientes con baja nubosidad
y genera una máscara de vegetación (NDVI) para filtrar parcelas en zonas sin
vegetación (urbano, solares baldíos, suelo desnudo).

La máscara resultante tiene 3 clases:
  0 = Nodata / nubes
  1 = Vegetación activa (cultivos, bosque, pasto) — NDVI >= 0.30
  2 = Sin vegetación (urbano, solares, suelo desnudo, agua) — NDVI < 0.30

Usa filter_classes: [2] en conf_sample.yaml para eliminar parcelas sin vegetación.

Uso:
    python generar_mascara_ndvi.py

Requiere autenticación openEO:
  1. Copia la URL que aparece y pégala en tu navegador
  2. Inicia sesión con tu cuenta de Copernicus Data Space
  3. Vuelve a la terminal y espera
"""
from pathlib import Path
import openeo
import rasterio
import numpy as np

RUTA_IMAGEN = Path(__file__).parent / "data" / "images" / "Sample" / "sentinel2_rgb_completa.tif"
RUTA_SALIDA = Path(__file__).parent / "data" / "masks" / "Sample.tif"

def obtener_bounds(ruta):
    with rasterio.open(ruta) as src:
        if src.crs and src.crs.to_string() != "EPSG:4326":
            from rasterio.warp import transform_bounds
            b = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        else:
            b = src.bounds
    return {"west": b[0], "south": b[1], "east": b[2], "north": b[3]}

def descargar_mascara_ndvi(bounds, ruta_salida):
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    conn = openeo.connect("https://openeo.dataspace.copernicus.eu")
    print("-" * 70)
    print("  ABRE EL NAVEGADOR EN LA URL QUE APARECERÁ ABAJO")
    print("  Inicia sesión con tu cuenta de Copernicus Data Space")
    print("  Luego vuelve a esta terminal y espera (máx 10 min)")
    print("-" * 70)
    conn.authenticate_oidc(max_poll_time=600)

    print("Cargando Sentinel-2 L2A (2025-01 a 2026-07, < 30% nubes)...")
    s2 = conn.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=bounds,
        temporal_extent=["2025-01-01", "2026-07-01"],
        bands=["B04", "B08"],
    ).filter_property("eo:cloud_cover", "<=", 30)

    def calc_ndvi(data, ctx=None):
        nir = data.array_element(index=1)
        red = data.array_element(index=0)
        return (nir - red) / (nir + red + 0.0001)

    print("Calculando mediana temporal y NDVI...")
    mediana = s2.reduce_dimension(dimension="t", reducer="median")
    ndvi_cube = mediana.reduce_dimension(dimension="bands", reducer=calc_ndvi)

    temp = str(ruta_salida.parent / "_temp_ndvi.tif")
    print("Descargando NDVI (puede tomar varios minutos)...")
    ndvi_cube.download(temp)

    with rasterio.open(temp) as src:
        ndvi = src.read(1)
        meta = src.meta.copy()

    mascara = np.zeros_like(ndvi, dtype=np.uint8)
    mascara[ndvi >= 0.30] = 1
    mascara[(ndvi < 0.30) & (ndvi > -999)] = 2

    meta.update(dtype=rasterio.uint8, count=1, nodata=0)
    with rasterio.open(ruta_salida, "w", **meta) as dst:
        dst.write(mascara, 1)

    Path(temp).unlink()

    n_veg = int((mascara == 1).sum())
    n_noveg = int((mascara == 2).sum())
    total = n_veg + n_noveg
    print(f"Vegetación: {n_veg} px ({100*n_veg/total:.1f}%)")
    print(f"Sin vegetación: {n_noveg} px ({100*n_noveg/total:.1f}%)")
    print("Clases: 1=Vegetación 2=Sin vegetación (urbano+solares)")

if __name__ == "__main__":
    print("=== Generador de máscara NDVI ===")
    if not RUTA_IMAGEN.exists():
        print(f"ERROR: No existe {RUTA_IMAGEN}")
        exit(1)
    bounds = obtener_bounds(RUTA_IMAGEN)
    print(f"Bounds: {bounds}")
    descargar_mascara_ndvi(bounds, RUTA_SALIDA)
    print(f"Máscara guardada en {RUTA_SALIDA}")
    print("Luego actualiza conf_sample.yaml: filter_classes: [2]")
