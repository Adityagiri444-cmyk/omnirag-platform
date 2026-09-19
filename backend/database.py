import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Database URL - read from .env, never hardcoded here. This used to have the
# actual PostgreSQL password committed directly in this file, which meant it
# would be exposed to anyone with the code (including via git/GitHub), and
# would only work on the one machine with that exact username/password.
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency - gives database session to each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()