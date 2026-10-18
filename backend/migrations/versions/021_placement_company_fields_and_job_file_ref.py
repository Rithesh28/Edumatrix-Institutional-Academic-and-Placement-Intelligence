"""
Make company industry and location mandatory and add optional file_id to job_postings

Revision ID: 021
Revises: 020
Create Date: 2026-10-18 22:30:00.000000

This migration:
- Backfills any NULL or whitespace-only industry/location values in companies (safety default)
- Alters companies.industry to nullable=False
- Alters companies.location to nullable=False
- Adds nullable file_id column (UUID) to job_postings referencing files.id with ON DELETE SET NULL
- Creates index ix_job_postings_file_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Update companies table if it exists
    if 'companies' in existing_tables:
        # Backfill any NULL or whitespace-only industry and location before enforcing NOT NULL
        op.execute("UPDATE companies SET industry = 'General' WHERE industry IS NULL OR TRIM(industry) = ''")
        op.execute("UPDATE companies SET location = 'Not Specified' WHERE location IS NULL OR TRIM(location) = ''")

        # Alter industry and location to nullable=False with server_default
        op.alter_column('companies', 'industry', existing_type=sa.String(length=100), nullable=False, server_default='General')
        op.alter_column('companies', 'location', existing_type=sa.String(length=255), nullable=False, server_default='Not Specified')

    # 2. Update job_postings table if it exists
    if 'job_postings' in existing_tables:
        existing_columns_jobs = [c['name'] for c in inspector.get_columns('job_postings')]
        if 'file_id' not in existing_columns_jobs:
            op.add_column(
                'job_postings',
                sa.Column('file_id', UUID(as_uuid=True), nullable=True)
            )
            op.create_foreign_key(
                'fk_job_postings_file_id_files',
                'job_postings',
                'files',
                ['file_id'],
                ['id'],
                ondelete='SET NULL'
            )
            op.create_index('ix_job_postings_file_id', 'job_postings', ['file_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Revert job_postings table
    if 'job_postings' in existing_tables:
        existing_columns_jobs = [c['name'] for c in inspector.get_columns('job_postings')]
        existing_indexes_jobs = [ix['name'] for ix in inspector.get_indexes('job_postings')]
        foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys('job_postings')]

        if 'ix_job_postings_file_id' in existing_indexes_jobs:
            op.drop_index('ix_job_postings_file_id', table_name='job_postings')

        if 'fk_job_postings_file_id_files' in foreign_keys:
            op.drop_constraint('fk_job_postings_file_id_files', 'job_postings', type_='foreignkey')

        if 'file_id' in existing_columns_jobs:
            op.drop_column('job_postings', 'file_id')

    # 2. Revert companies table
    if 'companies' in existing_tables:
        op.alter_column('companies', 'location', existing_type=sa.String(length=255), nullable=True, server_default=None)
        op.alter_column('companies', 'industry', existing_type=sa.String(length=100), nullable=True, server_default=None)
