@echo off
SETLOCAL EnableExtensions EnableDelayedExpansion
title Instalador Delineate-Anything - Tesis Maiz

echo =====================================================================
echo [1/4] Limpiando configuracion de Conda y bloqueando canales comerciales
echo =====================================================================

:: Detectar ruta de Miniconda del usuario
set "CONDA_DIR=%USERPROFILE%\miniconda3"
if not exist "%CONDA_DIR%\Scripts\conda.exe" (
    echo [ERROR] No se encontro Miniconda en %CONDA_DIR%.
    echo Por favor, edita este script con la ruta correcta.
    pause
    exit /b 1
)

:: Inicializar el entorno de Conda para este script de procesamiento batch
call "%CONDA_DIR%\Scripts\activate.bat"

:: Forzar la reescritura limpia del archivo de configuracion (.condarc)
:: Esto destruye cualquier rastro de los canales comerciales que causan el error de ToS
echo channels:> "%USERPROFILE%\.condarc"
echo   - conda-forge>> "%USERPROFILE%\.condarc"
echo channel_priority: strict>> "%USERPROFILE%\.condarc"
echo override_channels: true>> "%USERPROFILE%\.condarc"

echo Configuacion de canales limpia instalada con exito (Conda-Forge unicamente).

echo.
echo =====================================================================
echo [2/4] Creando entorno aislado "tesis_maiz" con Python 3.10
echo =====================================================================
:: Eliminamos el entorno si existia a medias para evitar conflictos
call conda env remove -n tesis_maiz -y >nul 2>&1
call conda create -n tesis_maiz python=3.10 pip -y --override-channels -c conda-forge
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo la creacion del entorno Conda.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [3/4] Activando entorno de forma segura
echo =====================================================================
call conda activate tesis_maiz
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se pudo activar el entorno 'tesis_maiz'.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [4/4] Instalando dependencias geoespaciales (Conda) y ligeras (Pip)
echo =====================================================================
:: 1. Primero instalamos lo pesado y critico por Conda-Forge
call conda install -y --override-channels -c conda-forge gdal geopandas rasterio

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Hubo un problema al instalar las librerias geoespaciales de Conda.
    pause
    exit /b 1
)

:: 2. Luego instalamos de golpe TODO el resto usando el archivo de requerimientos del repositorio.
:: Conda respetara lo que ya instalo arriba y completara lo que falta (huggingface_hub, ultralytics, etc.)
if exist "requirements.txt" (
    echo Instalando el resto de dependencias desde requirements.txt...
    call pip install -r requirements.txt
) else (
    echo [ADVERTENCIA] No se encontro requirements.txt en esta carpeta.
    echo Instalando dependencias esenciales manualmente...
    call pip install huggingface_hub pyyaml ultralytics onnxruntime
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =====================================================================
    echo ¡INSTALACION COMPLETADA CON EXITO!
    echo El entorno "tesis_maiz" esta listo con todas las dependencias instaladas.
    echo =====================================================================
) else (
    echo [ERROR] Hubo un problema al completar la instalacion con Pip.
)