"""New class ProductImages

Revision ID: 06d2a7ab1bfc
Revises: 75eb9356217f
Create Date: 2025-02-06 21:52:43.939565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '06d2a7ab1bfc'
down_revision = '75eb9356217f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.drop_column('image')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image', sa.VARCHAR(), nullable=False))

    # ### end Alembic commands ###
