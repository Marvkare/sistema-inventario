-- Eliminar tablas en orden de dependencia para evitar errores
DROP TABLE IF EXISTS resguardos;
DROP TABLE IF EXISTS bienes;
DROP TABLE IF EXISTS areas;

-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS inventario;

-- Usar la base de datos inventario
USE inventario;

-- Crear la tabla areas (note: using lowercase consistently)

-- Tabla para almacenar la información de los usuarios
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

-- Tabla para almacenar los roles
CREATE TABLE role (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) UNIQUE NOT NULL,
    description VARCHAR(255)
);

-- Tabla de unión para vincular usuarios con roles (muchos a muchos)
CREATE TABLE roles_users (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES role(id) ON DELETE CASCADE
);

CREATE TABLE areas (
    `id` INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(255) NOT NULL,
    numero INT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear la tabla Bienes (note: using lowercase for consistency)
CREATE TABLE bienes (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `No_Inventario` VARCHAR(50) UNIQUE,
    `No_Factura` VARCHAR(50),
    `No_Cuenta` VARCHAR(50),
    `No_Resguardo` VARCHAR(50),
    `Proveedor` VARCHAR(255),
    `Descripcion_Del_Bien` TEXT,
    `Descripcion_Corta_Del_Bien` VARCHAR(512), 
    `Area` VARCHAR(100),
    `Rubro` VARCHAR(100),
    `Poliza` VARCHAR(50),
    `Fecha_Poliza` DATE,
    `Sub_Cuenta_Armonizadora` VARCHAR(100),
    `Fecha_Factura` DATE,
    `Costo_Inicial` DECIMAL(10, 2),
    `Depreciacion_Acumulada` DECIMAL(10, 2),
    `Costo_Final_Cantidad` DECIMAL(10, 2),
    `Cantidad` INT,
    `Estado_Del_Bien` VARCHAR(50),
    `Marca` VARCHAR(100),
    `Modelo` VARCHAR(100),
    `Numero_De_Serie` VARCHAR(100)  
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `imagenes_bien` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_bien` INT NOT NULL,
    `ruta_imagen` VARCHAR(255) NOT NULL,
    `fecha_subida` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_bien`) REFERENCES `bienes`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `imagenes_resguardo` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_resguardo` INT NOT NULL,
    `ruta_imagen` VARCHAR(255) NOT NULL,
    `fecha_subida` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`id_resguardo`) REFERENCES `resguardos`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Crear la tabla Resguardos con referencias correctas
CREATE TABLE resguardos (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `id_bien` INT NOT NULL,
    `id_area` INT NOT NULL,
    `No_Resguardo` VARCHAR(50) UNIQUE,
    `Tipo_De_Resguardo` INT,
    `Fecha_Resguardo` DATE,
    `No_Trabajador` VARCHAR(50),
    `Puesto` VARCHAR(100),
    `Nombre_Director_Jefe_De_Area` VARCHAR(255),
    `Nombre_Del_Resguardante` VARCHAR(255),
    `Fecha_Registro` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `Fecha_Ultima_Modificacion` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `Activo` BOOLEAN NOT NULL DEFAULT TRUE, 

    CONSTRAINT fk_resguardos_bien
        FOREIGN KEY (`id_bien`)
        REFERENCES bienes(`id`)
        ON DELETE RESTRICT,
    
    CONSTRAINT fk_resguardos_area
        FOREIGN KEY (`id_area`)
        REFERENCES areas(`id`)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS query_templates (
    id INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    columns JSON,
    filters JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS inventario;



CREATE TABLE IF NOT EXISTS oficio_traspaso (
    `id` INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    `Dependencia` VARCHAR(255),
    `Area` VARCHAR(255),
    `Oficio_clave` VARCHAR(255),
    `Asunto` TEXT,
    `Lugar_Fecha` DATE,
    `Secretaria_General_Municipal` VARCHAR(255),
    `No_Inventario` VARCHAR(50),
    `Cantidad` INT,
    `Descripcion` TEXT,
    `Tipo` VARCHAR(50),
    `id_resguardo_anterior` INT NOT NULL,
    `id_resguardo_actual` INT NOT NULL,
    `Fecha_Traspaso_DB` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `Fecha_Ultima_Modificacion` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

    CONSTRAINT fk_traspaso_resguardo_anterior
        FOREIGN KEY (`id_resguardo_anterior`)
        REFERENCES resguardos(`id`)
        ON DELETE RESTRICT,

    CONSTRAINT fk_traspaso_resguardo_actual
        FOREIGN KEY (`id_resguardo_actual`)
        REFERENCES resguardos(`id`)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Estructura de tabla para la tabla `resguardo_errores`
--
CREATE TABLE `resguardo_errores` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `upload_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `No_Inventario` text COLLATE utf8mb4_unicode_ci,
  `No_Factura` text COLLATE utf8mb4_unicode_ci,
  `No_Cuenta` text COLLATE utf8mb4_unicode_ci,
  `No_Resguardo` text COLLATE utf8mb4_unicode_ci,
  `No_Trabajador` text COLLATE utf8mb4_unicode_ci,
  `Proveedor` text COLLATE utf8mb4_unicode_ci,
  `Fecha_Resguardo` text COLLATE utf8mb4_unicode_ci,
  `Descripcion_Del_Bien` text COLLATE utf8mb4_unicode_ci,
  `Descripcion_Fisica` text COLLATE utf8mb4_unicode_ci,
  `Area` text COLLATE utf8mb4_unicode_ci,
  `Rubro` text COLLATE utf8mb4_unicode_ci,
  `Poliza` text COLLATE utf8mb4_unicode_ci,
  `Fecha_Poliza` text COLLATE utf8mb4_unicode_ci,
  `Sub_Cuenta_Armonizadora` text COLLATE utf8mb4_unicode_ci,
  `Fecha_Factura` text COLLATE utf8mb4_unicode_ci,
  `Costo_Inicial` text COLLATE utf8mb4_unicode_ci,
  `Depreciacion_Acumulada` text COLLATE utf8mb4_unicode_ci,
  `Costo_Final_Cantidad` text COLLATE utf8mb4_unicode_ci,
  `Cantidad` text COLLATE utf8mb4_unicode_ci,
  `Puesto` text COLLATE utf8mb4_unicode_ci,
  `Nombre_Director_Jefe_De_Area` text COLLATE utf8mb4_unicode_ci,
  `Tipo_De_Resguardo` text COLLATE utf8mb4_unicode_ci,
  `Adscripcion_Direccion_Area` text COLLATE utf8mb4_unicode_ci,
  `Nombre_Del_Resguardante` text COLLATE utf8mb4_unicode_ci,
  `Estado_Del_Bien` text COLLATE utf8mb4_unicode_ci,
  `Marca` text COLLATE utf8mb4_unicode_ci,
  `Modelo` text COLLATE utf8mb4_unicode_ci,
  `Numero_De_Serie` text COLLATE utf8mb4_unicode_ci,
  `Imagen_Path` VARCHAR(255),
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `Fecha_Registro` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Ultima_Modificacion` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_upload_id` (`upload_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


--
-- Estructura de tabla para la tabla `query_templates`
--


INSERT INTO areas (nombre, numero) VALUES
('SERVICIOS PÚBLICOS', null),
('MAQUINARIA Y PARQUE VEHICULAR', NULL),
('COMUNICACIÓN SOCIAL Y SISTEMAS', NULL),
('DIF MUNICIPAL (DIRECCION)', NULL),
('OFICIALIA MAYOR', NULL),
('CAPASMAH', NULL),
('INSTITUTO MUNICIPAL DEL DEPORTE', NULL),
('TESORERIA MUNICIPAL', NULL),
('DESARROLLO URBANO Y MOVILIDAD', NULL),
('PRESIDENCIA MUNICIPAL', NULL),
('SECRETARIA GENERAL MUNICIPAL', NULL),
('HONORABLE ASAMBLEA', NULL),
('SEGURIDAD PÚBLICA Y TRÁNSITO MUNICIPAL', NULL),
('DESARROLLO SOCIAL', NULL),
('PROTECCIÓN CIVIL Y BOMBEROS', NULL),
('REGLAMENTOS Y ESPECTÁCULOS', NULL),
('INSTANCIA MUNICIPAL  DE LAS MUJERES', NULL),
('CONCILIADOR MUNICIPAL', NULL),
('CASA DE CULTURA', NULL),
('CONTRALORIA INTERNA MUNICIPAL', NULL);

