import subprocess
import os
from pathlib import Path
import geopandas as gpd
import yaml

from utils.post_procesamiento_parcelas import procesar_parcelas_segmentadas

# --- Configuración de Rutas Relativas ---
# Asumiendo que ejecutas desde la raíz del proyecto
_REPO_ROOT = Path(__file__).resolve().parents[1]  # Ajusta si tu estructura difiere

DELINEATE_ANYTHING_ROOT = _REPO_ROOT / "delineate_anything"
DELINEATE_BATCH_CONFIG = DELINEATE_ANYTHING_ROOT / "batch_sample.yaml"
DELINEATE_SCRIPT = DELINEATE_ANYTHING_ROOT / "delineate.py"
URBAN_LAYER_CANDIDATES = [
    _REPO_ROOT / "data" / "urban" / "urban.gpkg",
    _REPO_ROOT / "data" / "urban" / "urban.geojson",
    _REPO_ROOT / "data" / "urban" / "urban.shp",
    _REPO_ROOT / "data" / "urban.gpkg",
    _REPO_ROOT / "data" / "urban.geojson",
    _REPO_ROOT / "data" / "urban.shp",
]

# En lugar de buscar un .venv local, apuntamos dinámicamente al Conda del sistema
CONDA_EXE = os.environ.get("CONDA_EXE", r"C:\Users\USER\anaconda3\Scripts\conda.exe")
#CONDA_EXE = os.environ.get("CONDA_EXE", r"C:\Users\mayno\miniconda3\Scripts\conda.exe")
CONDA_ENV_NAME = "tesis_maiz"


def _load_spatial_extent(geojson_path: Path) -> dict:
    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        raise ValueError(f"No se encontraron geometrías en {geojson_path}")

    geometry = gdf.geometry.unary_union
    return geometry.__geo_interface__


def _cargar_capa_urbana() -> gpd.GeoDataFrame | None:
    """Intenta cargar una capa urbana desde rutas comunes del proyecto."""
    for candidate in URBAN_LAYER_CANDIDATES:
        if candidate.exists():
            try:
                gdf = gpd.read_file(candidate)
                if not gdf.empty:
                    return gdf
            except Exception:
                continue
    return None


def _postprocesar_geo_packages_delineados(
    batch_config: Path | str,
    verbose: bool = True,
) -> None:
    """Aplica un filtro geométrico extra a los GeoPackages generados por Delineate-Anything."""
    batch_config_path = Path(batch_config)
    if not batch_config_path.exists():
        return

    try:
        batch_data = yaml.safe_load(batch_config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"  ⚠️ No fue posible leer la configuración de batch para postproceso: {exc}")
        return

    output_root = batch_data.get("output_root", "")
    if not output_root:
        return

    output_root_path = Path(output_root)
    if not output_root_path.is_absolute():
        output_root_path = (batch_config_path.parent / output_root_path).resolve()

    if not output_root_path.exists():
        print(f"  ⚠️ No se encontró el directorio de salida para postproceso: {output_root_path}")
        return

    gpkg_paths = sorted(
        path for path in output_root_path.glob("*.gpkg") if not path.name.endswith(".simp.gpkg")
    )
    if not gpkg_paths:
        print(f"  ⚠️ No se encontraron GeoPackages para postproceso en {output_root_path}")
        return

    for gpkg_path in gpkg_paths:
        try:
            gdf = gpd.read_file(gpkg_path)
        except Exception as exc:
            print(f"  ⚠️ No se pudo leer {gpkg_path} para postproceso: {exc}")
            continue

        if gdf.empty:
            print(f"  ⚠️ El archivo {gpkg_path} no contiene geometrías para filtrar")
            continue

        zonas_urbanas = _cargar_capa_urbana()
        if zonas_urbanas is not None:
            print(f"  🏙️ Se usará una capa urbana para filtrar parcelas en {gpkg_path}")
        else:
            print(f"  ℹ️ No se encontró una capa urbana para filtrar; se omite este paso")

        gdf_limpio = procesar_parcelas_segmentadas(
            gdf,
            zonas_urbanas=zonas_urbanas,
            umbral_buffer_m=50,
            verbose=verbose,
        )

        if gdf_limpio.empty:
            print(f"  ⚠️ El filtro eliminó todas las parcelas en {gpkg_path}")
            continue

        gdf_limpio.to_file(gpkg_path, driver="GPKG", mode="w")
        print(f"  ✅ Postproceso aplicado a {gpkg_path}")


def ejecutar_delineate_anything_local(
    batch_config: Path | str = DELINEATE_BATCH_CONFIG,
) -> None:
    """Ejecuta Delineate-Anything localmente dentro del entorno Conda 'tesis_maiz' con GPU."""
    batch_config_path = Path(batch_config)
    
    # Validaciones previas de archivos
    if not batch_config_path.exists():
        raise FileNotFoundError(f"No existe el archivo de batch: {batch_config_path}")
    if not DELINEATE_SCRIPT.exists():
        raise FileNotFoundError(f"No se encontró el script de delineación en: {DELINEATE_SCRIPT}")
    if not os.path.exists(CONDA_EXE):
        raise FileNotFoundError(f"No se detectó el ejecutable de Conda en la ruta especificada: {CONDA_EXE}")

    print(f" Lanzando inferencia por lotes en entorno Conda '{CONDA_ENV_NAME}' usando GPU...")
    print(f"Configuración utilizada: {batch_config_path.name}")

    # La magia en Windows: Usamos 'conda run -n nombre_entorno'
    # Esto inicializa CUDA, GDAL y todas las variables nativas automáticamente
    comando = [
        CONDA_EXE, "run", 
        "-n", CONDA_ENV_NAME, 
        "--no-capture-output",  # Para que veas el progreso de YOLO en tiempo real en tu consola
        "python", str(DELINEATE_SCRIPT), 
        "-b", str(batch_config_path)
    ]

    try:
        subprocess.run(
            comando,
            cwd=str(DELINEATE_ANYTHING_ROOT),
            check=True
        )
        print("\n Inferencia por lotes completada con éxito.")
        _postprocesar_geo_packages_delineados(batch_config_path, verbose=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] El script falló durante la ejecución. Código de salida: {e.returncode}")
        raise e