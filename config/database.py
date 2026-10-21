
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env
load_dotenv()

# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DATABASE_URL = os.getenv("DB_URL")

if not DATABASE_URL:
    raise ValueError(
        "DB_URL is missing. Please configure your Neon connection URL in .env"
    )

# =========================================================
# SQLALCHEMY
# =========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 15},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# =========================================================
# DATABASE SESSION
# =========================================================

def get_db():
    """Provide a database session and close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():
    """Create tables defined by the SQLAlchemy models."""
    from models.product import Product
    from models.customer import Customer
    from models.sales import Sale, SaleItem
    from models.inventory import Inventory

    Base.metadata.create_all(bind=engine)


# =========================================================
# DATABASE CONNECTION TEST
# =========================================================

def test_connection():
    """Test the PostgreSQL connection."""
    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            print(
                f"Successfully connected to PostgreSQL database: {database_name}"
            )
            return True

    except Exception as error:
        print(f"Database connection failed: {error}")
        return False
