import sqlite3

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path

    def create_db(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                original_path TEXT,
                hash TEXT,
                year TEXT,
                month TEXT,
                media_type TEXT,
                status TEXT,
                destination_path TEXT,
                final_name TEXT
            )
        """)
        conn.commit()
        return conn

    def insert_file(self, conn, record):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (original_path, hash, year, month, media_type, status, destination_path, final_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, record)
        conn.commit()
