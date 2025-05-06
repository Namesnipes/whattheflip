from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Provide a default or raise an error if not set
    # For local dev, you might default to SQLite if preferred
    # DATABASE_URL = "sqlite:///./sql_app.db"
    # engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    raise ValueError("DATABASE_URL environment variable not set.")
else:
    # For PostgreSQL
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session in FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
