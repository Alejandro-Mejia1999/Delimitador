"""
generar_mascara_lclu.py — Descarga ESA WorldCover 2021 como máscara LCLU
para filtrar parcelas en zonas urbanas durante la segmentación.

Uso:
    python generar_mascara_lclu.py

Requiere autenticación openEO (CDSE). El proceso es:
  1. El script mostrará una URL como: https://identity.dataspace.copernicus.eu/auth/...
  2. COPIA ESA URL Y ÁBRELA EN TU NAVEGADOR
  3. Inicia sesión con tu cuenta de Copernicus Data Space (o crea una gratis)
  4. Una vez autenticado, vuelve a esta terminal y espera a que termine
"""
from pathlib import Path
import openeo
import rasterio

RUTA_IMAGEN = Path(__file__).parent / "data" / "images" / "Sample" / "sentinel2_rgb_completa.tif"
RUTA_SALIDA = Path(__file__).parent / "data" / "masks" / "Sample.tif"

def obtener_bounds_desde_imagen(ruta_imagen):
    with rasterio.open(ruta_imagen) as src:
        if src.crs and src.crs.to_string() != "EPSG:4326":
            from rasterio.warp import transform_bounds
            bounds_4326 = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        else:
            bounds_4326 = src.bounds
    print(f"  Bounds (EPSG:4326): west={bounds_4326[0]:.4f}, south={bounds_4326[1]:.4f}, east={bounds_4326[2]:.4f}, north={bounds_4326[3]:.4f}")
    return {"west": bounds_4326[0], "south": bounds_4326[1], "east": bounds_4326[2], "north": bounds_4326[3]}

def descargar_worldcover(bounds_4326, ruta_salida):
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    print("Conectando a openEO CDSE...")
    conn = openeo.connect("https://openeo.dataspace.copernicus.eu")

    print()
    print("=" * 70)
    print("  📋 INSTRUCCIONES DE AUTENTICACIÓN:")
    print("=" * 70)
    print("  1. Se te mostrará una URL debajo")
    print("  2. CÓPIALA Y PÉGALA EN TU NAVEGADOR")
    print("  3. Inicia sesión con tu cuenta de Copernicus Data Space")
    print("     (Si no tienes: https://dataspace.copernicus.eu/ → Registrarse)")
    print("  4. Autoriza la aplicación")
    print("  5. VUELVE A ESTA TERMINAL y espera a que termine")
    print("=" * 70)
    print()

    conn.authenticate_oidc(max_poll_time=600)

    print("Cargando colección ESA_WORLDCOVER_10M_2021_V2...")
    cube = conn.load_collection(
        "ESA_WORLDCOVER_10M_2021_V2",
        spatial_extent=bounds_4326,
        bands=["MAP"],
    )

    print(f"Descargando máscara a {ruta_salida} (puede tomar varios minutos)...")
    cube.download(ruta_salida)

    with rasterio.open(ruta_salida) as src:
        vals = sorted(set(src.read(1).flatten().tolist()))
    print(f"Clases presentes: {vals}")
    print("  10=Árboles 20=Arbustos 30=Pastizal 40=Cultivos 50=Urbano 60=Suelo 80=Agua")

if __name__ == "__main__":
    print("=== Generador de máscara LCLU (ESA WorldCover 2021) ===")
    print(f"Imagen: {RUTA_IMAGEN}")
    if not RUTA_IMAGEN.exists():
        print(f"ERROR: No existe {RUTA_IMAGEN}")
        exit(1)
    bounds = obtener_bounds_desde_imagen(RUTA_IMAGEN)
    descargar_worldcover(bounds, RUTA_SALIDA)
    print("¡Listo! Ahora ejecuta la segmentación con el filtro urbano activado.")
    print("  python delineate.py -b batch_sample.yaml")
