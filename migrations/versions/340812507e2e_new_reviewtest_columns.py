"""New ReviewTest columns

Revision ID: 340812507e2e
Revises: 52ea8ea11fb7
Create Date: 2015-10-15 22:38:30.312116

"""

# revision identifiers, used by Alembic.
revision = '340812507e2e'
down_revision = '52ea8ea11fb7'

from alembic import op
import sqlalchemy as sa

import reviewq


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("review_test") as batch_op:
        batch_op.add_column(sa.Column('substrate', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('updated', reviewq.models.UTCDateTime(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("review_test") as batch_op:
        batch_op.drop_column('updated')
        batch_op.drop_column('substrate')
    ### end Alembic commands ###
