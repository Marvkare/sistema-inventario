# your_flask_app/routes/etiquetas.py
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from database import get_db_connection
from decorators import permission_required
from pymysql.err import MySQLError
import pymysql

etiquetas_bp = Blueprint('etiquetas', __name__)

@etiquetas_bp.route('/imprimir_etiquetas', methods=['GET'])
@login_required
@permission_required('resguardos.ver_resguardos')
def imprimir_etiquetas():
    """Ruta para renderizar la página de impresión de etiquetas."""
    return render_template('imprimir_etiquetas.html')

@etiquetas_bp.route('/buscar_bienes', methods=['POST'])
@login_required
@permission_required('resguardos.ver_resguardos')
def buscar_bienes():
    """
    Ruta para buscar bienes y resguardos en la base de datos
    y devolver los resultados en formato JSON.
    Solo muestra resultados de resguardos ACTIVOS.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
        query_text = request.json.get('query', '')
        
        if not query_text:
            return jsonify([])

        search_pattern = f"%{query_text}%"
        
        # Se añade r.Activo = 1 en el WHERE y se agrupan las condiciones del LIKE con paréntesis
        sql_query = """
            SELECT
                b.id AS id_bien,
                r.id AS id_resguardo,
                b.No_Inventario,
                b.Descripcion_Corta_Del_Bien,
                b.Descripcion_Del_Bien,
                r.No_Resguardo,
                r.Nombre_Del_Resguardante,
                a.nombre AS Area_Nombre
            FROM
                bienes b
            JOIN
                resguardos r ON b.id = r.id_bien
            JOIN
                areas a ON r.id_area = a.id
            WHERE
                r.Activo = 1 
                AND (
                    b.No_Inventario LIKE %s OR
                    b.Descripcion_Corta_Del_Bien LIKE %s OR
                    r.No_Resguardo LIKE %s OR
                    r.Nombre_Del_Resguardante LIKE %s
                )
            LIMIT 10
        """
        
        cursor.execute(sql_query, (search_pattern, search_pattern, search_pattern, search_pattern))
        results = cursor.fetchall()
        
        return jsonify(results)

    except pymysql.MySQLError as err: # Corregido a pymysql.MySQLError por si acaso
        print(f"Error de base de datos: {err}")
        return jsonify({"error": "Error de base de datos"}), 500
    finally:
        if cursor: cursor.close() # Es más seguro comprobar si el cursor existe antes de cerrarlo
        if conn: conn.close()