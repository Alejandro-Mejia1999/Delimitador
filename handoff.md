Resumen de arquitectura — Observatorio Maíz, Valle de Comayagua
Contexto del proyecto
Tesis de Ingeniería en Sistemas: estimación temprana de rendimiento de maíz en el Valle de Comayagua, Honduras, usando imágenes Sentinel-2 gratuitas. El sistema tiene tres etapas de pipeline (segmentación SAMGeo → clasificación Random Forest → estimación VPM) y un observatorio web Streamlit como capa de visualización.

Unidades de rendimiento en toda la UI: quintales (qq/ha y qq/parcela). Nunca toneladas métricas.

Estructura de carpetas
raíz/
├── app.py                        # Entrypoint Streamlit (st.navigation)
├── main.py                       # Script de seeding (correr con Streamlit detenido)
├── config.py                     # Todas las constantes — NO hardcodear en páginas
├── pages/
│   ├── inicio.py                 # Página de bienvenida
│   ├── 1_Parcelas.py             # Mapa interactivo
│   ├── 2_Series_Temporales.py    # Curvas EVI/LSWI/GPP
│   ├── 3_Estimacion.py           # Estimado vs referencia SAG/CAN
│   └── 4_Resumen_Valle.py        # Producción total + métricas validación
├── components/
│   ├── estilos.py                # CSS global — inyectar_estilos()
│   ├── sidebar_filtros.py        # Controles del sidebar por vista
│   ├── mapa_parcelas.py          # Render del mapa Folium
│   ├── graficas_series.py        # Plotly: EVI/LSWI/GPP
│   ├── graficas_estimacion.py    # Plotly: dispersión + barras por ventana
│   └── graficas_resumen.py       # Plotly: histograma + mapa de calor
├── utils/
│   ├── conexionDB.py             # get_connection() con caché / get_connection_raw() sin caché
│   ├── db.py                     # actualizar_gpkg() + seeding()
│   ├── queries.py                # cargar_parcelas() + cargar_municipio() con @st.cache_data
│   ├── capas_folium.py           # agregar_capa_poligonos() — función pura reutilizable
│   ├── dict_a_dataframe.py       # openeo_dict_to_dataframes()
│   ├── descargar_datacube.py     # descargar_datacube()
│   ├── aplicar_whittaker.py      # suavizador Whittaker-Eilers
│   ├── visualizar_datacube.py    # visualización de datacubes
│   ├── detectarVectores.py       # detectar_vectores()
│   └── kml_a_geojson.py          # kml_a_geojson()
├── pipeline/
│   ├── __init__.py
│   └── ingesta.py                # obtener_datacube_indices_crudo()
├── data/
│   ├── pipeline.gpkg             # Base de datos principal (SQLite/GeoPackage)
│   └── PoligonosMaizPlayitas.geojson  # GeoJSON fuente para el seeding
├── static/
│   └── ComayaguaMunicipio.geojson     # Polígono del municipio (área de estudio)
└── .streamlit/
    └── config.toml               # Tema oscuro — NO modificar sin necesidad
Base de datos (
pipeline.gpkg
)
Archivo SQLite con extensión GeoPackage. Tiene dos tipos de contenido:

Capas vectoriales (escritas con geopandas/pyogrio):

Clave en LAYERS_GPKG	Nombre real en el archivo	Estado
"parcelas"	"parcelas_vigentes"	✅ Poblada con 9 parcelas
"ciclos"	"ciclos"	⏳ Pendiente
"gpp_diario"	"gpp_diario"	⏳ Pendiente
"rendimiento"	"rendimiento"	⏳ Pendiente
"serie_evi"	"serie_evi"	⏳ Pendiente
"serie_lswi"	"serie_lswi"	⏳ Pendiente
Tablas SQLite (creadas por seeding()):

series_diarias_vpm — EVI/LSWI crudos y suavizados, temperatura, GPP diario por parcela y fecha
produccion_acumulada_ciclo — rendimiento y producción total por parcela y ciclo
Esquema de parcelas (parcelas_vigentes): id_parcela INTEGER, area_m2 REAL, area_ha REAL, geometry en EPSG:32616.

Regla crítica de Windows: geopandas/GDAL y SQLite no pueden tener el archivo abierto simultáneamente. En seeding() se escribe primero con geopandas y después se abre la conexión SQLite. Para correr main.py hay que detener Streamlit primero.

Reglas de programación (no negociables)
Sin if __name__ == "__main__" en páginas ni en app.py. Solo en utils/ para pruebas desde terminal.
Caché obligatoria: toda función que consulte la BD lleva @st.cache_data o @st.cache_resource. Están en 
queries.py
. Si el caché tiene datos viejos, usar el botón "🔄 Limpiar caché" en el sidebar de Parcelas o reiniciar Streamlit.
Conexión centralizada: la conexión SQLite vive únicamente en 
conexionDB.py
. get_connection() para Streamlit (con caché), get_connection_raw() para scripts de terminal (sin caché, con closing()).
Constantes en config.py: ningún valor hardcodeado en páginas o componentes.
Separación de responsabilidades: páginas solo ensamblan, lógica de consulta en utils/, renderizado en components/.
CRS: cálculos métricos en EPSG:32616. Reproyectar a EPSG:4326 solo al construir el mapa Folium.
Folium sobre leafmap. st_folium() con key dinámico por ciclo/ventana/modo.
Sin bfill()/ffill() fuera del período vegetativo. Los NaN por nubes se preservan para Whittaker.
Funciones puras en utils/: sin llamadas a st.* (excepto decoradores de caché).
Estado vacío siempre con st.warning() descriptivo, nunca fallo silencioso.
Código en español técnico: variables, funciones, comentarios, docstrings y UI.
Navegación Streamlit
Se usa st.navigation + st.Page (método recomendado en la documentación oficial, no el método pages/ automático). app.py es el entrypoint y actúa como marco común: aplica set_page_config e inyectar_estilos() una sola vez para todas las páginas. Las páginas individuales no llaman a set_page_config ni a inyectar_estilos().

Para levantar: .venv\Scripts\python.exe -m streamlit run app.py

Mapa interactivo (página Parcelas)
Dos capas activas:

Municipio de Comayagua — contorno azul #3498db, relleno casi transparente, tooltip desactivado (mostrar_tooltip=False) para no interferir con la navegación del mapa.
Parcelas segmentadas — color verde #2ecc71 (primera) o naranja #e67e22 (postrera), tooltip y popup activos.
Botón "🎯 Centrar en área de estudio" usa st.session_state["centrar_mapa"] para hacer fit_bounds al bounding box del municipio (MUNICIPIO_BOUNDS en config.py).

agregar_capa_poligonos() en 
capas_folium.py
 es la función reutilizable para cualquier capa de polígonos. Parámetro mostrar_tooltip: bool = True para controlar el tooltip por capa.

Pipeline de ingesta (
ingesta.py
)
Nombre de la función principal: obtener_datacube_indices_crudo — no renombrar.

Firma:

def obtener_datacube_indices_crudo(
    connection: openeo.Connection,
    geojson_openeo: dict,
    fecha_inicio: str,         # "YYYY-MM-DD"
    fecha_fin: str,            # "YYYY-MM-DD"
    config_cloud_mask: dict | None = None,
) -> dict:  # {"EVI": DataFrame, "LSWI": DataFrame}
El parámetro config_cloud_mask acepta cualquier subconjunto de estas claves (las ausentes usan el default):

Clave	Default	Descripción
kernel1_size	21	Kernel px, primera dilatación
kernel2_size	59	Kernel px, segunda dilatación
mask1_values	[2,4,5,6,7]	Clases SCL primera máscara
mask2_values	[3,8,9,10,11]	Clases SCL segunda máscara
erosion_kernel_size	3	Kernel px, erosión de bordes
Los defaults viven en _CLOUD_MASK_DEFAULTS a nivel de módulo. El merge se hace con {**_CLOUD_MASK_DEFAULTS, **(config_cloud_mask or {})}.

Retorna dict[str, pd.DataFrame] con DatetimeIndex × columnas de parcelas. Los NaN se preservan — el suavizador Whittaker los gestiona en la etapa siguiente.

Datos geoespaciales
Parcelas de estudio: 9 polígonos, Valle de Comayagua, Honduras. Bounds EPSG:4326: [-87.705, 14.409, -87.687, 14.439].
Municipio de Comayagua: 1 polígono, 
ComayaguaMunicipio.geojson
. Columnas: NOMBRE, COD_MUNI, superf_ha, Area_Km2. Bounds EPSG:4326: [-87.897, 14.357, -87.385, 14.597]. Centro: lat=14.477, lon=-87.641.
CRS nativo de ambos archivos: EPSG:32616 (UTM zona 16N).
Stack tecnológico
Categoría	Librería
UI	streamlit >= 1.45, streamlit-folium >= 0.25
Mapas	folium >= 0.19, shapely >= 2.1
Gráficas	plotly >= 6.0
Geodatos	geopandas >= 1.1, pyogrio (backend), fiona
BD	sqlite3 (stdlib), GeoPackage
Satélite	openeo (CDSE backend)
ML (pendiente)	scikit-learn >= 1.9
Suavizado	whittaker-eilers >= 0.2
Gestor de paquetes	uv (no pip directo)