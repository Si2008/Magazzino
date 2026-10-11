"""Base dichiarativa condivisa da tutti i modelli del dominio."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# Convenzioni di naming per i vincoli: garantiscono nomi deterministici
# e unici dei constraint, così i dump e i migration restano stabili.
CONVENZIONE_NOMI = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe base SQLAlchemy 2.x: tutti i modelli la ereditano."""

    metadata = MetaData(naming_convention=CONVENZIONE_NOMI)
