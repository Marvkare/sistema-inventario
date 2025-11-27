import os
import schedule
import time
import subprocess
from datetime import datetime
import json
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup_log.txt'),
        logging.StreamHandler()
    ]
)

def cargar_configuracion():
    """Cargar configuración de la base de datos"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Archivo config.json no encontrado")
        return None

def crear_respaldo():
    """Crear respaldo de la base de datos"""
    config = cargar_configuracion()
    if not config:
        return False
    
    # Crear directorio de respaldos si no existe
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Nombre del archivo con fecha
    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(backup_dir, f"respaldo_{fecha}.sql")
    
    try:
        # Comando mysqldump
        cmd = [
            'mysqldump',
            f"--host={config['host']}",
            f"--user={config['user']}",
            f"--password={config['password']}",
            config['database'],
            f"--result-file={backup_file}"
        ]
        
        # Ejecutar respaldo
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"✅ Respaldo creado exitosamente: {backup_file}")
            
            # Limpiar respaldos antiguos (mantener solo últimos 4)
            limpiar_respaldos_antiguos(backup_dir)
            return True
        else:
            logging.error(f"❌ Error en respaldo: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error al crear respaldo: {str(e)}")
        return False

def limpiar_respaldos_antiguos(backup_dir, mantener=4):
    """Eliminar respaldos antiguos, mantener solo los más recientes"""
    try:
        archivos = [f for f in os.listdir(backup_dir) if f.startswith('respaldo_') and f.endswith('.sql')]
        archivos.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
        
        # Eliminar archivos antiguos
        for archivo in archivos[mantener:]:
            os.remove(os.path.join(backup_dir, archivo))
            logging.info(f"🗑️ Respaldo antiguo eliminado: {archivo}")
            
    except Exception as e:
        logging.error(f"Error limpiando respaldos antiguos: {str(e)}")

def verificar_y_respaldar():
    """Verificar si es tiempo de respaldo y ejecutarlo"""
    # Verificar si hoy es domingo (día 6 de la semana)
    if datetime.now().weekday() == 6:  # 6 = domingo
        logging.info("🏁 Es domingo - ejecutando respaldo semanal")
        crear_respaldo()
    else:
        logging.info("⏭️ No es día de respaldo (solo domingos)")

def ejecutar_una_vez_al_dia():
    """Ejecutar el respaldo una vez al día si es domingo"""
    verificar_y_respaldar()
    
    # Programar siguiente ejecución en 24 horas
    schedule.every(24).hours.do(verificar_y_respaldar)

# Versión simplificada para ejecución manual
def respaldo_manual():
    """Función para ejecutar respaldo manualmente"""
    print("Iniciando respaldo manual...")
    crear_respaldo()

if __name__ == "__main__":
    print("🔧 Script de Respaldo MySQL Semanal")
    print("1. Ejecutar respaldo manual")
    print("2. Iniciar servicio en segundo plano")
    
    opcion = input("Selecciona opción (1/2): ")
    
    if opcion == "1":
        respaldo_manual()
    else:
        print("🚀 Iniciando servicio de respaldo automático...")
        print("El sistema verificará cada 24 horas si es domingo para hacer respaldo")
        print("Presiona Ctrl+C para detener")
        
        # Ejecutar inmediatamente al iniciar
        verificar_y_respaldar()
        
        # Programar ejecución diaria
        schedule.every(24).hours.do(verificar_y_respaldar)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(3600)  # Verificar cada hora
        except KeyboardInterrupt:
            print("\n⏹️ Servicio de respaldo detenido")