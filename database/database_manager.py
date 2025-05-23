# -*- coding: utf-8 -*-
"""
Thread-Safe DatabaseManager - v1.0.0
Manager database thread-safe per gestire operazioni SQLite concorrenti
"""

from typing import Dict, List, Optional, Any, Tuple
import sqlite3
import threading
import logging
from pathlib import Path


class DatabaseManager:
    """
    Manager database thread-safe per gestire operazioni SQLite concorrenti.
    Supporta connessioni multiple e operazioni atomiche.
    """
    
    def __init__(self, db_path: str):
        """
        Inizializza il database manager con supporto thread-safe.
        
        Args:
            db_path: Percorso del file database SQLite
        """
        self.db_path = db_path
        self._global_lock = threading.Lock()
        self._initialized = False
        
        # Assicura che la directory del database esista
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.info(f"DatabaseManager inizializzato: {db_path}")

    def create_db(self) -> sqlite3.Connection:
        """
        Crea una connessione database thread-safe con schema inizializzato.
        
        Returns:
            sqlite3.Connection: Connessione database configurata per thread-safety
        """
        # Configurazione SQLite per thread-safety
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Permette uso da thread diversi
            timeout=30.0,  # Timeout per lock contention
            isolation_level='DEFERRED'  # Transazioni ottimizzate
        )
        
        # Configura SQLite per prestazioni e concorrenza
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging per concorrenza
        conn.execute("PRAGMA synchronous=NORMAL")  # Bilanciamento sicurezza/prestazioni
        conn.execute("PRAGMA temp_store=MEMORY")  # Tabelle temporanee in memoria
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
        conn.execute("PRAGMA cache_size=10000")  # Cache più grande
        
        # Inizializza schema solo una volta
        with self._global_lock:
            if not self._initialized:
                self._initialize_schema(conn)
                self._initialized = True
        
        return conn

    def _initialize_schema(self, conn: sqlite3.Connection):
        """
        Inizializza lo schema del database con indici ottimizzati.
        
        Args:
            conn: Connessione database
        """
        cursor = conn.cursor()
        
        # Tabella principale files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT NOT NULL,
                hash TEXT NOT NULL,
                year TEXT,
                month TEXT,
                media_type TEXT,
                status TEXT,
                destination_path TEXT,
                final_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                processing_thread TEXT
            )
        """)
        
        # Indici per prestazioni
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_hash 
            ON files(hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_media_type_year_month 
            ON files(media_type, year, month)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_status 
            ON files(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_files_original_path 
            ON files(original_path)
        """)
        
        # Tabella statistiche processing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_files INTEGER DEFAULT 0,
                processed_files INTEGER DEFAULT 0,
                duplicate_files INTEGER DEFAULT 0,
                error_files INTEGER DEFAULT 0,
                worker_threads INTEGER DEFAULT 1,
                session_duration REAL,
                completed_at TIMESTAMP
            )
        """)
        
        conn.commit()
        logging.info("Schema database inizializzato con indici ottimizzati")

    def insert_file(self, conn: sqlite3.Connection, record: Tuple[str, ...]):
        """
        Inserisce thread-safe un record file nel database.
        
        Args:
            conn: Connessione database thread-specific
            record: Tupla con dati del file
        """
        cursor = conn.cursor()
        
        try:
            # Aggiungi informazioni thread
            extended_record = record + (threading.get_ident(),)
            
            cursor.execute("""
                INSERT INTO files (
                    original_path, hash, year, month, media_type, 
                    status, destination_path, final_name, processing_thread
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, extended_record)
            
            conn.commit()
            
        except sqlite3.IntegrityError as e:
            logging.error(f"Errore integrità database: {e}")
            conn.rollback()
            raise
        except sqlite3.OperationalError as e:
            logging.error(f"Errore operazionale database: {e}")
            conn.rollback()
            raise
        except Exception as e:
            logging.error(f"Errore inserimento database: {e}")
            conn.rollback()
            raise

    def check_duplicate(self, conn: sqlite3.Connection, file_hash: str) -> bool:
        """
        Controlla thread-safe se un hash è già presente nel database.
        
        Args:
            conn: Connessione database
            file_hash: Hash del file da controllare
            
        Returns:
            bool: True se il file è un duplicato
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM files WHERE hash = ?",
            (file_hash,)
        )
        count = cursor.fetchone()[0]
        return count > 0

    def get_file_by_hash(self, conn: sqlite3.Connection, file_hash: str) -> Optional[Tuple]:
        """
        Recupera informazioni di un file tramite hash.
        
        Args:
            conn: Connessione database
            file_hash: Hash del file
            
        Returns:
            Optional[Tuple]: Record del file o None se non trovato
        """
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM files WHERE hash = ? LIMIT 1",
            (file_hash,)
        )
        return cursor.fetchone()

    def start_processing_session(self, total_files: int, worker_threads: int) -> int:
        """
        Inizia una nuova sessione di processing e ritorna l'ID sessione.
        
        Args:
            total_files: Numero totale di file da processare
            worker_threads: Numero di thread worker
            
        Returns:
            int: ID della sessione
        """
        with self._global_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO processing_stats (total_files, worker_threads)
                VALUES (?, ?)
            """, (total_files, worker_threads))
            
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logging.info(f"Nuova sessione processing avviata: ID {session_id}")
            return session_id

    def update_processing_stats(
        self,
        session_id: int,
        processed_files: int,
        duplicate_files: int,
        error_files: int
    ):
        """
        Aggiorna statistiche della sessione di processing.
        
        Args:
            session_id: ID della sessione
            processed_files: File processati
            duplicate_files: File duplicati
            error_files: File con errori
        """
        with self._global_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE processing_stats 
                SET processed_files = ?, duplicate_files = ?, error_files = ?
                WHERE id = ?
            """, (processed_files, duplicate_files, error_files, session_id))
            
            conn.commit()
            conn.close()

    def complete_processing_session(self, session_id: int, duration: float):
        """
        Completa una sessione di processing.
        
        Args:
            session_id: ID della sessione
            duration: Durata in secondi
        """
        with self._global_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE processing_stats 
                SET session_duration = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (duration, session_id))
            
            conn.commit()
            conn.close()
            
            logging.info(f"Sessione processing {session_id} completata in {duration:.2f}s")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Recupera statistiche complete dal database.
        
        Returns:
            Dict[str, Any]: Statistiche complete
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Stats generali
        cursor.execute("""
            SELECT 
                COUNT(*) as total_files,
                COUNT(CASE WHEN status = 'copied' THEN 1 END) as processed,
                COUNT(CASE WHEN status = 'duplicate' THEN 1 END) as duplicates,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as errors,
                COUNT(CASE WHEN media_type = 'PHOTO' THEN 1 END) as photos,
                COUNT(CASE WHEN media_type = 'VIDEO' THEN 1 END) as videos
            FROM files
        """)
        
        general_stats = cursor.fetchone()
        
        # Stats per anno
        cursor.execute("""
            SELECT year, COUNT(*) as count
            FROM files 
            WHERE year != 'Unknown'
            GROUP BY year 
            ORDER BY year DESC
        """)
        
        yearly_stats = cursor.fetchall()
        
        # Ultima sessione
        cursor.execute("""
            SELECT * FROM processing_stats 
            ORDER BY session_start DESC 
            LIMIT 1
        """)
        
        last_session = cursor.fetchone()
        
        conn.close()
        
        return {
            'general': {
                'total_files': general_stats[0],
                'processed_files': general_stats[1],
                'duplicate_files': general_stats[2],
                'error_files': general_stats[3],
                'photos': general_stats[4],
                'videos': general_stats[5]
            },
            'yearly': dict(yearly_stats),
            'last_session': last_session
        }

    def cleanup_database(self):
        """
        Operazioni di pulizia e ottimizzazione del database.
        """
        with self._global_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Vacuum per ottimizzare spazio
            cursor.execute("VACUUM")
            
            # Analizza per aggiornare statistiche query optimizer
            cursor.execute("ANALYZE")
            
            conn.close()
            logging.info("Database ottimizzato e pulito")

    def export_report(self, output_path: str):
        """
        Esporta un report dettagliato in formato CSV.
        
        Args:
            output_path: Percorso file di output
        """
        import csv
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                original_path,
                hash,
                year,
                month,
                media_type,
                status,
                destination_path,
                final_name,
                created_at
            FROM files
            ORDER BY created_at DESC
        """)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Percorso Originale', 'Hash', 'Anno', 'Mese', 'Tipo Media',
                'Status', 'Destinazione', 'Nome Finale', 'Data Processing'
            ])
            writer.writerows(cursor.fetchall())
        
        conn.close()
        logging.info(f"Report esportato: {output_path}")