# utils/post_procesamiento_parcelas.py
"""
Post-procesamiento de parcelas segmentadas por Delineate-Anything.

Filtra falsos positivos basándose en:
  - Área mínima (elimina polígonos pequeños)
  - NDVI mínimo (elimina áreas sin vegetación activa)
"""

import numpy as np
import geopandas as gpd
from pathlib import Path


def filtrar_parcelas_por_area(
    geodf: gpd.GeoDataFrame,
    area_minima_m2: float = 1000,
) -> gpd.GeoDataFrame:
    """
    Filtra polígonos menores que el área mínima (en metros cuadrados).
    
    Args:
        geodf: GeoDataFrame con geometrías en CRS métrico (EPSG:32616 recomendado)
        area_minima_m2: Área mínima en m² (default: 1000 ≈ 0.1 ha)
    
    Returns:
        GeoDataFrame filtrado (solo parcelas >= area_minima_m2)
    
    Ejemplo:
        >>> gdf_limpio = filtrar_parcelas_por_area(gdf_crudo, area_minima_m2=500)
        >>> print(f"Parcelas válidas: {len(gdf_limpio)} / {len(gdf_crudo)}")
    """
    if geodf.empty:
        return geodf.copy()
    
    n_antes = len(geodf)
    geodf_filtrado = geodf[geodf.geometry.area >= area_minima_m2].copy()
    n_despues = len(geodf_filtrado)
    
    print(f"  📏 Filtro por área: {n_antes} → {n_despues} parcelas "
          f"(umbral: {area_minima_m2} m²)")
    
    return geodf_filtrado


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
    ndvi_minimo: float = 0.3,
    verbose: bool = True,
) -> gpd.GeoDataFrame:
    """
    Pipeline completo: filtra parcelas falsas por área y NDVI.
    
    Args:
        geodf_crudas: GeoDataFrame con segmentos de Delineate-Anything
        red: Array 2D banda roja (opcional, si None omite filtro NDVI)
        nir: Array 2D banda NIR (opcional, si None omite filtro NDVI)
        area_minima_m2: Umbral de área en m²
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
    
    # Paso 2: Filtro por NDVI (opcional)
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
