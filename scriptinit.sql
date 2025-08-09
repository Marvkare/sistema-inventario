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
    `No_Nomina` VARCHAR(50),
    `Proveedor` VARCHAR(255),
    `Fecha_Elaboracion` DATE,
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
    `Numero_De_Serie` VARCHAR(100)
);