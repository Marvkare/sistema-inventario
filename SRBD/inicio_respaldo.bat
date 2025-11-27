@echo off
title Sistema de Respaldo MySQL
echo Iniciando servicio de respaldo automático...
echo Este servicio se ejecutará en segundo plano y hará respaldos los domingos
echo Para detenerlo, cierra esta ventana o presiona Ctrl+C
timeout /t 3

python backup_mysql.py 2
pause