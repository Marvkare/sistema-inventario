-- Crear la base de datos si no existe
CREATE DATABASE IF NOT EXISTS inventario;

-- Usar la base de datos inventario
USE inventario;

-- Crear la tabla resguardo
CREATE TABLE IF NOT EXISTS resguardo (
    `No_Folio` INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    `No_Inventario` VARCHAR(50) UNIQUE NOT NULL,
    `No_Factura` VARCHAR(50),
    `No_Cuenta` VARCHAR(50),
    `No_Resguardo` VARCHAR(50) UNIQUE NOT NULL,
    `No_Trabajador` VARCHAR(50),
    `Proveedor` VARCHAR(255),
    `Fecha_Resguardo` DATE,
    `Descripcion_Del_Bien` TEXT,
    `Descripcion_Fisica` TEXT,
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
    `Nombre_Del_Usuario` VARCHAR(255),
    `Puesto` VARCHAR(100),
    `Nombre_Director_Jefe_Area` VARCHAR(255),
    `Tipo_De_Resguardo` VARCHAR(100),
    `Adscripcion_Direccion_Area` VARCHAR(255),
    `Nombre_Del_Resguardante` VARCHAR(255),
    `Estado_Del_Bien` VARCHAR(50),
    `Marca` VARCHAR(100),
    `Modelo` VARCHAR(100),
    `Numero_De_Serie` VARCHAR(100),
    `Fecha_Registro` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `Fecha_Ultima_Modificacion` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

--
-- Estructura de tabla para la tabla `resguardo_errores`
--
CREATE TABLE `resguardo_errores` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `upload_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `No_Folio` text COLLATE utf8mb4_unicode_ci,
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
  `Nombre_Del_Usuario` text COLLATE utf8mb4_unicode_ci,
  `Puesto` text COLLATE utf8mb4_unicode_ci,
  `Nombre_Director_Jefe_Area` text COLLATE utf8mb4_unicode_ci,
  `Tipo_De_Resguardo` text COLLATE utf8mb4_unicode_ci,
  `Adscripcion_Direccion_Area` text COLLATE utf8mb4_unicode_ci,
  `Nombre_Del_Resguardante` text COLLATE utf8mb4_unicode_ci,
  `Estado_Del_Bien` text COLLATE utf8mb4_unicode_ci,
  `Marca` text COLLATE utf8mb4_unicode_ci,
  `Modelo` text COLLATE utf8mb4_unicode_ci,
  `Numero_De_Serie` text COLLATE utf8mb4_unicode_ci,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `idx_upload_id` (`upload_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
