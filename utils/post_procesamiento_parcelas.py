# utils/post_procesamiento_parcelas.py
"""
Post-procesamiento de parcelas segmentadas por Delineate-Anything.

Filtra falsos positivos basándose en:
  - Área mínima (elimina polígonos pequeños)
  - Compacidad/solidez (elimina formas muy irregulares o fragmentadas)
  - Zona urbana (elimina parcelas dentro o muy cerca de áreas urbanas)
  - NDVI mínimo (elimina áreas sin vegetación activa)
"""

import numpy as np
import geopandas as gpd
from pathlib import Path


CRS_METRICO = "EPSG:32616"

def filtrar_parcelas_por_area(
    geodf: gpd.GeoDataFrame,
    area_minima_m2: float = 1000,
) -> gpd.GeoDataFrame:
    """
    Filtra polígonos menores que el área mínima (en metros cuadrados).
    Reproyecta automáticamente a CRS métrico (EPSG:32616) si es necesario.
    
    Args:
        geodf: GeoDataFrame con geometrías
        area_minima_m2: Área mínima en m² (default: 1000 ≈ 0.1 ha)
    
    Returns:
        GeoDataFrame filtrado (solo parcelas >= area_minima_m2)
    """
    if geodf.empty:
        return geodf.copy()
    
    geodf_metric = geodf.copy()
    if geodf_metric.crs and geodf_metric.crs.is_geographic:
        geodf_metric = geodf_metric.to_crs(CRS_METRICO)
    
    n_antes = len(geodf_metric)
    geodf_filtrado = geodf_metric[geodf_metric.geometry.area >= area_minima_m2].copy()
    n_despues = len(geodf_filtrado)
    
    print(f"  📏 Filtro por área: {n_antes} → {n_despues} parcelas "
          f"(umbral: {area_minima_m2} m²)")
    
    return geodf_filtrado


def filtrar_parcelas_por_compacidad(
    geodf: gpd.GeoDataFrame,
    umbral_compacidad: float = 0.6,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Filtra polígonos con baja solidez/compacidad.

    La compacidad se calcula como area / area_del_convex_hull. Valores cercanos a 1
    indican formas compactas y realistas; valores más bajos suelen corresponder a
    polígonos irregulares o fragmentados producto de errores de delineación.

    Args:
        geodf: GeoDataFrame con geometrías
        umbral_compacidad: Umbral mínimo de compacidad (0-1)
        verbose: Si True, imprime progreso

    Returns:
        GeoDataFrame filtrado (solo parcelas con compacidad >= umbral)
    """
    if geodf.empty:
        return geodf.copy()

    def _calcular_compacidad(geom) -> float:
        if geom is None or geom.is_empty:
            return np.nan

        hull_area = geom.convex_hull.area
        if hull_area <= 0:
            return np.nan

        return geom.area / hull_area

    n_antes = len(geodf)
    geodf_copia = geodf.copy()
    if geodf_copia.crs and geodf_copia.crs.is_geographic:
        geodf_copia = geodf_copia.to_crs(CRS_METRICO)
    geodf_copia["compacidad"] = geodf_copia.geometry.apply(_calcular_compacidad)

    geodf_filtrado = geodf_copia[
        (geodf_copia["compacidad"].notna()) &
        (geodf_copia["compacidad"] >= umbral_compacidad)
    ].copy()
    geodf_filtrado = geodf_filtrado.drop(columns=["compacidad"])

    n_despues = len(geodf_filtrado)
    if verbose:
        print(
            f"  🧩 Filtro por compacidad: {n_antes} → {n_despues} parcelas "
            f"(umbral compacidad >= {umbral_compacidad})"
        )

    return geodf_filtrado


def filtrar_parcelas_por_zona_urbana(
    geodf: gpd.GeoDataFrame,
    zonas_urbanas: gpd.GeoDataFrame,
    umbral_buffer_m: float = 0.0,
    usar_centroide: bool = True,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Elimina parcelas que caen dentro o cerca de zonas urbanas.

    Args:
        geodf: GeoDataFrame con parcelas
        zonas_urbanas: GeoDataFrame con las zonas urbanas/edificadas
        umbral_buffer_m: separación adicional en metros alrededor de las zonas urbanas
        usar_centroide: si True, evalúa el centroide de cada parcela; si False, evalúa toda la geometría
        verbose: Si True, imprime progreso

    Returns:
        GeoDataFrame filtrado sin las parcelas urbanas
    """
    if geodf.empty or zonas_urbanas.empty:
        return geodf.copy()

    geodf_copia = geodf.copy()
    if geodf_copia.crs and geodf_copia.crs.is_geographic:
        geodf_copia = geodf_copia.to_crs(CRS_METRICO)
    zonas = zonas_urbanas.to_crs(geodf_copia.crs)

    if umbral_buffer_m > 0:
        zonas = zonas.buffer(umbral_buffer_m)

    if usar_centroide:
        puntos = geodf_copia.geometry.centroid
        mask = points_within(puntos, zonas.unary_union)
    else:
        mask = geodf_copia.geometry.apply(lambda geom: geom.intersects(zonas.unary_union))

    geodf_filtrado = geodf_copia[~mask].copy()

    n_antes = len(geodf_copia)
    n_despues = len(geodf_filtrado)
    if verbose:
        print(
            f"  🏙️ Filtro por zona urbana: {n_antes} → {n_despues} parcelas "
            f"(buffer: {umbral_buffer_m} m)"
        )

    return geodf_filtrado


def points_within(points, polygon_or_collection):
    """Versión simple para evaluar si puntos están dentro de una geometría o colección."""
    return [point.within(polygon_or_collection) for point in points]


def calcular_ndvi_por_parcela(
    geodf: gpd.GeoDataFrame,
    red: np.ndarray,
    nir: np.ndarray,
    crs_raster: str = "EPSG:32616",
    verbose: bool = True,
) -> np.ndarray:
    """
    Calcula NDVI medio para cada polígono del GeoDataFrame.
    
    NDVI = (NIR - RED) / (NIR + RED + ε)
    
    Args:
        geodf: GeoDataFrame con geometrías (debe estar en el mismo CRS que el raster)
        red: Array 2D con banda roja (píxeles)
        nir: Array 2D con banda NIR (píxeles)
        crs_raster: CRS de los rasters (se asume que geodf ya está en este CRS)
        verbose: Si True, imprime progreso
    
    Returns:
        Array 1D con NDVI medio por parcela
    
    Ejemplo:
        >>> ndvi_valores = calcular_ndvi_por_parcela(gdf, red_band, nir_band)
        >>> gdf['ndvi'] = ndvi_valores
    """
    import rasterio.mask
    from rasterio.transform import from_bounds
    
    if geodf.empty:
        return np.array([])
    
    # Crear transformación raster (asume esquina superior-izquierda)
    # Se asume que red/nir son arrays 2D con resolución 10m
    n_rows, n_cols = red.shape
    # Bounds ficticios (ajusta si tienes bounds reales)
    transform = from_bounds(0, 0, n_cols * 10, n_rows * 10, n_rows, n_cols)
    
    ndvi_list = []
    
    for idx, row in geodf.iterrows():
        try:
            # Crear máscara para este polígono
            mask = rasterio.mask.geometry_mask(
                [row.geometry],
                out_shape=red.shape,
                invert=True,
                transform=transform,
            )
            
            # Extraer píxeles dentro del polígono
            red_px = red[mask]
            nir_px = nir[mask]
            
            if len(red_px) == 0:
                ndvi_list.append(np.nan)
                continue
            
            # Calcular NDVI
            ndvi = (nir_px.astype(float) - red_px.astype(float)) / \
                   (nir_px.astype(float) + red_px.astype(float) + 1e-8)
            
            ndvi_mean = np.nanmean(ndvi)
            ndvi_list.append(ndvi_mean)
            
        except Exception as e:
            if verbose:
                print(f"  ⚠️  Parcela {idx}: error al calcular NDVI: {e}")
            ndvi_list.append(np.nan)
    
    return np.array(ndvi_list)


def filtrar_parcelas_por_ndvi(
    geodf: gpd.GeoDataFrame,
    red: np.ndarray,
    nir: np.ndarray,
    ndvi_minimo: float = 0.3,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Filtra polígonos con NDVI medio menor que el umbral (no-vegetación).
    
    Args:
        geodf: GeoDataFrame con geometrías
        red: Array 2D banda roja (píxeles)
        nir: Array 2D banda NIR (píxeles)
        ndvi_minimo: Umbral de NDVI (default: 0.3 = vegetación moderada)
        verbose: Si True, imprime progreso
    
    Returns:
        GeoDataFrame filtrado (solo parcelas con NDVI >= ndvi_minimo)
    
    Ejemplo:
        >>> gdf_verde = filtrar_parcelas_por_ndvi(gdf, red_band, nir_band, ndvi_minimo=0.25)
        >>> print(f"Parcelas con vegetación: {len(gdf_verde)} / {len(gdf)}")
    """
    if geodf.empty:
        return geodf.copy()
    
    n_antes = len(geodf)
    
    # Calcular NDVI
    ndvi_vals = calcular_ndvi_por_parcela(
        geodf, red, nir, verbose=verbose
    )
    
    # Filtrar
    geodf_copia = geodf.copy()
    geodf_copia['ndvi'] = ndvi_vals
    
    # Solo mantener parcelas con NDVI válido y >= umbral
    geodf_filtrado = geodf_copia[
        (geodf_copia['ndvi'].notna()) & (geodf_copia['ndvi'] >= ndvi_minimo)
    ].copy()
    
    # Opcional: drop la columna ndvi si no la necesitas después
    geodf_filtrado = geodf_filtrado.drop(columns=['ndvi'])
    
    n_despues = len(geodf_filtrado)
    print(f"  🌱 Filtro por NDVI: {n_antes} → {n_despues} parcelas "
          f"(umbral NDVI >= {ndvi_minimo})")
    
    return geodf_filtrado


def procesar_parcelas_segmentadas(
    geodf_crudas: gpd.GeoDataFrame,
    red: np.ndarray = None,
    nir: np.ndarray = None,
    area_minima_m2: float = 1000,
    umbral_compacidad: float = 0.6,
    zonas_urbanas: gpd.GeoDataFrame = None,
    umbral_buffer_m: float = 0.0,
    ndvi_minimo: float = 0.3,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Pipeline completo: filtra parcelas falsas por área, compacidad, zona urbana y NDVI.
    
    Args:
        geodf_crudas: GeoDataFrame con segmentos de Delineate-Anything
        red: Array 2D banda roja (opcional, si None omite filtro NDVI)
        nir: Array 2D banda NIR (opcional, si None omite filtro NDVI)
        area_minima_m2: Umbral de área en m²
        umbral_compacidad: Umbral mínimo de compacidad/solidez (0-1)
        zonas_urbanas: GeoDataFrame opcional con zonas urbanas para filtrar
        umbral_buffer_m: Buffer en metros alrededor de zonas urbanas
        ndvi_minimo: Umbral de NDVI (0-1)
        verbose: Si True, imprime progreso
    
    Returns:
        GeoDataFrame limpio con parcelas validadas
    
    Ejemplo:
        >>> # Solo filtro por área
        >>> gdf_limpio = procesar_parcelas_segmentadas(
        ...     gdf_crudo,
        ...     area_minima_m2=800
        ... )
        >>> 
        >>> # Filtro completo con NDVI
        >>> gdf_limpio = procesar_parcelas_segmentadas(
        ...     gdf_crudo,
        ...     red=red_band,
        ...     nir=nir_band,
        ...     area_minima_m2=800,
        ...     ndvi_minimo=0.25
        ... )
    """
    if verbose:
        print(f"\n🔍 Procesando {len(geodf_crudas)} parcelas segmentadas...")
    
    # Paso 1: Filtro por área
    gdf = filtrar_parcelas_por_area(
        geodf_crudas,
        area_minima_m2=area_minima_m2,
    )

    # Paso 2: Filtro por compacidad (opcional, pero activo por defecto)
    gdf = filtrar_parcelas_por_compacidad(
        gdf,
        umbral_compacidad=umbral_compacidad,
        verbose=verbose,
    )
    
    # Paso 3: Filtro por zona urbana (opcional)
    if zonas_urbanas is not None:
        gdf = filtrar_parcelas_por_zona_urbana(
            gdf,
            zonas_urbanas,
            umbral_buffer_m=umbral_buffer_m,
            verbose=verbose,
        )

    # Paso 4: Filtro por NDVI (opcional)
    if red is not None and nir is not None:
        gdf = filtrar_parcelas_por_ndvi(
            gdf,
            red,
            nir,
            ndvi_minimo=ndvi_minimo,
            verbose=verbose,
        )
    else:
        if verbose:
            print("  ⏭️  Filtro NDVI omitido (no se proporcionaron bandas RED/NIR)")
    
    if verbose:
        print(f"✅ Resultado final: {len(gdf)} parcelas válidas\n")
    
    return gdf
