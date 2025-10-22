# Sistema de Inventario y Resguardo Patrimonial (Atitalaquia)

Sistema de software para el control, inventario y resguardo de bienes patrimoniales, diseñado para cumplir con el marco jurídico aplicable al municipio de Atitalaquia, Hidalgo, y alineado con la Ley General de Contabilidad Gubernamental (LGCG).

## 🏛️ Contexto y Propósito

La gestión del patrimonio público en México exige un control riguroso y auditable. Los procesos manuales o basados en hojas de cálculo son propensos a errores, dificultan la rendición de cuentas y representan un alto riesgo ante las auditorías de la **Auditoría Superior del Estado de Hidalgo (ASEH)**.

Este sistema nace como una solución tecnológica para automatizar y asegurar el cumplimiento del ciclo de vida de los bienes patrimoniales, desde su adquisición hasta su disposición final. Su arquitectura y lógica de negocio están fundamentadas en:

1.  **Ley General de Contabilidad Gubernamental (LGCG)**: Asegurando la obligatoria conciliación contable entre el inventario físico y los registros financieros.
2.  **Ley de Bienes para el Estado de Hidalgo**: Respetando la clasificación de bienes (Dominio Público y Privado) y los procedimientos que esto conlleva.
3.  **Reglamento de los Bienes Patrimoniales Municipales de Atitalaquia**: Modelando los roles, responsabilidades y procedimientos específicos del municipio.

El objetivo es transformar el inventario de una tarea administrativa a una **plataforma estratégica de cumplimiento, transparencia y defensa ante auditorías**.

-----

## ✨ Funcionalidades Implementadas

Actualmente, el sistema cuenta con los siguientes módulos clave que cubren las etapas iniciales y de control del ciclo de vida del bien:

### 📋 Módulo de Alta de Bienes

Permite el registro de nuevos activos capturando toda la información obligatoria según el **Artículo 33 del Reglamento**, incluyendo:

  - Descripción detallada (marca, modelo, serie).
  - Valor y fecha de adquisición.
  - Capacidad para **adjuntar la factura digitalizada**, creando un expediente digital desde el origen.

### 👤 Módulo de Resguardos y Traspasos

Formaliza la custodia y responsabilidad sobre los bienes:

  - **Asignación de Resguardos**: Vincula un bien a un empleado (responsable directo) y a su jefe (responsable solidario).
  - **Generación de Resguardos en PDF**: Crea el documento oficial listo para ser firmado y archivado.
  - **Traspaso de Responsabilidad**: Facilita el cambio de resguardante de manera ágil y documentada, generando el acta de entrega-recepción correspondiente.

### 🏢 Módulo de Administración de Áreas

Replica la estructura organizacional del municipio, permitiendo a los **Titulares de Unidad Administrativa** (Jefes de Área) visualizar y gestionar el inventario completo de sus dependencias, cumpliendo con su rol de "resguardante solidario" (Artículo 30).

### 🖨️ Generador de Etiquetas con Códigos QR

Para un control físico eficiente, el sistema genera etiquetas personalizables para cada bien. Estas etiquetas incluyen:

  - Número de inventario.
  - Descripción del bien.
  - **Un código QR único** que, al ser escaneado con un dispositivo móvil, puede dirigir a la ficha de información detallada del activo (funcionalidad futura).

### 📊 Módulo de Reportes Dinámicos

Una herramienta fundamental para el control y la fiscalización. Permite generar informes al instante, como:

  - Inventario general del municipio.
  - Inventario por área o unidad administrativa.
  - Inventario por responsable (resguardante).
  - Reporte mensual de movimientos patrimoniales (altas, bajas, traspasos) para informar a la Secretaría General Municipal, conforme al **Artículo 18 del Reglamento**.

-----

## 💻 Pila Tecnológica

| Componente      | Tecnología                                                                                                                                                                                                 |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Backend** |    Python                                                                                           |
| **Base de Datos** |  Mysql                                                                                       |
| **ORM** |  con `Flask-SQLAlchemy`                                                                                                                     |
| **Autenticación** |                                                                                                                                |
| **Formularios** |                                                                                                                                           |
| **Migraciones** |                                                                                                                                  |
| **Reportes PDF** |                                                                                                                                                       |
| **Imágenes** |                                                                                                                                             |
| **Exportación** |   exportación a Excel.                                              |

-----

## 🚀 Instalación y Puesta en Marcha

Sigue estos pasos para configurar el entorno de desarrollo local:

1.  **Clonar el repositorio:**

    ```bash
    git clone https://github.com/Marvkare/sistema-inventario.git
    cd sistema-inventario
    ```

2.  **Crear y activar un entorno virtual:**

    ```bash
    # Para Windows
    python3.12 -m venv venv
    .\venv\Scripts\activate

    # Para macOS/Linux
    python3.12 -m venv venv
    source venv/bin/activate
    ```

3.  **Instalar las dependencias:**

    ```bash
    pip install -r requirements_python312.txt
    ```

4.  **Configurar las variables de entorno:**
    Crea un archivo llamado `.env` en la raíz del proyecto y añade las siguientes variables. Este archivo es ignorado por Git para proteger tus credenciales.

    ```ini
    # Clave secreta para la seguridad de la sesión de Flask
    SECRET_KEY='tu_clave_secreta_aqui'

    # Configuración de la base de datos MySQL
    DB_HOST='localhost'
    DB_USER='tu_usuario_db'
    DB_PASSWORD='tu_contraseña_db'
    DB_NAME='nombre_de_tu_db'
    ```

5.  **Inicializar y migrar la base de datos:**
    Asegúrate de haber creado la base de datos en MySQL. Luego, ejecuta los comandos de Flask-Migrate.

    ```bash
    # Estos comandos deben ser ejecutados una vez para crear las tablas
    flask db init  # Solo la primera vez
    flask db migrate -m "Migración inicial"
    flask db upgrade
    ```

6.  **Ejecutar la aplicación:**

    ```bash
    flask run
    ```

    La aplicación estará disponible en `http://127.0.0.1:5000`.

-----

## 🗺️ Roadmap y Futuras Funcionalidades

El desarrollo del sistema es un proceso continuo. Las próximas etapas se centrarán en cerrar el ciclo de vida del bien y fortalecer las capacidades de auditoría:

  - [ ] **Módulo de Bajas y Disposición Final**: Implementar el flujo de trabajo normativo (dictamen técnico, avalúo, autorización del comité, enajenación) para la desincorporación de activos.
  - [ ] **Módulo de Auditoría (ASEH)**: Una interfaz de solo lectura diseñada para responder a los requerimientos de la Contraloría Interna y la ASEH, permitiendo generar expedientes digitales completos e históricos de cualquier bien.
  - [ ] **Dashboard de Control**: Un tablero con indicadores clave en tiempo real para la alta dirección (ej. bienes sin resguardo, bienes en mal estado, procesos de baja estancados).
  - [ ] **Alertas Automatizadas**: Notificaciones por correo sobre eventos críticos (ej. vencimiento de avalúos, falta de reportes mensuales).
  - [ ] **Integración con otros Sistemas**:
      - **Contabilidad**: Para la conciliación automática de pólizas.
      - **Recursos Humanos**: Para activar alertas de entrega-recepción en bajas de personal.

## ✍️ Autor

  * **Marvkare** - [GitHub Profile](https://www.google.com/search?q=https://github.com/Marvkare)