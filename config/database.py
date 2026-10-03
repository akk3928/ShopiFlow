
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "shopiflow")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


# PostgreSQL connection URL
DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


# =========================================================
# SQLALCHEMY
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


# =========================================================
# DATABASE SESSION
# =========================================================

def get_db():
    """
    Provide a database session.

    The session is automatically closed
    after use.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    """
    Create all database tables defined
    by the SQLAlchemy models.
    """

    # Import models before creating tables
    from models.product import Product
    from models.customer import Customer
    from models.sales import Sale, SaleItem
    from models.inventory import Inventory

    Base.metadata.create_all(bind=engine)


# =========================================================
# DATABASE CONNECTION TEST
# =========================================================

def test_connection():
    """
    Test the PostgreSQL database connection.
    """

    try:
        with engine.connect() as connection:
            print("Successfully connected to ShopiFlow PostgreSQL database.")
            return True

    except Exception as error:
        print(f"Database connection failed: {error}")
        return False

