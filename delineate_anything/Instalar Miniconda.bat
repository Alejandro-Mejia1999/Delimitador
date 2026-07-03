@echo off
echo [1/2] Descargando instalador oficial de Miniconda...
if not exist miniconda_installer.exe (
    curl -sL https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o miniconda_installer.exe
)

echo [2/2] Ejecutando instalador en modo silencioso...
echo Por favor espera a que el instalador termine de forma pacifica...
start /wait "" miniconda_installer.exe /InstallationType=JustMe /RegisterPython=0 /S /D=%USERPROFILE%\miniconda3

del miniconda_installer.exe
echo Instalacion base terminada en %USERPROFILE%\miniconda3.
pause