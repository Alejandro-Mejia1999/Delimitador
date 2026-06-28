# ==========================================
# CELDA: UTILIDAD — openeo_dict_to_dataframes
# (Ejecutar una vez, reutilizar en todo el notebook)
# ==========================================
import pandas as pd
import numpy as np

def openeo_dict_to_dataframes(
    diccionario: dict,
    nombres_bandas: list,
    nombres_columnas: list = None,
    transformaciones: dict = None
) -> dict:
    """
    Convierte el dict retornado por openEO aggregate_spatial().execute()
    en un dict de DataFrames pandas, uno por banda.

    Parameters
    ----------
    diccionario : dict
        Salida directa de cube.execute(). Claves = fechas ISO, valores = lista
        de geometrías x bandas: [[b0_g0, b1_g0], [b0_g1, b1_g1], ...].
    nombres_bandas : list[str]
        Nombres de las bandas en el orden posicional que retorna openEO.
        Ejemplo: ["EVI", "LSWI"] o ["temperature-mean", "solar-radiation-flux"].
    nombres_columnas : list[str], opcional
        Etiquetas para las columnas (geometrías). Si None, genera "Parcela_1", ...
    transformaciones : dict, opcional
        {nombre_banda: callable} para transformar valores crudos antes de
        almacenarlos. Útil para conversiones de escala.
        Ejemplo: {"temperature-mean": lambda x: x / 100.0 - 273.15}

    Returns
    -------
    dict[str, pd.DataFrame]
        Clave = nombre de banda. Valor = DataFrame con DatetimeIndex
        normalizado (sin zona horaria, truncado a medianoche).
        Todos los valores son float64; None → np.nan.

    Raises
    ------
    ValueError
        Si el número de bandas detectado no coincide con nombres_bandas.
    """
    if transformaciones is None:
        transformaciones = {}

    fechas_str = sorted(diccionario.keys())
    fechas_idx = pd.to_datetime(fechas_str).tz_localize(None).normalize()

    # 1. Detectar estructura y número de geometrías de forma segura
    muestra_valida = None
    for f in fechas_str:
        if diccionario[f] is not None and len(diccionario[f]) > 0:
            muestra_valida = diccionario[f]
            break
            
    if muestra_valida is None:
        raise ValueError("El diccionario de clima no contiene datos válidos.")

    # openEO devuelve una lista simple [b0, b1] si es una sola geometría,
    # o una lista de listas [[b0, b1], [b0, b1]] si son varias geometrías.
    es_lista_de_listas = isinstance(muestra_valida[0], (list, tuple))
    num_geom = len(muestra_valida) if es_lista_de_listas else 1

    if nombres_columnas is None:
        nombres_columnas = [f"Parcela_{i+1}" for i in range(num_geom)]

    acumuladores = {banda: [] for banda in nombres_bandas}

    for f in fechas_str:
        valores_fecha = diccionario[f]

        # Manejo de fechas vacías
        if valores_fecha is None or len(valores_fecha) == 0:
            for nombre_banda in nombres_bandas:
                acumuladores[nombre_banda].append([np.nan] * num_geom)
            continue

        for idx_banda, nombre_banda in enumerate(nombres_bandas):
            transform = transformaciones.get(nombre_banda, None)
            fila = []

            if es_lista_de_listas:
                # Caso multigeometría (Tus parcelas de satélite)
                for geom in valores_fecha:
                    if geom is None:
                        fila.append(np.nan)
                    else:
                        val_raw = geom[idx_banda]
                        if val_raw is None or (isinstance(val_raw, float) and np.isnan(val_raw)):
                            fila.append(np.nan)
                        else:
                            fila.append(float(transform(val_raw)) if transform else float(val_raw))
            else:
                # Caso monogeometría (Tu polígono de clima AGERA5)
                val_raw = valores_fecha[idx_banda]
                if val_raw is None or (isinstance(val_raw, float) and np.isnan(val_raw)):
                    fila.append(np.nan)
                else:
                    fila.append(float(transform(val_raw)) if transform else float(val_raw))

            acumuladores[nombre_banda].append(fila)

    # Construir DataFrames
    resultado = {}
    for nombre_banda in nombres_bandas:
        resultado[nombre_banda] = pd.DataFrame(
            acumuladores[nombre_banda],
            index=fechas_idx,
            columns=nombres_columnas,
            dtype=float
        )

    return resultado