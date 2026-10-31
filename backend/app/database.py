from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        columns = {column["name"] for column in inspect(engine).get_columns("recordings")}
        if "file_sha256" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE recordings ADD COLUMN file_sha256 VARCHAR(64)"))
                connection.execute(
                    text("CREATE UNIQUE INDEX IF NOT EXISTS ix_recordings_file_sha256 "
                         "ON recordings (file_sha256)")
                )
        insight_columns = {column["name"] for column in inspect(engine).get_columns("recording_insights")}
        with engine.begin() as connection:
            if "topic" not in insight_columns:
                connection.execute(text("ALTER TABLE recording_insights ADD COLUMN topic VARCHAR(255)"))
            if "highlights" not in insight_columns:
                connection.execute(text("ALTER TABLE recording_insights ADD COLUMN highlights TEXT"))
