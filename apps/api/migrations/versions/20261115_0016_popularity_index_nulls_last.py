"""Index popularity the way the catalog sorts it.

Catalog pages order by popularity_score DESC NULLS LAST. The original index was plain DESC,
which Postgres stores as NULLS FIRST, so it could not serve that ordering and the unfiltered
"popular" list sorted the whole catalog (about 13 seconds on the live database).
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0016"
down_revision = "20261020_0015"
branch_labels = None
depends_on = None

INDEX = "ix_fragrances_popularity_score_desc"


def upgrade() -> None:
    op.drop_index(INDEX, table_name="fragrances")
    op.create_index(INDEX, "fragrances", [sa.text("popularity_score DESC NULLS LAST")])


def downgrade() -> None:
    op.drop_index(INDEX, table_name="fragrances")
    op.create_index(INDEX, "fragrances", [sa.text("popularity_score DESC")])
