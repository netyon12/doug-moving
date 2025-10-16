"""Adiciona suporte a múltiplas plantas por supervisor

Revision ID: supervisor_multiplas_plantas
Revises: 
Create Date: 2025-10-16 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'supervisor_multiplas_plantas'
down_revision = None  # Ajustar se houver migração anterior
branch_labels = None
depends_on = None


def upgrade():
    """
    Cria tabela de associação supervisor-planta e migra dados existentes
    """
    # 1. Criar tabela de associação
    op.create_table(
        'supervisor_planta_association',
        sa.Column('supervisor_id', sa.Integer(), nullable=False),
        sa.Column('planta_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['supervisor_id'], ['supervisor.id'], ),
        sa.ForeignKeyConstraint(['planta_id'], ['planta.id'], ),
        sa.PrimaryKeyConstraint('supervisor_id', 'planta_id')
    )
    
    # 2. Migrar dados existentes (copia planta_id para a tabela de associação)
    connection = op.get_bind()
    
    # Verifica qual banco está sendo usado
    if connection.engine.name == 'sqlite':
        # SQLite
        connection.execute(sa.text("""
            INSERT INTO supervisor_planta_association (supervisor_id, planta_id)
            SELECT id, planta_id FROM supervisor WHERE planta_id IS NOT NULL
        """))
    else:
        # PostgreSQL
        connection.execute(sa.text("""
            INSERT INTO supervisor_planta_association (supervisor_id, planta_id)
            SELECT id, planta_id FROM supervisor WHERE planta_id IS NOT NULL
        """))
    
    # 3. Tornar planta_id nullable (manter por compatibilidade temporária)
    with op.batch_alter_table('supervisor', schema=None) as batch_op:
        batch_op.alter_column('planta_id',
                              existing_type=sa.INTEGER(),
                              nullable=True)


def downgrade():
    """
    Reverte as mudanças
    """
    # Reverter planta_id para not null
    with op.batch_alter_table('supervisor', schema=None) as batch_op:
        batch_op.alter_column('planta_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)
    
    # Remover tabela de associação
    op.drop_table('supervisor_planta_association')

