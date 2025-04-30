"""
Migration script to add password reset tokens table
"""

import logging
import sqlite3
from app.core.database import get_db

logger = logging.getLogger(__name__)

def run_migration():
    """
    Add password_reset_tokens table to the database
    """
    try:
        with get_db() as db:
            # Check if the table already exists
            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_tokens'")
            result = cursor.fetchone()

            if result:
                logger.info("password_reset_tokens table already exists")
                return True

            # Create the password_reset_tokens table
            db.execute("""
                CREATE TABLE password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Create an index on the token for faster lookups
            db.execute("CREATE INDEX idx_password_reset_tokens_token ON password_reset_tokens (token)")

            # Create an index on the user_id for faster lookups
            db.execute("CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens (user_id)")

            db.commit()
            logger.info("Successfully created password_reset_tokens table")
            return True

    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error creating password_reset_tokens table: {e}")
        return False
