#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
                 exclude_hidden_dirs=True, exclude_patterns=None, dry_run=False):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.db_manager = db_manager
        self.supported_extensions = supported_extensions
        self.image_extensions = image_extensions
        self.video_extensions = video_extensions
        self.photographic_prefixes = photographic_prefixes
        self.exclude_hidden_dirs = exclude_hidden_dirs
        self.exclude_patterns = exclude_patterns or []
        self.dry_run = dry_run
        
        # Solo crea connessione DB se NON e' dry-run
        if not self.dry_run:
            self.conn = self.db_manager.create_db()
        else:
            self.conn = None
            # Per dry-run, simula il database con dizionario in memoria
            self.mock_db = {}
        
        # Contatori per il summary
        self.stats = {
            'migrated': 0,
            'duplicates': 0,
            'to_review': 0,
            'unsupported': 0,
            'total_processed': 0,
            'total_size': 0,
            'space_needed': 0
        }
        self.start_time = None
        
        # Per dry-run: collezione di operazioni pianificate
        self.planned_operations = []

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
        
        # Processa anche i file non supportati per registrarli
        if not self.dry_run:
            print(f"\nRegistrazione file non supportati...")
            for file_path in unsupported_files:
                self._handle_unsupported_file(file_path)
        else:
            print(f"\nAnalisi file non supportati...")
            for file_path in unsupported_files:
                self._analyze_unsupported_file(file_path)
        
        if len(supported_files) == 0:
            print("Nessun file supportato da elaborare.")
            logging.info("Nessun file con estensioni supportate trovato.")
            self._print_summary()
            return
        
        print(f"\nTrovati {len(supported_files)} file da elaborare")
        logging.info(f"Trovati {len(supported_files)} file da elaborare")
        
        # Progress bar configurata per dry-run o normale
        action = "Analizzando" if self.dry_run else "Elaborazione"
        with tqdm(total=len(supported_files), 
                 desc=action, 
                 unit="file",
                 dynamic_ncols=True,
                 leave=True,
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
            
            # Processa i file uno alla volta
            for file_path in supported_files:
                try:
                    # Aggiorna solo il nome del file corrente (troncato)
                    filename = file_path.name
                    if len(filename) > 30:
                        filename = filename[:27] + "..."
                    pbar.set_description(f"-> {filename}")
                    
                    # Processa il file (dry-run o normale)
                    if self.dry_run:
                        self._analyze_file(file_path)
                    else:
                        self._process_file_quiet(file_path)
                    
                    # Aggiorna progress bar
                    pbar.update(1)
                    
                except Exception as e:
                    # Solo errori critici visibili
                    tqdm.write(f"Errore {file_path.name}: {str(e)}")
                    logging.error(f"Errore durante l'elaborazione di {file_path}: {e}")
                    pbar.update(1)
        
        if self.dry_run:
            print("\n=== ANTEPRIMA OPERAZIONI COMPLETATA ===")
            self._print_dry_run_preview()
        else:
            print("\nElaborazione completata!")
        
        logging.info("Scansione completata.")
        
        # Mostra il summary finale
        self._print_summary()

    def _analyze_file(self, file_path):
        """Analizza un file in modalita' dry-run senza modifiche."""
        logging.info(f"Analisi file: {file_path}")
        
        # Calcola size del file
        try:
            file_size = file_path.stat().st_size
            self.stats['total_size'] += file_size
        except OSError:
            file_size = 0
        
        # Calcola hash del file (necessario per check duplicati)
        _, file_hash = HashUtils.compute_hash(file_path)
        
        # Simula controllo duplicati
        if file_hash in self.mock_db:
            # File duplicato trovato
            self._analyze_duplicate(file_path, file_hash, file_size)
        else:
            # File nuovo
            self._analyze_new_file(file_path, file_hash, file_size)
            # Aggiungi al mock database
            self.mock_db[file_hash] = str(file_path)

    def _analyze_new_file(self, file_path, file_hash, file_size):
        """Analizza un nuovo file in modalita' dry-run."""
        # Estrai data
        date_info = DateExtractor.extract_date(
            file_path, 
            self.image_extensions, 
            self.video_extensions
        )
        
        if date_info:
            year, month, _ = date_info
            media_type = self._get_media_type(file_path)
            
            # Calcola percorso di destinazione
            dest_dir = self.dest_dir / media_type / year / month
            dest_file_path = dest_dir / file_path.name
            
            # Pianifica operazione
            operation = {
                'type': 'migrate',
                'source': str(file_path),
                'destination': str(dest_file_path),
                'media_type': media_type,
                'year': year,
                'month': month,
                'size': file_size
            }
            self.planned_operations.append(operation)
            
            # Aggiorna statistiche
            self.stats['migrated'] += 1
            self.stats['total_processed'] += 1
            self.stats['space_needed'] += file_size
            
            logging.info(f"Pianificato: {file_path} -> {dest_file_path}")
        else:
            # File senza data estraibile
            self._analyze_no_date_file(file_path, file_hash, file_size)

    def _analyze_duplicate(self, file_path, file_hash, file_size):
        """Analizza un file duplicato in modalita' dry-run."""
        media_type = self._get_media_type(file_path)
        duplicate_dir = self.dest_dir / f"{media_type}_DUPLICATES"
        dest_file_path = duplicate_dir / file_path.name
        
        # Pianifica operazione
        operation = {
            'type': 'duplicate',
            'source': str(file_path),
            'destination': str(dest_file_path),
            'media_type': media_type,
            'size': file_size,
            'original': self.mock_db[file_hash]
        }
        self.planned_operations.append(operation)
        
        # Aggiorna statistiche
        self.stats['duplicates'] += 1
        self.stats['total_processed'] += 1
        # I duplicati non occupano spazio aggiuntivo
        
        logging.info(f"Duplicato identificato: {file_path} (originale: {self.mock_db[file_hash]})")

    def _analyze_no_date_file(self, file_path, file_hash, file_size):
        """Analizza file senza data estraibile in modalita' dry-run."""
        review_dir = self.dest_dir / "ToReview"
        dest_file_path = review_dir / file_path.name
        
        # Pianifica operazione
        operation = {
            'type': 'review',
            'source': str(file_path),
            'destination': str(dest_file_path),
            'media_type': self._get_media_type(file_path),
            'size': file_size
        }
        self.planned_operations.append(operation)
        
        # Aggiorna statistiche
        self.stats['to_review'] += 1
        self.stats['total_processed'] += 1
        self.stats['space_needed'] += file_size
        
        logging.info(f"Da rivedere: {file_path} -> {dest_file_path}")

    def _analyze_unsupported_file(self, file_path):
        """Analizza un file non supportato in modalita' dry-run."""
        try:
            file_size = file_path.stat().st_size
            self.stats['total_size'] += file_size
        except OSError:
            pass
        
        logging.info(f"File non supportato identificato: {file_path}")

    def _print_dry_run_preview(self):
        """Stampa l'anteprima dettagliata delle operazioni pianificate."""
        print("\n" + "="*60)
        print("ANTEPRIMA OPERAZIONI (DRY-RUN)")
        print("="*60)
        
        if not self.planned_operations:
            print("Nessuna operazione pianificata.")
            return
        
        # Raggruppa operazioni per tipo
        migrate_ops = [op for op in self.planned_operations if op['type'] == 'migrate']
        duplicate_ops = [op for op in self.planned_operations if op['type'] == 'duplicate']
        review_ops = [op for op in self.planned_operations if op['type'] == 'review']
        
        # Mostra operazioni di migrazione (prime 10)
        if migrate_ops:
            print(f"\nFile da migrare ({len(migrate_ops)}):")
            for i, op in enumerate(migrate_ops[:10]):
                size_mb = op['size'] / (1024*1024)
                print(f"  {op['source']}")
                print(f"    -> {op['destination']} ({size_mb:.1f} MB)")
            if len(migrate_ops) > 10:
                print(f"    ... e altri {len(migrate_ops)-10} file")
        
        # Mostra duplicati (prime 5)
        if duplicate_ops:
            print(f"\nDuplicati identificati ({len(duplicate_ops)}):")
            for i, op in enumerate(duplicate_ops[:5]):
                size_mb = op['size'] / (1024*1024)
                print(f"  {op['source']} ({size_mb:.1f} MB)")
                print(f"    -> DUPLICATO di: {op['original']}")
            if len(duplicate_ops) > 5:
                print(f"    ... e altri {len(duplicate_ops)-5} duplicati")
        
        # Mostra file da rivedere (prime 5)
        if review_ops:
            print(f"\nFile da rivedere ({len(review_ops)}):")
            for i, op in enumerate(review_ops[:5]):
                size_mb = op['size'] / (1024*1024)
                print(f"  {op['source']} ({size_mb:.1f} MB)")
                print(f"    -> {op['destination']} (data non estraibile)")
            if len(review_ops) > 5:
                print(f"    ... e altri {len(review_ops)-5} file")
        
        # Statistiche spazio
        total_mb = self.stats['total_size'] / (1024*1024)
        needed_mb = self.stats['space_needed'] / (1024*1024)
        saved_mb = total_mb - needed_mb
        
        print(f"\nSpazio:")
        print(f"  Totale file analizzati: {total_mb:.1f} MB")
        print(f"  Spazio necessario: {needed_mb:.1f} MB")
        print(f"  Spazio risparmiato (duplicati): {saved_mb:.1f} MB")

    def _process_file_quiet(self, file_path):
        """Processa un singolo file senza output su console."""
        # Log solo su file, NON su console
        logging.info(f"Elaborazione file: {file_path}")
        
        # Calcola hash del file
        _, file_hash = HashUtils.compute_hash(file_path)
        
        # Controlla duplicati nel database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE hash = ?", (file_hash,))
        existing = cursor.fetchone()
        
        if existing:
            # File duplicato trovato
            self._handle_duplicate_quiet(file_path, file_hash)
        else:
            # File nuovo
            self._handle_new_file_quiet(file_path, file_hash)

    def _handle_new_file_quiet(self, file_path, file_hash):
        """Gestisce un nuovo file senza output su console."""
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
            
            # Log solo su file
            logging.info(f"File processato: {file_path} -> {dest_file}")
        else:
            # Se non si riesce a estrarre la data, sposta in ToReview
            self._handle_no_date_file_quiet(file_path, file_hash)

    def _handle_duplicate_quiet(self, file_path, file_hash):
        """Gestisce un file duplicato senza output su console."""
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
        
        # Log solo su file
        logging.info(f"Duplicato gestito: {file_path} -> {dest_file}")

    def _handle_no_date_file_quiet(self, file_path, file_hash):
        """Gestisce file senza data estraibile senza output su console."""
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
        
        # Log solo su file
        logging.info(f"File senza data: {file_path} -> {dest_file}")

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
        # Controlla se l'esclusione delle directory nascoste e' abilitata
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

    def _handle_unsupported_file(self, file_path):
        """Gestisce un file con estensione non supportata."""
        # Calcola hash del file
        _, file_hash = HashUtils.compute_hash(file_path)
        
        # Registra nel database
        record = (
            str(file_path),
            file_hash,
            None,  # year
            None,  # month
            "UNSUPPORTED",  # media_type
            "unsupported",  # status
            None,  # destination_path
            None   # final_name
        )
        self.db_manager.insert_file(self.conn, record)
        
        logging.info(f"File non supportato registrato: {file_path}")

    def _print_summary(self):
        """Stampa il riepilogo finale dell'elaborazione."""
        end_time = time.time()
        total_time = end_time - self.start_time
        
        # Calcola minuti e secondi
        minutes = int(total_time // 60)
        seconds = total_time % 60
        
        print(f"\n{'='*50}")
        if self.dry_run:
            print("RIEPILOGO ANTEPRIMA (DRY-RUN)")
        else:
            print("RIEPILOGO OPERAZIONI")
        print("="*50)
        
        print(f"  File migrati: {self.stats['migrated']}")
        print(f"  File duplicati: {self.stats['duplicates']}")
        print(f"  File da rivedere: {self.stats['to_review']}")
        print(f"  File non supportati: {self.stats['unsupported']}")
        print(f"  Totale file processati: {self.stats['total_processed']}")
        
        if self.dry_run and 'total_size' in self.stats:
            total_gb = self.stats['total_size'] / (1024*1024*1024)
            needed_gb = self.stats['space_needed'] / (1024*1024*1024)
            print(f"  Spazio totale: {total_gb:.2f} GB")
            print(f"  Spazio necessario: {needed_gb:.2f} GB")
        
        print(f"  Tempo totale: {minutes} min {seconds:.2f} sec")
        
        if self.dry_run:
            print("\nUsa senza --dry-run per eseguire le operazioni realmente")
        
        # Log anche nel file di log
        mode = "DRY-RUN" if self.dry_run else "EXEC"
        logging.info(f"Summary [{mode}] - Migrated: {self.stats['migrated']}, Duplicates: {self.stats['duplicates']}, "
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