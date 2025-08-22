# your_flask_app/routes/resguardos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
import mysql.connector
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename
from datetime import date,datetime

from database import get_db, get_db_connection, get_table_columns, AVAILABLE_COLUMNS

resguardos_bp = Blueprint('resguardos', __name__)

@resguardos_bp.route('/crear_resguardo', methods=['GET', 'POST'])
def crear_resguardo():
    conn = None # Initialize connection to None
    try:
        if request.method == 'POST':
            # Extract all form data
            no_inventario = request.form.get('No_Inventario')
            no_factura = request.form.get('No_Factura')
            no_cuenta = request.form.get('No_Cuenta')
            no_resguardo = request.form.get('No_Resguardo')
            no_trabajador = request.form.get('No_Trabajador')
            proveedor = request.form.get('Proveedor')
            fecha_resguardo = request.form.get('Fecha_Resguardo') # Date string
            descripcion_del_bien = request.form.get('Descripcion_Del_Bien')
            descripcion_fisica = request.form.get('Descripcion_Fisica')
            area = request.form.get('Area')
            rubro = request.form.get('Rubro')
            poliza = request.form.get('Poliza')
            fecha_poliza = request.form.get('Fecha_Poliza') # Date string
            sub_cuenta_armonizadora = request.form.get('Sub_Cuenta_Armonizadora')
            fecha_factura = request.form.get('Fecha_Factura') # Date string
            costo_inicial = request.form.get('Costo_Inicial')
            depreciacion_acumulada = request.form.get('Depreciacion_Acumulada')
            costo_final_cantidad = request.form.get('Costo_Final_Cantidad')
            cantidad = request.form.get('Cantidad')
            puesto = request.form.get('Puesto')
            nombre_director_jefe_de_area = request.form.get('Nombre_Director_Jefe_De_Area')
            tipo_de_resguardo = request.form.get('Tipo_De_Resguardo')
            adscripcion_direccion_area = request.form.get('Adscripcion_Direccion_Area')
            nombre_del_resguardante = request.form.get('Nombre_Del_Resguardante')
            estado_del_bien = request.form.get('Estado_Del_Bien')
            marca = request.form.get('Marca')
            modelo = request.form.get('Modelo')
            numero_de_serie = request.form.get('Numero_De_Serie')

            # --- Image Upload Handling ---
            image_path = None
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file.filename != '' and current_app.allowed_file(file.filename): # Use the global helper
                    filename = secure_filename(file.filename)
                    # Use the configured UPLOAD_FOLDER
                    file_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(file_save_path)
                    image_path = os.path.join('uploads', filename).replace('\\', '/')

            conn = get_db_connection()
            if conn is None:
                flash("Error de conexión a la base de datos.", 'danger')
                return redirect(url_for('main.resguardos_list')) # Use blueprint prefix
            cursor = conn.cursor()

            sql = """
                INSERT INTO resguardo (
                    No_Inventario, No_Factura, No_Cuenta, No_Resguardo, No_Trabajador,
                    Proveedor, Fecha_Resguardo, Descripcion_Del_Bien, Descripcion_Fisica,
                    Area, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora,
                    Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final_Cantidad,
                    Cantidad, Puesto, Nombre_Director_Jefe_De_Area,
                    Tipo_De_Resguardo, Adscripcion_Direccion_Area, Nombre_Del_Resguardante,
                    Estado_Del_Bien, Marca, Modelo, Numero_De_Serie, Imagen_Path
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """

            values = (
                no_inventario, no_factura, no_cuenta, no_resguardo, no_trabajador,
                proveedor, fecha_resguardo, descripcion_del_bien, descripcion_fisica,
                area, rubro, poliza, fecha_poliza, sub_cuenta_armonizadora,
                fecha_factura, costo_inicial, depreciacion_acumulada, costo_final_cantidad,
                cantidad,  puesto, nombre_director_jefe_de_area,
                tipo_de_resguardo, adscripcion_direccion_area, nombre_del_resguardante,
                estado_del_bien, marca, modelo, numero_de_serie, image_path
            )

            cursor.execute(sql, values)
            conn.commit()
            flash('Resguardo creado exitosamente.', 'success')
            return redirect(url_for('main.resguardos_list')) # Use blueprint prefix

        # If it's a GET request
        return render_template('crear_resguardo.html', available_columns=get_table_columns())

    except mysql.connector.Error as err:
        flash(f"Error de base de datos al crear resguardo: {err}", 'danger')
        traceback.print_exc()
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", 'danger')
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            
    return redirect(url_for('main.resguardos_list')) # Use blueprint prefix

@resguardos_bp.route('/generate_resguardo_pdf/<int:id_resguardo>')
def generate_resguardo_pdf(id_resguardo):
    conn, cursor = get_db() # Using get_db for dictionary cursor
    if not conn:
        flash("No se pudo conectar a la base de datos.", 'error')
        return redirect(url_for('main.resguardos_list'))

    try:
        cursor.execute("SELECT * FROM resguardo WHERE id = %s", (id_resguardo,))
        resguardo_data = cursor.fetchone()
        if not resguardo_data:
            flash("Resguardo no encontrado.", 'error')
            return redirect(url_for('main.resguardos_list'))
    except mysql.connector.Error as err:
        flash(f"Error al obtener datos: {err}", 'error')
        return redirect(url_for('main.resguardos_list'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    try:
        reader = PdfReader(current_app.config['PDF_TEMPLATE_PATH'])
        
        if not reader.get_form_text_fields():
            flash("La plantilla PDF no contiene campos de formulario.", 'error')
            return redirect(url_for('main.resguardos_list'))

        # Map your DB data to PDF fields
        # This is a critical part, ensure field names in PDF match these keys
        field_data = {
            "No_Inventario_Field": resguardo_data.get('No_Inventario', ''),
            "No_Factura_Field": resguardo_data.get('No_Factura', ''),
            "No_Cuenta_Field": resguardo_data.get('No_Cuenta', ''),
            # Add all other fields you want to populate
            "No_Resguardo_Field": resguardo_data.get('No_Resguardo', ''),
            "Proveedor_Field": resguardo_data.get('Proveedor', ''),
            "Fecha_Resguardo_Field": str(resguardo_data.get('Fecha_Resguardo', '')) if resguardo_data.get('Fecha_Resguardo') else '',
            "Descripcion_Del_Bien_Field": resguardo_data.get('Descripcion_Del_Bien', ''),
            "Descripcion_Fisica_Field": resguardo_data.get('Descripcion_Fisica', ''),
            "Area_Field": resguardo_data.get('Area', ''),
            "Rubro_Field": resguardo_data.get('Rubro', ''),
            "Poliza_Field": resguardo_data.get('Poliza', ''),
            "Fecha_Poliza_Field": str(resguardo_data.get('Fecha_Poliza', '')) if resguardo_data.get('Fecha_Poliza') else '',
            "Sub_Cuenta_Armonizadora_Field": resguardo_data.get('Sub_Cuenta_Armonizadora', ''),
            "Fecha_Factura_Field": str(resguardo_data.get('Fecha_Factura', '')) if resguardo_data.get('Fecha_Factura') else '',
            "Costo_Inicial_Field": str(resguardo_data.get('Costo_Inicial', '')),
            "Depreciacion_Acumulada_Field": str(resguardo_data.get('Depreciacion_Acumulada', '')),
            "Costo_Final_Cantidad_Field": str(resguardo_data.get('Costo_Final_Cantidad', '')),
            "Cantidad_Field": str(resguardo_data.get('Cantidad', '')),
            
            "Puesto_Field": resguardo_data.get('Puesto', ''),
            "Nombre_Director_Jefe_De_Area_Field": resguardo_data.get('Nombre_Director_Jefe_De_Area', ''),
            "Numero_De_Serie_Field": resguardo_data.get('Numero_De_Serie', '')
        }

        writer = PdfWriter()
        writer.clone_reader_document_root(reader)
        
        # Fill the form fields
        writer.update_page_form_field_values(writer.pages[0], field_data) # Assuming fields are on the first page

        # Flatten the form fields so they are not editable in the final PDF
        writer.flatten_form()

        # Save to BytesIO to send as file
        output_pdf_buffer = BytesIO()
        writer.write(output_pdf_buffer)
        output_pdf_buffer.seek(0)

        return send_file(
            output_pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'resguardo_{id_resguardo}.pdf'
        )

    except FileNotFoundError:
        flash("Plantilla PDF no encontrada en " + current_app.config['PDF_TEMPLATE_PATH'], 'error')
    except Exception as e:
        flash(f"Error al generar PDF: {str(e)}", 'error')
        print(f"Error detallado:\n{traceback.format_exc()}")
        
    return redirect(url_for('main.resguardos_list'))


@resguardos_bp.route('/ver_resguardos')
def ver_resguardos():
    conn = None
    resguardos_data = []
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)
    offset = (page - 1) * limit

    # Search parameters
    search_column = request.args.get('search_column', 'all')
    search_query = request.args.get('search_query', '').strip()
    
    # Check if this is an AJAX request for infinite scroll
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_select_columns = """
            r.id,
            b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Descripcion_Del_Bien,
            b.Descripcion_Corta_Del_Bien, a.nombre AS Area_Nombre,
            b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
            b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada,
            b.Costo_Final_Cantidad, b.Cantidad, b.Estado_Del_Bien, b.Marca,
            b.Modelo, b.Numero_De_Serie,
            r.No_Resguardo, r.Tipo_De_Resguardo, r.Fecha_Resguardo, r.No_Trabajador,
            r.Puesto, r.Nombre_Director_Jefe_De_Area,
            r.Nombre_Del_Resguardante,
            b.Proveedor
        """
        
        sql_query = f"""
            SELECT {sql_select_columns}
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
        """
        
        where_clauses = []
        sql_params = []

        if search_query:
            if search_column == 'all':
                all_columns_search_clauses = []
                # Use a specific list of columns for "all" search for better performance
                searchable_cols = [
                    'b.No_Inventario', 'b.No_Factura', 'b.No_Cuenta', 'b.Descripcion_Del_Bien',
                    'a.nombre', 'b.Proveedor', 'b.Rubro', 'r.No_Resguardo',
                    'r.Nombre_Del_Resguardante'
                ]
                for col in searchable_cols:
                    all_columns_search_clauses.append(f"{col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                where_clauses.append("(" + " OR ".join(all_columns_search_clauses) + ")")
            else:
                # Find the correct table prefix for the search column
                col_mapping = {
                    'Area_Nombre': 'a.nombre',
                    'No_Inventario': 'b.No_Inventario',
                    'No_Factura': 'b.No_Factura',
                    'No_Cuenta': 'b.No_Cuenta',
                    'Descripcion_Del_Bien': 'b.Descripcion_Del_Bien',
                    'Descripcion_Corta_Del_Bien': 'b.Descripcion_Corta_Del_Bien',
                    'Rubro': 'b.Rubro',
                    'Poliza': 'b.Poliza',
                    'Fecha_Poliza': 'b.Fecha_Poliza',
                    'Sub_Cuenta_Armonizadora': 'b.Sub_Cuenta_Armonizadora',
                    'Fecha_Factura': 'b.Fecha_Factura',
                    'Costo_Inicial': 'b.Costo_Inicial',
                    'Depreciacion_Acumulada': 'b.Depreciacion_Acumulada',
                    'Costo_Final_Cantidad': 'b.Costo_Final_Cantidad',
                    'Cantidad': 'b.Cantidad',
                    'Estado_Del_Bien': 'b.Estado_Del_Bien',
                    'Marca': 'b.Marca',
                    'Modelo': 'b.Modelo',
                    'Numero_De_Serie': 'b.Numero_De_Serie',
                    'No_Resguardo': 'r.No_Resguardo',
                    'No_Trabajador': 'r.No_Trabajador',
                    'Fecha_Resguardo': 'r.Fecha_Resguardo',
                    'Puesto': 'r.Puesto',
                    'Nombre_Director_Jefe_De_Area': 'r.Nombre_Director_Jefe_De_Area',
                    'Tipo_De_Resguardo': 'r.Tipo_De_Resguardo',
                    'Nombre_Del_Resguardante': 'r.Nombre_Del_Resguardante',
                    'Proveedor': 'b.Proveedor'
                }

                db_col = col_mapping.get(search_column)
                if db_col:
                    where_clauses.append(f"{db_col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                else:
                    flash("Columna de búsqueda inválida.", 'error')
                    search_column = 'all'

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        sql_query += f" ORDER BY r.id DESC LIMIT %s OFFSET %s"
        sql_params.extend([limit, offset])

        cursor.execute(sql_query, sql_params)
        resguardos_data = cursor.fetchall()
        
        # Prepare a list of user-friendly column names for the search dropdown
        available_columns_for_search = [col for col in AVAILABLE_COLUMNS if col not in [
            'Descripcion_Del_Bien', 'Descripcion_Corta_Del_Bien', 'Puesto', 'Tipo_De_Resguardo', 'Estado_Del_Bien'
        ]]

        if is_ajax:
            # Format dates to string for JSON serialization
           
            for row in resguardos_data:
                for key, value in row.items():
                    if isinstance(value, (date, datetime)):
                        row[key] = value.isoformat()
            
            # Use 'Area_Nombre' key instead of 'Area' as defined in the query
            
            return jsonify(resguardos_data)
        else:
            return render_template(
                'resguardos_list.html',
                resguardos=resguardos_data,
                search_column=search_column,
                search_query=search_query,
                available_columns_for_search=available_columns_for_search,
                current_page=page,
                limit=limit
            )

    except mysql.connector.Error as err:
        flash(f"Error al obtener resguardos: {err}", 'error')
        print(f"Error: {err}")
        return render_template('resguardos_list.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", 'error')
        print(f"Unexpected error: {e}")
        return render_template('resguardos_list.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/resguardos_clasificados')
def resguardos_clasificados():
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos", 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
     SELECT r.*,
                   CASE
                       WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 'Sujeto de Control'
                       ELSE 'Resguardo Normal'
                   END AS Tipo_De_Resguardo
            FROM resguardo r
            ORDER BY
                CASE
                    WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 0
                    ELSE 1
                END,
                r.id
""")
        resguardos = cursor.fetchall()
        
        column_names = [desc[0] for desc in cursor.description]
        
        return render_template('resguardos_clasificados.html', 
                            resguardos=resguardos,
                            column_names=column_names)
    except Exception as e:
        flash(f"Error al obtener resguardos: {str(e)}", 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

        
@resguardos_bp.route('/exportar_resguardos_excel', methods=['POST'])
def exportar_resguardos_excel():
    try:
        selected_columns = request.form.getlist('columns')
        
        if not selected_columns:
            return jsonify({'error': 'No se seleccionaron columnas'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
            
        try:
            cursor = conn.cursor(dictionary=True)
            columns_str = ', '.join(selected_columns)
            cursor.execute(f"""
                SELECT {columns_str}, 
                       CASE 
                           WHEN Tipo_De_Resguardo  = 1 THEN 'Sujeto de Control'
                           ELSE 'Resguardo Normal'
                       END AS Tipo_de_resguardo
                FROM resguardo
                ORDER BY Tipo_De_Resguardo  DESC, id
            """)
            data = cursor.fetchall()
            
            df = pd.DataFrame(data)
            
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, sheet_name='Resguardos', index=False)
            writer.close()
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='resguardos_clasificados.xlsx'
            )
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# It's good practice to have a helper function to get areas
def get_areas_list_from_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT nombre FROM areas ORDER BY nombre")
        areas = [row['nombre'] for row in cursor.fetchall()]
        return areas
    except Exception as e:
        print(f"Error fetching areas from DB: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/edit_resguardo/<int:id>', methods=['GET', 'POST'])
def edit_resguardo(id):
    conn = None
    form_data = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch the specific resguardo data for editing using a JOIN
        query = """
            SELECT
                r.id, r.id_bien, r.id_area, r.No_Resguardo, r.Tipo_De_Resguardo, r.Fecha_Resguardo,
                r.No_Trabajador, r.Puesto, r.Nombre_Director_Jefe_De_Area,
                r.Nombre_Del_Resguardante, r.Fecha_Registro, r.Fecha_Ultima_Modificacion,
                b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Proveedor, b.Descripcion_Del_Bien,
                b.Descripcion_Corta_Del_Bien, b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
                b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada, b.Costo_Final_Cantidad,
                b.Cantidad, b.Estado_Del_Bien, b.Marca, b.Modelo, b.Numero_De_Serie, b.Imagen_Path,
                a.nombre AS area_nombre
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
            WHERE r.id = %s
        """
        cursor.execute(query, (id,))
        form_data = cursor.fetchone()

        if not form_data:
            flash("Resguardo no encontrado.", 'error')
            return redirect(url_for('resguardos.ver_resguardos'))

        # Handle POST request for updating the resguardo
        if request.method == 'POST':
            # Extract form data
            # Use .get() with a default value to avoid errors if a field is missing
            no_inventario = request.form.get('No_Inventario')
            no_factura = request.form.get('No_Factura')
            no_cuenta = request.form.get('No_Cuenta')
            no_resguardo = request.form.get('No_Resguardo')
            no_trabajador = request.form.get('No_Trabajador')
            proveedor = request.form.get('Proveedor')
            fecha_resguardo = request.form.get('Fecha_Resguardo')
            descripcion_del_bien = request.form.get('Descripcion_Del_Bien')
            descripcion_corta_del_bien = request.form.get('Descripcion_Corta_Del_Bien')
            area_nombre = request.form.get('Area')
            rubro = request.form.get('Rubro')
            poliza = request.form.get('Poliza')
            fecha_poliza = request.form.get('Fecha_Poliza')
            sub_cuenta_armonizadora = request.form.get('Sub_Cuenta_Armonizadora')
            fecha_factura = request.form.get('Fecha_Factura')
            costo_inicial = request.form.get('Costo_Inicial')
            depreciacion_acumulada = request.form.get('Depreciacion_Acumulada')
            costo_final_cantidad = request.form.get('Costo_Final_Cantidad')
            cantidad = request.form.get('Cantidad')
            puesto = request.form.get('Puesto')
            nombre_director_jefe_de_area = request.form.get('Nombre_Director_Jefe_De_Area')
            tipo_de_resguardo = request.form.get('Tipo_De_Resguardo')
            nombre_del_resguardante = request.form.get('Nombre_Del_Resguardante')
            estado_del_bien = request.form.get('Estado_Del_Bien')
            marca = request.form.get('Marca')
            modelo = request.form.get('Modelo')
            numero_de_serie = request.form.get('Numero_De_Serie')

            # Handle file upload for image
            image_path = form_data.get('Imagen_Path')
            if 'imagen' in request.files and request.files['imagen'].filename != '':
                file = request.files['imagen']
                if current_app.allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(file_save_path)
                    image_path = os.path.join('uploads', filename).replace('\\', '/')

            # Start transaction
            conn.start_transaction()

            # Step 1: Update the 'areas' table
            # Find the ID of the selected area
            cursor.execute("SELECT id FROM areas WHERE nombre = %s", (area_nombre,))
            area_record = cursor.fetchone()
            if not area_record:
                flash("El área seleccionada no existe. Por favor, elija una de la lista.", 'danger')
                return redirect(url_for('resguardos.edit_resguardo', id=id))
            id_area = area_record['id']

            # Step 2: Update the 'bienes' table
            sql_bienes = """
                UPDATE bienes SET
                    `No_Inventario`=%s, `No_Factura`=%s, `No_Cuenta`=%s, `Proveedor`=%s,
                    `Descripcion_Del_Bien`=%s, `Descripcion_Corta_Del_Bien`=%s, `Rubro`=%s,
                    `Poliza`=%s, `Fecha_Poliza`=%s, `Sub_Cuenta_Armonizadora`=%s,
                    `Fecha_Factura`=%s, `Costo_Inicial`=%s, `Depreciacion_Acumulada`=%s,
                    `Costo_Final_Cantidad`=%s, `Cantidad`=%s, `Estado_Del_Bien`=%s,
                    `Marca`=%s, `Modelo`=%s, `Numero_De_Serie`=%s, `Imagen_Path`=%s
                WHERE id=%s
            """
            values_bienes = (
                no_inventario, no_factura, no_cuenta, proveedor,
                descripcion_del_bien, descripcion_corta_del_bien, rubro,
                poliza, fecha_poliza, sub_cuenta_armonizadora,
                fecha_factura, costo_inicial, depreciacion_acumulada,
                costo_final_cantidad, cantidad, estado_del_bien,
                marca, modelo, numero_de_serie, image_path,
                form_data['id_bien']
            )
            cursor.execute(sql_bienes, values_bienes)

            # Step 3: Update the 'resguardos' table
            sql_resguardos = """
                UPDATE resguardos SET
                    `id_area`=%s, `No_Resguardo`=%s, `Tipo_De_Resguardo`=%s, `Fecha_Resguardo`=%s,
                    `No_Trabajador`=%s,  `Puesto`=%s, `Nombre_Director_Jefe_De_Area`=%s,
                    `Nombre_Del_Resguardante`=%s
                WHERE id=%s
            """
            values_resguardos = (
                id_area, no_resguardo, tipo_de_resguardo, fecha_resguardo,
                no_trabajador, puesto, nombre_director_jefe_de_area,
                nombre_del_resguardante, id
            )
            cursor.execute(sql_resguardos, values_resguardos)

            conn.commit()
            flash("Resguardo actualizado exitosamente.", 'success')
            return redirect(url_for('resguardos.ver_resguardos'))

        # For GET request, render the form
        all_areas = get_areas_list_from_db()

        # The HTML template will now receive form_data with combined fields
        return render_template('edit_resguardo.html',
                               form_data=form_data,
                               areas=all_areas,
                               is_editing=True)

    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        flash(f"Error de base de datos al actualizar resguardo: {err}", 'danger')
        traceback.print_exc()
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
        flash(f"Ocurrió un error inesperado: {e}", 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    return redirect(url_for('resguardos.ver_resguardos'))


@resguardos_bp.route('/delete/<int:id>', methods=['POST'])
def delete_resguardo(id):
    """Elimina un registro de la base de datos."""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        query = "DELETE FROM resguardo WHERE No_Folio = %s"
        cursor.execute(query, (id,))
        conn.commit()
        flash("Resguardo eliminado correctamente.", 'success')
    except mysql.connector.Error as err:
        flash(f"Error al eliminar resguardo: {err}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index'))

@resguardos_bp.route('/ver_resguardo/<int:id>')
def ver_resguardo(id):
    conn = None
    resguardo_data = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Realiza un JOIN para obtener los datos de las tres tablas
        query = """
            SELECT
                r.id, r.No_Resguardo, r.Tipo_De_Resguardo, r.Fecha_Resguardo,
                r.No_Trabajador, r.Puesto, r.Nombre_Director_Jefe_De_Area,
                r.Nombre_Del_Resguardante, r.Fecha_Registro,
                b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Proveedor, b.Descripcion_Del_Bien,
                b.Descripcion_Corta_Del_Bien, b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
                b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada, b.Costo_Final_Cantidad,
                b.Cantidad, b.Estado_Del_Bien, b.Marca, b.Modelo, b.Numero_De_Serie, b.Imagen_Path,
                a.nombre AS area_nombre
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
            WHERE r.id = %s
        """
        cursor.execute(query, (id,))
        resguardo_data = cursor.fetchone()

        if not resguardo_data:
            flash("Resguardo no encontrado.", 'danger')
            return redirect(url_for('resguardos.ver_resguardos')) # Redirige a la lista de resguardos

        return render_template('ver_resguardo.html', resguardo=resguardo_data)

    except mysql.connector.Error as err:
        flash(f"Error de base de datos: {err}", 'danger')
        traceback.print_exc()
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    
    return redirect(url_for('resguardos.ver_resguardos'))