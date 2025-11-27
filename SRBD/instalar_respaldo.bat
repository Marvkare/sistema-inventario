@echo off
echo Instalando servicio de respaldo automático...
echo.

:: Crear acceso directo en el inicio de Windows
echo Creando acceso directo en carpeta de inicio...
copy "inicio_respaldo.bat" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\"

echo.
echo ✅ Instalación completada!
echo El sistema de respaldo se ejecutará automáticamente al iniciar Windows
echo Los respaldos se guardarán en la carpeta 'backups'
echo.
pause