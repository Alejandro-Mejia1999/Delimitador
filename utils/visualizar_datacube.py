import holoviews as hv
import hvplot.xarray
import xarray as xr
import sys

def visualizar_banda(ruta_netcdf, banda='B04', cmap='RdYlGn', ancho=600, alto=450):
    """
    Visualiza una banda de un datacube (ej. NDVI, EVI, B04) con slider temporal.
    Funciona en Colab, Jupyter local y scripts Python.

    Parámetros:
    - ruta_netcdf: str, ruta al archivo NetCDF
    - banda: str, nombre de la banda a visualizar (ej. 'B04')
    - cmap: str, colormap para la visualización
    - ancho, alto: dimensiones del gráfico
    """
    # Detectar entorno
    EN_COLAB = 'google.colab' in sys.modules
    EN_JUPYTER = 'ipykernel' in sys.modules

    if EN_COLAB:
        from IPython.display import display
        hv.notebook_extension('bokeh')
    else:
        hv.extension('bokeh')

    print("📦 Cargando NetCDF en un xarray.Dataset...")
    dataset_local = xr.open_dataset(ruta_netcdf)

    # Detectar dimensión temporal
    dim_tiempo = 't' if 't' in dataset_local.dims else 'time'

    print(f"📊 Generando mapa interactivo de la banda {banda}...")
    grafico_interactivo = dataset_local.hvplot.image(
        x='x',
        y='y',
        z=banda,
        groupby=dim_tiempo,
        cmap=cmap,
        rasterize=True,
        width=ancho,
        height=alto,
        title=f"Visualización de {banda}"
    )

    if EN_COLAB or EN_JUPYTER:
        from IPython.display import display
        display(grafico_interactivo)
    else:
        # En script puro: guardar a HTML
        hv.save(grafico_interactivo, f'{banda}_map.html', backend='bokeh')
        print(f"✅ Mapa guardado en {banda}_map.html, ábrelo en tu navegador.")

    return grafico_interactivo
