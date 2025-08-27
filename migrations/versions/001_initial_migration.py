"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2025-08-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create policies table
    op.create_table(
        'policies',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False, index=True),
        sa.Column('issuer', sa.String(100), nullable=False, index=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('scope', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('text_full', sa.Text(), nullable=True),
        sa.Column('last_updated', sa.Date(), nullable=True),
    )
    
    # Create procedures table
    op.create_table(
        'procedures',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('policy_id', sa.String(50), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('applies_to', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('deadlines', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('fees', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('contacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    
    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('policy_id', sa.String(50), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('page', sa.Integer(), nullable=True),
        sa.Column('clause', sa.String(100), nullable=True),
        sa.Column('bbox', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    
    # Create chunks table
    op.create_table(
        'chunks',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('policy_id', sa.String(50), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('section', sa.String(255), nullable=True, index=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('url', sa.String(1024), nullable=True),
        sa.Column('page', sa.Integer(), nullable=True),
        sa.Column('bbox', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('chunks')
    op.drop_table('sources')
    op.drop_table('procedures')
    op.drop_table('policies')
