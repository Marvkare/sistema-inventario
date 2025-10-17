"""Modifica ProcesoBaja para registrar nombres de solicitante y jefe de área

Revision ID: 17554422ead4
Revises: <ID_de_la_revision_anterior>
Create Date: 2025-10-10 13:58:10.176906

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '17554422ead4'
down_revision = None # Ajusta esto si tienes una revisión anterior
branch_labels = None
depends_on = None


def upgrade():
    # ### Script ajustado para añadir las columnas faltantes ###
    with op.batch_alter_table('procesos_baja', schema=None) as batch_op:
        # Añadir las nuevas columnas que faltan
        batch_op.add_column(sa.Column('id_usuario_captura', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('nombre_solicitante', sa.String(length=255), nullable=False))
        batch_op.add_column(sa.Column('nombre_jefe_area', sa.String(length=255), nullable=True))
        
        # Crear la Foreign Key para la nueva columna
        batch_op.create_foreign_key(
            'fk_procesos_baja_id_usuario_captura_user', # Nombre para la constraint
            'user', ['id_usuario_captura'], ['id']
        )


def downgrade():
    # ### Script para revertir los cambios ###
    with op.batch_alter_table('procesos_baja', schema=None) as batch_op:
        # Eliminar la Foreign Key
        batch_op.drop_constraint('fk_procesos_baja_id_usuario_captura_user', type_='foreignkey')
        
        # Eliminar las columnas que se añadieron
        batch_op.drop_column('nombre_jefe_area')
        batch_op.drop_column('nombre_solicitante')
        batch_op.drop_column('id_usuario_captura')