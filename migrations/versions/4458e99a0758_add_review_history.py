"""add review history

Revision ID: 4458e99a0758
Revises: 52ea8ea11fb7
Create Date: 2014-09-25 14:36:07.186074

"""
revision = '4458e99a0758'
down_revision = '52ea8ea11fb7'
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('review_history', sa.Column('id', sa.Integer(), nullable=False), sa.Column('review_id', sa.Integer(), nullable=True), sa.Column('user_id', sa.Integer(), nullable=True), sa.Column('what', sa.Text(), nullable=True), sa.Column('prev', sa.Text(), nullable=True), sa.Column('new', sa.Text(), nullable=True), sa.Column('api_url', sa.Text(), nullable=True), sa.ForeignKeyConstraint(['review_id'], ['review.id']), sa.ForeignKeyConstraint(['user_id'], ['user.id']), sa.PrimaryKeyConstraint('id'))



def downgrade():
    op.drop_table('review_history')



