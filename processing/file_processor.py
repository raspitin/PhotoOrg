# -*- coding: utf-8 -*-
"""
FileProcessor with Parallel Processing Support - v1.0.0
Processore di file con supporto per elaborazione parallela multi-thread
"""

from typing import List, Tuple, Optional, Dict, Any
import os
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from processing.date_extractor import DateExtractor
from processing.hash_utils import HashUtils
from processing.file_utils import FileUtils


class FileProcessor:
    """
    Processore di file con supporto per elaborazione parallela multi-thread.
    Gestisce scansione, estrazione metadati, organizzazione e tracking database.
    """
    
    def __init__(
        self,
        source_dir: str,
        dest_dir: str,
        db_manager,
        supported_extensions: List[str],
        image_extensions: List[str],
        video_extensions: List[str],
        photographic_prefixes: List[str] = None,
        exclude_hidden_dirs: bool = True,
        exclude_patterns: List[str] = None,
        max_workers: Optional[int] = None
    ):
        """
        Inizializza il processore di file con configurazione parallela.
        
        Args:
            source_dir: Directory sorgente da scansionare
            dest_dir: Directory di destinazione per l'organizzazione
            db_manager: Manager database per il tracking
            supported_extensions: Liste delle estensioni supportate
            image_extensions: Estensioni specifiche per immagini
            video_extensions: Estensioni specifiche per video
            photographic_prefixes: Prefissi per identificare file fotografici
            exclude_hidden_dirs: Se escludere directory nascoste
            exclude_patterns: Pattern aggiuntivi da escludere
            max_workers: Numero massimo di worker (auto-detect se None)
        """
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.db_manager = db_manager
        self.supported_extensions = [ext.lower() for ext in supported_extensions]
        self.image_extensions = [ext.lower() for ext in image_extensions]
        self.video_extensions = [ext.lower() for ext in video_extensions]
        self.photographic_prefixes = photographic_prefixes or []
        self.exclude_hidden_dirs = exclude_hidden_dirs
        self.exclude_patterns = exclude_patterns or []
        
        # Auto CPU detection con override manuale
        self.max_workers = max_workers or self._detect_optimal_workers()
        
        # Thread-safe database connection pool
        self._db_lock = threading.Lock()
        self._connections = {}
        self._connection_lock = threading.Lock()
        
        # Progress tracking
        self._progress_lock = threading.Lock()
        self._processed_count = 0
        self._error_count = 0
        self._duplicate_count = 0
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'duplicate_files': 0,
            'error_files': 0,
            'photos_organized': 0,
            'videos_organized': 0
        }
        
        logging.info(f"FileProcessor inizializzato con {self.max_workers} worker threads")

    def _detect_optimal_workers(self) -> int:
        """
        Rileva automaticamente il numero ottimale di worker thread.
        
        Returns:
            int: Numero ottimale di worker thread
        """
        cpu_count = os.cpu_count() or 4
        # Per I/O intensive tasks, usiamo più thread dei core disponibili
        optimal_workers = min(cpu_count * 2, 16)  # Max 16 thread per evitare overhead
        logging.info(f"CPU rilevati: {cpu_count}, worker ottimali: {optimal_workers}")
        return optimal_workers

    def _get_thread_connection(self):
        """
        Ottiene una connessione database thread-safe per il thread corrente.
        
        Returns:
            sqlite3.Connection: Connessione database thread-safe
        """
        thread_id = threading.get_ident()
        
        with self._connection_lock:
            if thread_id not in self._connections:
                self._connections[thread_id] = self.db_manager.create_db()
                logging.debug(f"Nuova connessione DB creata per thread {thread_id}")
            
            return self._connections[thread_id]

    def _cleanup_connections(self):
        """Chiude tutte le connessioni database thread-safe."""
        with self._connection_lock:
            for thread_id, conn in self._connections.items():
                try:
                    conn.close()
                    logging.debug(f"Connessione DB chiusa per thread {thread_id}")
                except Exception as e:
                    logging.warning(f"Errore chiusura connessione thread {thread_id}: {e}")
            self._connections.clear()

    def scan_directory(self):
        """
        Scansiona la directory sorgente e processa tutti i file supportati in parallelo.
        """
        logging.info(f"Inizio scansione directory: {self.source_dir}")
        
        # Prima fase: raccolta file con reporting dettagliato
        files_to_process = self._collect_files()
        
        if not files_to_process:
            logging.warning("Nessun file trovato da processare")
            print("[WARN] Nessun file trovato nella directory sorgente.")
            return
        
        self.stats['total_files'] = len(files_to_process)
        logging.info(f"Trovati {len(files_to_process)} file da processare")
        print(f"[INFO] Trovati {len(files_to_process)} file da processare con {self.max_workers} thread paralleli")
        
        # Seconda fase: processing parallelo
        self._process_files_parallel(files_to_process)
        
        # Cleanup finale
        self._cleanup_connections()
        self._print_final_stats()

    def _collect_files(self) -> List[Path]:
        """
        Raccoglie tutti i file validi da processare con reporting dettagliato.
        
        Returns:
            List[Path]: Lista dei file da processare
        """
        files_to_process = []
        total_items = 0
        skipped_dirs = 0
        skipped_files = 0
        unsupported_files = 0
        
        print("[SCAN] Scansione directory in corso...")
        
        try:
            # Raccoglie tutti gli item per conteggio accurato
            all_items = list(self.source_dir.rglob("*"))
            total_items = len(all_items)
            
            print(f"[SCAN] Trovati {total_items} item totali da analizzare...")
            
            for root_path in all_items:
                if self._should_skip_path(root_path):
                    if root_path.is_dir():
                        skipped_dirs += 1
                    else:
                        skipped_files += 1
                    continue
                
                if root_path.is_file():
                    if self._is_supported_file(root_path):
                        files_to_process.append(root_path)
                    else:
                        unsupported_files += 1
                        
        except Exception as e:
            logging.error(f"Errore durante la raccolta file: {e}")
            raise
        
        # Report dettagliato scansione
        print(f"[STATS] Risultati scansione:")
        print(f"   [FILES] Item totali scansionati: {total_items}")
        print(f"   [SUCCESS] File supportati trovati: {len(files_to_process)}")
        print(f"   [SKIP] Directory ignorate: {skipped_dirs}")
        print(f"   [SKIP] File ignorati (pattern): {skipped_files}")
        print(f"   [SKIP] File non supportati: {unsupported_files}")
        print(f"   [TARGET] File da processare: {len(files_to_process)}")
        print()
        
        return files_to_process

    def _process_files_parallel(self, files: List[Path]):
        """
        Processa i file in parallelo con progress tracking semplice.
        """
        logging.info(f"Inizio processing parallelo con {self.max_workers} workers")
        
        print(f"[START] Inizio processing {len(files)} file con {self.max_workers} worker paralleli...")
        
        completed = 0
        total = len(files)
        
        # ThreadPoolExecutor per worker management  
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Sottometti tutti i task
            future_to_file = {
                executor.submit(self._process_single_file, file_path): file_path
                for file_path in files
            }
            
            # Processa i risultati man mano che completano
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                
                try:
                    result = future.result()
                    
                    # Aggiorna statistiche
                    with self._progress_lock:
                        completed += 1
                        self._processed_count += 1
                        
                        if result['status'] == 'duplicate':
                            self._duplicate_count += 1
                            self.stats['duplicate_files'] += 1
                        elif result['status'] == 'copied':
                            if result['media_type'] == 'PHOTO':
                                self.stats['photos_organized'] += 1
                            else:
                                self.stats['videos_organized'] += 1
                            self.stats['processed_files'] += 1
                        elif result['status'] == 'error':
                            self._error_count += 1
                            self.stats['error_files'] += 1
                    
                    # Mostra progresso
                    if completed % 20 == 0 or completed == total or completed <= 10:
                        percent = (completed / total) * 100
                        print(f"[PROGRESS] {completed}/{total} ({percent:.1f}%) - Processati: {self.stats['processed_files']}, Duplicati: {self._duplicate_count}, Errori: {self._error_count}")
                        
                except Exception as e:
                    logging.error(f"Errore processing {file_path}: {e}")
                    
                    with self._progress_lock:
                        completed += 1
                        self._error_count += 1
                        self.stats['error_files'] += 1
                    
                    if completed % 20 == 0 or completed == total:
                        percent = (completed / total) * 100
                        print(f"[PROGRESS] {completed}/{total} ({percent:.1f}%) - Processati: {self.stats['processed_files']}, Duplicati: {self._duplicate_count}, Errori: {self._error_count}")
        
        print(f"[SUCCESS] Processing completato: {completed} file elaborati")

    def _process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Processa un singolo file in modo thread-safe.
        
        Args:
            file_path: Path del file da processare
            
        Returns:
            Dict[str, Any]: Risultato del processing
        """
        try:
            # Ottieni connessione thread-safe
            conn = self._get_thread_connection()
            
            # Estrai metadati
            media_type = "PHOTO" if file_path.suffix.lower() in self.image_extensions else "VIDEO"
            
            # Calcola hash per rilevamento duplicati
            _, file_hash = HashUtils.compute_hash(file_path)
            
            # Estrai data
            date_info = DateExtractor.extract_date(
                file_path,
                self.image_extensions,
                self.video_extensions
            )
            
            if date_info:
                year, month, _ = date_info
            else:
                year, month = "Unknown", "Unknown"
                logging.warning(f"Data non estratta per {file_path}")
            
            # Organizza il file
            result = self._organize_file(
                file_path, media_type, year, month, file_hash, conn
            )
            
            return {
                'status': result,
                'media_type': media_type,
                'file_path': str(file_path)
            }
            
        except Exception as e:
            logging.error(f"Errore processing file {file_path}: {e}")
            raise

    def _organize_file(
        self,
        file_path: Path,
        media_type: str,
        year: str,
        month: str,
        file_hash: str,
        conn
    ) -> str:
        """
        Organizza un singolo file nella struttura di destinazione.
        
        Args:
            file_path: Path del file originale
            media_type: Tipo di media (PHOTO/VIDEO)
            year: Anno estratto
            month: Mese estratto  
            file_hash: Hash del file per duplicati
            conn: Connessione database thread-safe
            
        Returns:
            str: Status dell'operazione (copied/duplicate/error)
        """
        try:
            # Determina directory di destinazione
            if year == "Unknown" or month == "Unknown":
                dest_dir = self.dest_dir / "ToReview" / media_type
            else:
                dest_dir = self.dest_dir / media_type / year / month
            
            # Crea directory se necessaria
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Controlla duplicati
            if self._is_duplicate(file_hash, conn):
                duplicate_dir = self.dest_dir / f"{media_type}_DUPLICATES"
                duplicate_dir.mkdir(parents=True, exist_ok=True)
                final_path = FileUtils.safe_copy(file_path, duplicate_dir, file_path.name)
                status = "duplicate"
            else:
                # Copia il file
                final_path = FileUtils.safe_copy(file_path, dest_dir, file_path.name)
                status = "copied"
            
            # Thread-safe database insert
            with self._db_lock:
                record = (
                    str(file_path),
                    file_hash,
                    year,
                    month,
                    media_type,
                    status,
                    str(final_path),
                    final_path.name
                )
                self.db_manager.insert_file(conn, record)
            
            return status
            
        except Exception as e:
            logging.error(f"Errore organizzazione file {file_path}: {e}")
            return "error"

    def _is_duplicate(self, file_hash: str, conn) -> bool:
        """
        Controlla se un file è un duplicato basandosi sull'hash.
        
        Args:
            file_hash: Hash del file da controllare
            conn: Connessione database
            
        Returns:
            bool: True se è un duplicato
        """
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE hash = ?", (file_hash,))
        count = cursor.fetchone()[0]
        return count > 0

    def _should_skip_path(self, path: Path) -> bool:
        """
        Determina se un path deve essere saltato.
        
        Args:
            path: Path da verificare
            
        Returns:
            bool: True se deve essere saltato
        """
        # Salta directory nascoste se configurato
        if self.exclude_hidden_dirs and any(
            part.startswith('.') for part in path.parts
        ):
            return True
        
        # Salta pattern specificati
        for pattern in self.exclude_patterns:
            if pattern in str(path):
                return True
        
        return False

    def _is_supported_file(self, file_path: Path) -> bool:
        """
        Verifica se un file è supportato.
        
        Args:
            file_path: Path del file
            
        Returns:
            bool: True se supportato
        """
        return file_path.suffix.lower() in self.supported_extensions

    def _print_final_stats(self):
        """Stampa statistiche finali dell'elaborazione."""
        logging.info("Statistiche finali:")
        logging.info(f"   File totali trovati: {self.stats['total_files']}")
        logging.info(f"   File processati: {self.stats['processed_files']}")
        logging.info(f"   Foto organizzate: {self.stats['photos_organized']}")
        logging.info(f"   Video organizzati: {self.stats['videos_organized']}")
        logging.info(f"   File duplicati: {self.stats['duplicate_files']}")
        logging.info(f"   Errori: {self.stats['error_files']}")
        
        print("\n[STATS] Riepilogo Elaborazione:")
        print(f"[SUCCESS] File processati: {self.stats['processed_files']}")
        print(f"[PHOTO] Foto organizzate: {self.stats['photos_organized']}")
        print(f"[VIDEO] Video organizzati: {self.stats['videos_organized']}")
        print(f"[DUP] Duplicati gestiti: {self.stats['duplicate_files']}")
        if self.stats['error_files'] > 0:
            print(f"[ERROR] Errori: {self.stats['error_files']}")
        print(f"[THREADS] Elaborazione parallela completata con {self.max_workers} worker")