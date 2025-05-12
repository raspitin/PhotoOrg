import hashlib
import logging
import shutil
from pathlib import Path
from tqdm import tqdm
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .date_extractor import DateExtractor
from .file_utils import FileUtils
from .hash_utils import HashUtils


class FileProcessor:
    def __init__(self, source_dir, dest_dir, db_manager, supported_extensions, 
                 image_extensions, video_extensions, photographic_prefixes,
                 exclude_hidden_dirs=True, exclude_patterns=None):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.db_manager = db_manager
        self.supported_extensions = supported_extensions
        self.image_extensions = image_extensions
        self.video_extensions = video_extensions
        self.photographic_prefixes = photographic_prefixes
        self.exclude_hidden_dirs = exclude_hidden_dirs
        self.exclude_patterns = exclude_patterns or []
        self.conn = self.db_manager.create_db()
        
        # Contatori per il summary
        self.stats = {
            'migrated': 0,
            'duplicates': 0,
            'to_review': 0,
            'unsupported': 0,
            'total_processed': 0
        }
        self.start_time = None

    def scan_directory(self):
        """Scansiona ricorsivamente la directory di origine e processa i file."""
        logging.info(f"Inizio scansione della directory: {self.source_dir}")
        self.start_time = time.time()  # Inizia il timer
        
        # Debug: conta tutti i file
        all_files = list(self._get_all_files())
        supported_files = list(self._get_supported_files())
        unsupported_files = list(self._get_unsupported_files())
        
        print(f"Debug - File totali trovati: {len(all_files)}")
        print(f"Debug - File supportati: {len(supported_files)}")
        print(f"Debug - File non supportati: {len(unsupported_files)}")
        print(f"Debug - File esclusi: {len(all_files) - len(supported_files) - len(unsupported_files)}")
        
        self.stats['unsupported'] = len(unsupported_files)
        
        if len(supported_files) == 0:
            print("Nessun file da elaborare trovato.")
            logging.info("Nessun file con estensioni supportate trovato.")
            return
        
        print(f"\nTrovati {len(supported_files)} file da elaborare")
        logging.info(f"Trovati {len(supported_files)} file da elaborare")
        
        # Configurazione tqdm con parametri ottimizzati
        with tqdm(total=len(supported_files), 
                 desc="Elaborazione file", 
                 unit="file",
                 file=sys.stdout,  # Output diretto su stdout
                 dynamic_ncols=True,  # Adatta la larghezza dinamicamente
                 miniters=1,  # Aggiorna ad ogni iterazione
                 smoothing=0.1,  # Smoothing pi� reattivo
                 leave=True) as pbar:
            
            # Processa i file uno alla volta
            for file_path in supported_files:
                try:
                    # Aggiorna descrizione con il file corrente
                    pbar.set_description(f"Elaborando: {file_path.name[:50]}...")
                    
                    # Processa il file
                    self._process_file(file_path)
                    
                    # Aggiorna la progress bar immediatamente
                    pbar.update(1)
                    pbar.refresh()  # Forza il refresh della visualizzazione
                    
                except Exception as e:
                    logging.error(f"Errore durante l'elaborazione di {file_path}: {e}")
                    tqdm.write(f"??  Errore: {file_path.name} - {str(e)}")
                    pbar.update(1)
        
        print("\nElaborazione completata!")
        logging.info("Scansione completata.")
        
        # Mostra il summary finale
        self._print_summary()

    def _get_all_files(self):
        """Generatore che restituisce tutti i file (per debug)."""
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file():
                yield file_path
                
    def _get_supported_files(self):
        """Generatore che restituisce i file con estensioni supportate."""
        for file_path in self.source_dir.rglob("*"):
            # Salta i file nelle directory nascoste (che iniziano con .)
            if self._is_hidden_path(file_path):
                continue
                
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                yield file_path

    def _get_unsupported_files(self):
        """Generatore che restituisce i file con estensioni non supportate."""
        for file_path in self.source_dir.rglob("*"):
            # Salta i file nelle directory nascoste (che iniziano con .)
            if self._is_hidden_path(file_path):
                continue
                
            if file_path.is_file() and file_path.suffix.lower() not in self.supported_extensions:
                yield file_path
    
    def _is_hidden_path(self, path):
        """Verifica se il path contiene directory nascoste o pattern da escludere"""
        # Controlla se l'esclusione delle directory nascoste � abilitata
        if self.exclude_hidden_dirs:
            # Controlla se qualsiasi parte del percorso (tranne la root) inizia con '.'
            for part in path.parts:
                if part.startswith('.') and part != '.':
                    return True
        
        # Controlla pattern di esclusione aggiuntivi
        for pattern in self.exclude_patterns:
            if pattern in str(path):
                return True
                
        return False

    def _print_summary(self):
        """Stampa il riepilogo finale dell'elaborazione."""
        end_time = time.time()
        total_time = end_time - self.start_time
        
        # Calcola minuti e secondi
        minutes = int(total_time // 60)
        seconds = total_time % 60
        
        print("\nSummary:")
        print(f"  Migrated files: {self.stats['migrated']}")
        print(f"  Duplicate files: {self.stats['duplicates']}")
        print(f"  Files to review: {self.stats['to_review']}")
        print(f"  Unsupported files: {self.stats['unsupported']}")
        print(f"  Total files processed: {self.stats['total_processed']}")
        print(f"  Total time: {minutes} min {seconds:.2f} sec")
        
        # Log anche nel file di log
        logging.info(f"Summary - Migrated: {self.stats['migrated']}, Duplicates: {self.stats['duplicates']}, "
                    f"To Review: {self.stats['to_review']}, Unsupported: {self.stats['unsupported']}, "
                    f"Total Processed: {self.stats['total_processed']}, Time: {minutes}m {seconds:.2f}s")

    def _process_file(self, file_path):
        """Processa un singolo file."""
        logging.info(f"Elaborazione file: {file_path}")
        
        # Calcola hash del file
        _, file_hash = HashUtils.compute_hash(file_path)
        
        # Controlla duplicati nel database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE hash = ?", (file_hash,))
        existing = cursor.fetchone()
        
        if existing:
            # File duplicato trovato
            self._handle_duplicate(file_path, file_hash)
        else:
            # File nuovo
            self._handle_new_file(file_path, file_hash)

    def _handle_duplicate(self, file_path, file_hash):
        """Gestisce un file duplicato."""
        media_type = self._get_media_type(file_path)
        duplicate_dir = self.dest_dir / f"{media_type}_DUPLICATES"
        duplicate_dir.mkdir(parents=True, exist_ok=True)
        
        # Copia il file nella cartella duplicati
        dest_file = FileUtils.safe_copy(file_path, duplicate_dir, file_path.name)
        
        # Registra nel database
        record = (
            str(file_path),
            file_hash,
            None,  # year
            None,  # month
            media_type,
            "duplicate",
            str(duplicate_dir),
            dest_file.name
        )
        self.db_manager.insert_file(self.conn, record)
        
        # Aggiorna statistiche
        self.stats['duplicates'] += 1
        self.stats['total_processed'] += 1
        
        logging.info(f"Duplicato gestito: {file_path} -> {dest_file}")

    def _handle_new_file(self, file_path, file_hash):
        """Gestisce un nuovo file."""
        # Estrai data
        date_info = DateExtractor.extract_date(
            file_path, 
            self.image_extensions, 
            self.video_extensions
        )
        
        if date_info:
            year, month, _ = date_info
            media_type = self._get_media_type(file_path)
            
            # Crea directory di destinazione
            dest_dir = self.dest_dir / media_type / year / month
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Copia il file
            dest_file = FileUtils.safe_copy(file_path, dest_dir, file_path.name)
            
            # Registra nel database
            record = (
                str(file_path),
                file_hash,
                year,
                month,
                media_type,
                "processed",
                str(dest_dir),
                dest_file.name
            )
            self.db_manager.insert_file(self.conn, record)
            
            # Aggiorna statistiche
            self.stats['migrated'] += 1
            self.stats['total_processed'] += 1
            
            logging.info(f"File processato: {file_path} -> {dest_file}")
        else:
            # Se non si riesce a estrarre la data, sposta in ToReview
            self._handle_no_date_file(file_path, file_hash)

    def _handle_no_date_file(self, file_path, file_hash):
        """Gestisce file senza data estraibile."""
        review_dir = self.dest_dir / "ToReview"
        review_dir.mkdir(parents=True, exist_ok=True)
        
        dest_file = FileUtils.safe_copy(file_path, review_dir, file_path.name)
        
        record = (
            str(file_path),
            file_hash,
            None,
            None,
            self._get_media_type(file_path),
            "to_review",
            str(review_dir),
            dest_file.name
        )
        self.db_manager.insert_file(self.conn, record)
        
        # Aggiorna statistiche
        self.stats['to_review'] += 1
        self.stats['total_processed'] += 1
        
        logging.info(f"File senza data: {file_path} -> {dest_file}")

    def _get_media_type(self, file_path):
        """Determina il tipo di media in base all'estensione."""
        suffix = file_path.suffix.lower()
        if suffix in self.image_extensions:
            return "PHOTO"
        elif suffix in self.video_extensions:
            return "VIDEO"
        return "UNKNOWN"