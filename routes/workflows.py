# Este diccionario centraliza toda la lógica de negocio para los procesos de baja.
# Define la línea de tiempo, los documentos requeridos y las transiciones de estado
# para cada motivo de baja posible.

WORKFLOWS = {
    'Obsolescencia': {
        'timeline': ['Solicitado', 'Pendiente de Comité', 'Autorizado para Disposición', 'Finalizado'],
        'documentos_requeridos': {
            'Solicitud de Baja': 'Oficio inicial que arranca el proceso.',
            'Fotografías del bien': 'Evidencia fotográfica del estado actual del bien.',
            'Dictamen Técnico': 'Justificación técnica de por qué el bien es obsoleto.',
            'Acta de Comité': 'Autorización del comité para proceder con la baja.',
            'Acta de Baja': 'Documento que formaliza la disposición final (venta, donación, etc.).'
        },
        'transiciones': {
            'Solicitado': {
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Dictamen Técnico',
                'texto_accion': 'Enviar a Comité'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Autorizado para Disposición',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Autorizar Disposición'
            },
            'Autorizado para Disposición': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Baja', # Requiere el acta final
                'texto_accion': 'Finalizar Proceso'
            }
        }
    },
    'Inutilidad': {
        'timeline': ['Solicitado', 'Pendiente de Comité', 'Autorizado para Disposición', 'Finalizado'],
        'documentos_requeridos': {
            'Solicitud de Baja': 'Oficio inicial que arranca el proceso.',
            'Fotografías del bien': 'Evidencia fotográfica del daño del bien.',
            'Dictamen Técnico': 'Justificación técnica de que el bien es inservible y su reparación no es viable.',
            'Acta de Comité': 'Autorización del comité para proceder con la baja.',
            'Acta de Baja': 'Documento que formaliza la disposición final (destrucción, etc.).'
        },
        'transiciones': {
            'Solicitado': {
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Dictamen Técnico',
                'texto_accion': 'Enviar a Comité'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Autorizado para Disposición',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Autorizar Disposición'
            },
            'Autorizado para Disposición': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Baja',
                'texto_accion': 'Finalizar Proceso'
            }
        }
    },
    'Robo': {
        'timeline': ['Solicitado', 'Registrar Acta de Echos','Registrar Denuncia Penal ','Pendiente de Comité', 'Finalizado'], # Flujo más corto
        'documentos_requeridos': {
            'Solicitud de Baja': 'Acta circunstanciada de hechos o similar.',
            'Acta de echos': 'Documento que describe los hechos del robo interna.',
            'Denuncia de Robo': 'Copia certificada de la denuncia penal ante el MP. Indispensable.',
            'Acta de Comité': 'Autorización del comité para la baja administrativa.',
            'Acta de Baja': 'Documento que formaliza la baja contable.'
        },
        'transiciones': {
            'Solicitado': {
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Solicitud de Baja',
                'texto_accion': 'Enviar a Comité con Denuncia'
            },
            'Resgistrar Acta de Echos':{
                'siguiente_estatus': 'Registrar Denuncia Penal',
                'documento_necesario': 'Acta de Echos',
                'texto_accion': 'Enviar a Comité con Resolución'
            }, 
            'Registrar Denuncia Penal':{ 
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Denuncia de Robo',
                'texto_accion': 'Enviar a Comité con Denuncia'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Finalizar (Baja Administrativa)'
            }
        }
    },
    'Extravío': {
        'timeline': ['Solicitado', 'Pendiente de Comité', 'Finalizado'], # Flujo similar a Robo
        'documentos_requeridos': {
            'Solicitud de Baja': 'Acta circunstanciada de hechos.',
            'Acta de Investigación': 'Resolución de la Contraloría Interna sobre la investigación y deslinde de responsabilidades.',
            'Acta de Comité': 'Autorización del comité basada en la resolución de Contraloría.',
            'Acta de Baja': 'Documento que formaliza la baja contable.'
        },
        'transiciones': {

            'Solicitado': {
                'siguiente_estatus': 'Generar Acta de Echos',
                'documento_necesario': 'Solicitud de Baja',
                'texto_accion': 'Iniciar Investigación'
            },
            
            'Generar Acta de Echos':{
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Acta de Investigación',
                'texto_accion': 'Enviar a Comité con Resolución'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Finalizar (Baja Administrativa)'
            }
        }
    },
    'Siniestro': {
        'timeline': ['Solicitado', 'Pendiente de Comité', 'Autorizado para Disposición', 'Finalizado'],
        'documentos_requeridos': {
            'Solicitud de Baja': 'Acta circunstanciada de hechos sobre el siniestro.',
            'Fotografías del bien': 'Evidencia fotográfica del siniestro.',
            'Acta de Siniestro': 'Dictamen de aseguradora o reporte de autoridades (Protección Civil, etc.).',
            'Acta de Comité': 'Autorización del comité para la baja.',
            'Acta de Baja': 'Documento para la disposición de los restos (chatarra).'
        },
        'transiciones': {
            'Solicitado': {
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Acta de Siniestro',
                'texto_accion': 'Enviar a Comité'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Autorizado para Disposición',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Autorizar Disposición'
            },
            'Autorizado para Disposición': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Baja',
                'texto_accion': 'Finalizar Proceso'
            }
        }
    },
    'Enajenación': {
        'timeline': ['Solicitado', 'Pendiente de Comité', 'Autorizado para Disposición', 'Finalizado'],
        'documentos_requeridos': {
            'Solicitud de Baja': 'Acuerdo del Ayuntamiento o Acta de Comité para enajenar.',
            'Avalúo Comercial': 'Documento que determina el precio de salida del bien.',
            'Acta de Comité': 'Autorización del procedimiento de venta.',
            'Acta de Baja': 'Documento que formaliza la venta (factura, acta de fallo, etc.).'
        },
        'transiciones': {
            'Solicitado': {
                'siguiente_estatus': 'Pendiente de Comité',
                'documento_necesario': 'Avalúo Comercial',
                'texto_accion': 'Enviar a Comité con Avalúo'
            },
            'Pendiente de Comité': {
                'siguiente_estatus': 'Autorizado para Disposición',
                'documento_necesario': 'Acta de Comité',
                'texto_accion': 'Autorizar Venta'
            },
            'Autorizado para Disposición': {
                'siguiente_estatus': 'Finalizado',
                'documento_necesario': 'Acta de Baja',
                'texto_accion': 'Finalizar Proceso de Venta'
            }
        }
    },
}

# Añadimos un alias para 'Extravío' por si se usa indistintamente
WORKFLOWS['Extravio'] = WORKFLOWS['Extravío']

# Un workflow por defecto en caso de que el motivo no se encuentre
DEFAULT_WORKFLOW = WORKFLOWS['Inutilidad']  