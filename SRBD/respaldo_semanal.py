import os
import subprocess
from datetime import datetime
import json

def crear_respaldo_semanal():
    """Script optimizado para tareas programadas de Windows"""
    
    # Cargar configuración
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        print("Error: No se pudo cargar config.json")
        return
    
    # Solo ejecutar los domingos
    if datetime.now().weekday() != 6:
        return
    
    # Crear directorio de respaldos
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Nombre del archivo
    fecha = datetime.now().strftime("%Y-%m-%d")
    backup_file = os.path.join(backup_dir, f"respaldo_semanal_{fecha}.sql")
    
    # Comando mysqldump
    cmd = f"mysqldump -h {config['host']} -u {config['user']} -p{config['password']} {config['database']} > \"{backup_file}\""
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"Respaldo semanal creado: {backup_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error creando respaldo: {e}")

if __name__ == "__main__":
    crear_respaldo_semanal()