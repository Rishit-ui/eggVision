"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-07 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    op.create_table('farms',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('devices',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('farm_id', sa.Uuid(), nullable=True),
        sa.Column('firmware_version', sa.String(), nullable=True),
        sa.Column('software_version', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('camera_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('hardware_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_sync', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_status', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )
    
    op.create_table('eggs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('egg_id', sa.String(), nullable=False),
        sa.Column('farm_id', sa.Uuid(), nullable=True),
        sa.Column('egg_type', sa.String(), nullable=True),
        sa.Column('laying_date', sa.Date(), nullable=True),
        sa.Column('storage_condition', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('egg_id')
    )
    
    op.create_table('batches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('batch_id', sa.String(), nullable=False),
        sa.Column('farm_id', sa.Uuid(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('total_eggs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scanned_eggs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id')
    )
    
    op.create_table('scans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('egg_id', sa.Uuid(), nullable=True),
        sa.Column('batch_id', sa.Uuid(), nullable=True),
        sa.Column('device_id', sa.Uuid(), nullable=True),
        sa.Column('original_image_url', sa.String(), nullable=True),
        sa.Column('processed_image_url', sa.String(), nullable=True),
        sa.Column('image_quality', sa.String(), nullable=True),
        sa.Column('image_quality_score', sa.Float(), nullable=True),
        sa.Column('image_quality_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('camera_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('capture_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], ),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['egg_id'], ['eggs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('predictions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('scan_id', sa.Uuid(), nullable=False),
        sa.Column('freshness_class', sa.String(), nullable=True),
        sa.Column('freshness_score', sa.Float(), nullable=True),
        sa.Column('estimated_age_min', sa.Integer(), nullable=True),
        sa.Column('estimated_age_max', sa.Integer(), nullable=True),
        sa.Column('predicted_haugh_unit', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('air_cell_area', sa.Float(), nullable=True),
        sa.Column('air_cell_ratio', sa.Float(), nullable=True),
        sa.Column('yolk_visibility', sa.String(), nullable=True),
        sa.Column('crack_probability', sa.Float(), nullable=True),
        sa.Column('blood_spot_probability', sa.Float(), nullable=True),
        sa.Column('explanation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('heatmap_url', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('inference_time_ms', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('sensor_readings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sa.Uuid(), nullable=True),
        sa.Column('scan_id', sa.Uuid(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('ambient_light', sa.Float(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('ground_truth',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('egg_id', sa.Uuid(), nullable=False),
        sa.Column('haugh_unit', sa.Float(), nullable=True),
        sa.Column('albumen_ph', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('observations', sa.Text(), nullable=True),
        sa.Column('measured_by', sa.String(), nullable=True),
        sa.Column('measured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['egg_id'], ['eggs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('model_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('model_type', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dataset_version', sa.String(), nullable=True),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version')
    )
    
    op.create_table('audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.Uuid(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('model_versions')
    op.drop_table('ground_truth')
    op.drop_table('sensor_readings')
    op.drop_table('predictions')
    op.drop_table('scans')
    op.drop_table('batches')
    op.drop_table('eggs')
    op.drop_table('devices')
    op.drop_table('farms')
    op.drop_table('users')
