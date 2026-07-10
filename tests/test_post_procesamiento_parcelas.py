import geopandas as gpd
from shapely.geometry import Polygon

from utils.post_procesamiento_parcelas import filtrar_parcelas_por_compacidad


def test_filtrar_parcelas_por_compacidad_elimina_geometrias_irregulares():
    gdf = gpd.GeoDataFrame(
        {
            "id": [1, 2],
            "nombre": ["compacta", "irregular"],
        },
        geometry=[
            Polygon([(0, 0), (20, 0), (20, 20), (0, 20)]),
            Polygon([(0, 0), (25, 0), (30, 5), (25, 20), (5, 20)]),
        ],
        crs="EPSG:32616",
    )

    resultado = filtrar_parcelas_por_compacidad(gdf, umbral_compacidad=0.6)

    assert len(resultado) == 1
    assert resultado.iloc[0]["id"] == 1
