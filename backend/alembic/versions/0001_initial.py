"""Initial schema: users, workspaces, documents, conversations, usage, audit.

DRY approach for the scaffold: the migration materializes the current ORM
metadata. Production teams switch to explicit op.create_table() sequences once
the schema stabilizes (see docs/11-database.md).
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from app.db.models import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.db.models import Base

    Base.metadata.drop_all(bind=bind)