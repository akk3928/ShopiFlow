import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Database:
    """PostgreSQL database connection manager for ShopiFlow."""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.database = os.getenv("DB_NAME", "shopiflow")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD")

    def connect(self):
        """Create and return a PostgreSQL database connection."""
        try:
            connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )

            print("Successfully connected to ShopiFlow database.")
            return connection

        except psycopg2.Error as error:
            print(f"Database connection failed: {error}")
            return None

    def close(self, connection):
        """Close the database connection."""
        if connection:
            connection.close()
            print("Database connection closed.")
