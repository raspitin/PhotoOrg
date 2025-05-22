#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from config.config_loader import ConfigLoader
from loggingSetup.logging_setup import LoggingSetup
from database.database_manager import DatabaseManager
from processing.file_processor import FileProcessor
from pathlib import Path
import sys
import logging
import shutil
import argparse
from typing import Dict, Any, Optional


def setup_minimal_logging():
    """
    Configura logging minimo per tracciare eventi prima della configurazione completa.
    """
    logging.basicConfig(
        level=logging.ERROR,
        format="%(levelname)s: %(message)s"
    )


def create_argument_parser():
    """
    Crea e configura il parser degli argomenti della linea di comando.
    
    Returns:
        argparse.ArgumentParser: Parser configurato
    """
    parser = argparse.ArgumentParser(
        prog='PhotoOrg',
        description='Photo and Video Organizer - Organize your media files by date with duplicate detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                                    # Normal execution
  %(prog)s --dry-run                          # Preview operations without changes
  %(prog)s --reset                            # Reset database and directories
  %(prog)s --source /mnt/photos --dest /backup --non-interactive
  %(prog)s --config custom_config.yaml --verbose
  %(prog)s --reset --force --quiet           # Force reset without confirmation

For more information, visit: https://github.com/raspitin/PhotoOrg
        ''')
    
    # Configuration options
    config_group = parser.add_argument_group('Configuration')
    config_group.add_argument(
        '--config', '-c',
        metavar='PATH',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    config_group.add_argument(
        '--source', '-s',
        metavar='PATH',
        help='Override source directory from config'
    )
    config_group.add_argument(
        '--dest', '-d',
        metavar='PATH',
        help='Override destination directory from config'
    )
    
    # Operation modes
    mode_group = parser.add_argument_group('Operation Modes')
    mode_group.add_argument(
        '--dry-run', '--preview',
        action='store_true',
        help='Preview operations without making any changes'
    )
    mode_group.add_argument(
        '--reset',
        action='store_true',
        help='Reset database, logs, and destination directories'
    )
    mode_group.add_argument(
        '--non-interactive', '--batch',
        action='store_true',
        help='Run without user prompts (for automation)'
    )
    
    # Behavior options
    behavior_group = parser.add_argument_group('Behavior')
    behavior_group.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmations (use with --reset or --non-interactive)'
    )
    behavior_group.add_argument(
        '--auto-create-dirs',
        action='store_true',
        help='Automatically create missing directories'
    )
    
    # Output control
    output_group = parser.add_argument_group('Output Control')
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable detailed output'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimize output (errors only)'
    )
    output_group.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    # Advanced options (for future use)
    advanced_group = parser.add_argument_group('Advanced Options')
    advanced_group.add_argument(
        '--parallel', '-j',
        type=int,
        metavar='N',
        default=1,
        help='Number of parallel workers (default: 1, future feature)'
    )
    advanced_group.add_argument(
        '--skip-duplicates',
        action='store_true',
        help='Skip duplicate detection (faster, future feature)'
    )
    
    return parser


def validate_config(config: Dict[str, Any], args) -> None:
    """
    Valida che la configurazione contenga tutte le chiavi richieste.
    
    Args:
        config: Dizionario di configurazione da validare
        args: Argomenti della linea di comando
        
    Raises:
        ValueError: Se mancano chiavi obbligatorie o i tipi non sono corretti
    """
    required_keys = [
        "source", "destination", "database", "log",
        "supported_extensions", "image_extensions", "video_extensions"
    ]
    
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Chiavi di configurazione mancanti: {', '.join(missing_keys)}")
    
    # Verifica che i path esistano o siano creabili
    source_path = Path(config["source"])
    if not source_path.exists():
        raise ValueError(f"Directory sorgente non trovata: {source_path}")
    
    if not source_path.is_dir():
        raise ValueError(f"Il percorso sorgente non e' una directory: {source_path}")
    
    # Verifica che la directory sorgente sia accessibile in lettura
    try:
        # Tenta di listare il contenuto per verificare i permessi di lettura
        list(source_path.iterdir())
    except PermissionError:
        raise ValueError(f"Permesso negato per accedere alla directory sorgente: {source_path}")
    except OSError as e:
        raise ValueError(f"Errore di accesso alla directory sorgente '{source_path}': {e}")
    
    # Verifica directory di destinazione se esiste
    dest_path = Path(config["destination"])
    if dest_path.exists():
        if not dest_path.is_dir():
            raise ValueError(f"Il percorso di destinazione esiste ma non e' una directory: {dest_path}")
        
        # Verifica permessi di scrittura sulla directory di destinazione
        try:
            # Crea un file temporaneo per testare i permessi di scrittura
            test_file = dest_path / ".test_write_permission"
            test_file.touch()
            test_file.unlink()  # Rimuovi subito
        except PermissionError:
            raise ValueError(f"Permesso negato per scrivere nella directory di destinazione: {dest_path}")
        except OSError as e:
            raise ValueError(f"Errore di accesso alla directory di destinazione '{dest_path}': {e}")
    
    # Verifica che le estensioni siano liste
    for ext_key in ["supported_extensions", "image_extensions", "video_extensions"]:
        if not isinstance(config[ext_key], list):
            raise ValueError(f"'{ext_key}' deve essere una lista")
        if not config[ext_key]:  # Lista vuota
            raise ValueError(f"'{ext_key}' non puo' essere una lista vuota")
    
    # Verifica che photographic_prefixes sia una lista (se presente)
    if "photographic_prefixes" in config and not isinstance(config["photographic_prefixes"], list):
        raise ValueError("'photographic_prefixes' deve essere una lista")
    
    # Verifica che exclude_patterns sia una lista (se presente)
    if "exclude_patterns" in config and not isinstance(config["exclude_patterns"], list):
        raise ValueError("'exclude_patterns' deve essere una lista")
    
    if not args.quiet:
        print("Configurazione validata con successo")


def create_destination_directory(dest_dir: Path, args) -> bool:
    """
    Gestisce la creazione della directory di destinazione con gestione errori robusta.
    
    Args:
        dest_dir: Path della directory di destinazione
        args: Argomenti della linea di comando
        
    Returns:
        bool: True se la directory esiste o e' stata creata, False altrimenti
    """
    if dest_dir.exists():
        if not dest_dir.is_dir():
            if not args.quiet:
                print(f"Errore: '{dest_dir}' esiste ma non e' una directory.")
            return False
        if not args.quiet:
            print(f"Directory di destinazione gia' esistente: {dest_dir}")
        return True
    
    # Modalita' non-interattiva o auto-create
    if args.non_interactive or args.auto_create_dirs or args.force:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if not args.quiet:
                print(f"Directory '{dest_dir}' creata automaticamente.")
            return True
        except Exception as e:
            if not args.quiet:
                print(f"Errore durante la creazione automatica della directory '{dest_dir}': {e}")
            return False
    
    # Modalita' interattiva
    try:
        response = input(f"La directory di destinazione '{dest_dir}' non esiste. Vuoi crearla? [s/N]: ").strip().lower()
        if response == "s":
            dest_dir.mkdir(parents=True, exist_ok=True)
            if not args.quiet:
                print(f"Directory '{dest_dir}' creata con successo.")
            return True
        else:
            if not args.quiet:
                print("Operazione annullata. Nessuna directory creata.")
            return False
            
    except PermissionError as e:
        if not args.quiet:
            print(f"Errore: Permesso negato per creare la directory '{dest_dir}': {e}")
        return False
    except OSError as e:
        if not args.quiet:
            print(f"Errore del sistema durante la creazione della directory '{dest_dir}': {e}")
        return False
    except KeyboardInterrupt:
        if not args.quiet:
            print("\nOperazione interrotta dall'utente.")
        return False
    except Exception as e:
        if not args.quiet:
            print(f"Errore imprevisto durante la creazione della directory '{dest_dir}': {e}")
        return False


def reset_environment(database_path: str, log_path: str, dest_dir: str, args) -> None:
    """
    Ripristina l'ambiente eliminando il database, i log e le directory di destinazione.
    Con gestione completa delle eccezioni e conferma utente.
    
    Args:
        database_path: Percorso del file database
        log_path: Percorso del file di log
        dest_dir: Percorso della directory di destinazione
        args: Argomenti della linea di comando
    """
    if not args.quiet:
        print("ATTENZIONE: Procedura di Reset dell'Ambiente")
        print("Questa operazione eliminera':")
        print(f"  - Database: {database_path}")
        print(f"  - File di log: {log_path}")
        print(f"  - Directory: {dest_dir}/PHOTO")
        print(f"  - Directory: {dest_dir}/VIDEO") 
        print(f"  - Directory: {dest_dir}/PHOTO_DUPLICATES")
        print(f"  - Directory: {dest_dir}/VIDEO_DUPLICATES")
        print(f"  - Directory: {dest_dir}/ToReview")
        print()
    
    # Controllo conferma
    if not args.force and not args.non_interactive:
        try:
            response = input("Sei sicuro di voler procedere? [s/N]: ").strip().lower()
            if response != "s":
                if not args.quiet:
                    print("Reset annullato.")
                return
        except KeyboardInterrupt:
            if not args.quiet:
                print("\nReset interrotto.")
            return
    
    if not args.quiet:
        print("Inizio procedura di reset dell'ambiente")
    
    reset_success = True
    
    # Elimina il database
    db_path = Path(database_path)
    if db_path.exists():
        try:
            db_path.unlink()
            if not args.quiet:
                print(f"Database eliminato: {db_path}")
        except PermissionError as e:
            if not args.quiet:
                print(f"Errore: Permesso negato per eliminare il database '{db_path}': {e}")
            reset_success = False
        except OSError as e:
            if not args.quiet:
                print(f"Errore del sistema eliminando il database '{db_path}': {e}")
            reset_success = False
        except Exception as e:
            if not args.quiet:
                print(f"Errore imprevisto eliminando il database '{db_path}': {e}")
            reset_success = False
    else:
        if args.verbose:
            print(f"Database non trovato (gia' eliminato?): {db_path}")

    # Elimina il file di log
    log_file = Path(log_path)
    if log_file.exists():
        try:
            log_file.unlink()
            if not args.quiet:
                print(f"File di log eliminato: {log_file}")
        except PermissionError as e:
            if not args.quiet:
                print(f"Errore: Permesso negato per eliminare il log '{log_file}': {e}")
            reset_success = False
        except OSError as e:
            if not args.quiet:
                print(f"Errore del sistema eliminando il log '{log_file}': {e}")
            reset_success = False
        except Exception as e:
            if not args.quiet:
                print(f"Errore imprevisto eliminando il log '{log_file}': {e}")
            reset_success = False
    else:
        if args.verbose:
            print(f"File di log non trovato (gia' eliminato?): {log_file}")

    # Elimina le directory di destinazione
    dest_path = Path(dest_dir)
    folders_to_remove = ["PHOTO", "VIDEO", "PHOTO_DUPLICATES", "VIDEO_DUPLICATES", "ToReview"]
    
    for folder in folders_to_remove:
        folder_path = dest_path / folder
        if folder_path.exists():
            try:
                shutil.rmtree(folder_path)
                if not args.quiet:
                    print(f"Cartella eliminata: {folder_path}")
            except PermissionError as e:
                if not args.quiet:
                    print(f"Errore: Permesso negato per eliminare '{folder_path}': {e}")
                reset_success = False
            except OSError as e:
                if not args.quiet:
                    print(f"Errore del sistema eliminando '{folder_path}': {e}")
                reset_success = False
            except Exception as e:
                if not args.quiet:
                    print(f"Errore imprevisto eliminando '{folder_path}': {e}")
                reset_success = False
        else:
            if args.verbose:
                print(f"Cartella non trovata (gia' eliminata?): {folder_path}")
    
    if not args.quiet:
        if reset_success:
            print("Reset dell'ambiente completato con successo")
        else:
            print("Reset dell'ambiente completato con alcuni errori. Controlla i messaggi sopra.")


def initialize_logging(config: Dict[str, Any], args) -> None:
    """
    Inizializza il sistema di logging usando la configurazione fornita.
    
    Args:
        config: Dizionario di configurazione
        args: Argomenti della linea di comando
    """
    try:
        LoggingSetup.setup_logging(config["log"])
        if args.verbose:
            print("Sistema di logging inizializzato")
    except Exception as e:
        if not args.quiet:
            print(f"Errore durante l'inizializzazione del logging: {e}")
            print("Continuo con il logging di base")


def initialize_database(config: Dict[str, Any], args) -> Optional[DatabaseManager]:
    """
    Inizializza il database manager con gestione errori.
    
    Args:
        config: Dizionario di configurazione
        args: Argomenti della linea di comando
        
    Returns:
        DatabaseManager istanziato o None in caso di errore
    """
    try:
        db_manager = DatabaseManager(config["database"])
        if args.verbose:
            print("Database manager inizializzato")
        return db_manager
    except Exception as e:
        if not args.quiet:
            print(f"Errore durante l'inizializzazione del database: {e}")
        return None


def initialize_file_processor(config: Dict[str, Any], db_manager: DatabaseManager, args) -> Optional[FileProcessor]:
    """
    Inizializza il processore dei file con gestione errori.
    
    Args:
        config: Dizionario di configurazione
        db_manager: Istanza del database manager
        args: Argomenti della linea di comando
        
    Returns:
        FileProcessor istanziato o None in caso di errore
    """
    try:
        file_processor = FileProcessor(
            source_dir=config["source"],
            dest_dir=config["destination"],
            db_manager=db_manager,
            supported_extensions=config["supported_extensions"],
            image_extensions=config["image_extensions"],
            video_extensions=config["video_extensions"],
            photographic_prefixes=config.get("photographic_prefixes", []),
            exclude_hidden_dirs=config.get("exclude_hidden_dirs", True),
            exclude_patterns=config.get("exclude_patterns", []),
            dry_run=getattr(args, 'dry_run', False)
        )
        if args.verbose:
            print("File processor inizializzato")
        return file_processor
    except Exception as e:
        if not args.quiet:
            print(f"Errore durante l'inizializzazione del file processor: {e}")
        return None


def main():
    """
    Funzione principale con gestione completa degli errori e CLI professionale.
    """
    # Parse argomenti della linea di comando
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging minimo SOLO per errori critici iniziali
    setup_minimal_logging()
    
    if not args.quiet:
        print("Avvio Photo and Video Organizer")
    
    # Carica e valida la configurazione
    try:
        config = ConfigLoader.load_config(args.config)
        if args.verbose:
            print(f"Configurazione caricata da: {args.config}")
        elif not args.quiet:
            print("Configurazione caricata")
            
        # Override da argomenti CLI
        if args.source:
            config["source"] = args.source
            if args.verbose:
                print(f"Directory sorgente override: {args.source}")
        if args.dest:
            config["destination"] = args.dest
            if args.verbose:
                print(f"Directory destinazione override: {args.dest}")
                
    except FileNotFoundError:
        print(f"Errore: Il file di configurazione '{args.config}' non e' stato trovato.")
        return 1
    except Exception as e:
        print(f"Errore durante il caricamento della configurazione: {e}")
        return 1
    
    # Valida la configurazione
    try:
        validate_config(config, args)
    except ValueError as e:
        print(f"Errore di configurazione: {e}")
        return 1
    except Exception as e:
        print(f"Errore durante la validazione della configurazione: {e}")
        return 1
    
    # Modalita' di reset - gestita prima di altre inizializzazioni
    if args.reset:
        if args.verbose:
            print("Modalita' reset attivata")
        elif not args.quiet:
            print("Modalita' reset attivata")
        # Setup logging per reset
        initialize_logging(config, args)
        reset_environment(config["database"], config["log"], config["destination"], args)
        return 0
    
    # Modalita' dry-run
    if hasattr(args, 'dry_run') and args.dry_run:
        if not args.quiet:
            print("=== MODALITA' DRY-RUN ===")
            print("Anteprima operazioni (nessuna modifica effettiva)")
            print()
        # Dry-run non inizializza logging su file (non serve)
    else:
        # Inizializza il logging completo (SOLO SU FILE per modalità normale)
        initialize_logging(config, args)
    
    # Verifica/crea la directory di destinazione
    dest_dir = Path(config["destination"])
    if not create_destination_directory(dest_dir, args):
        if not args.quiet:
            print("Impossibile procedere senza directory di destinazione.")
        return 1
    
    # Inizializza il database manager (solo se non è dry-run)
    if hasattr(args, 'dry_run') and args.dry_run:
        db_manager = None  # Non serve database per dry-run
        if args.verbose:
            print("Dry-run: database non necessario")
    else:
        db_manager = initialize_database(config, args)
        if db_manager is None:
            if not args.quiet:
                print("Errore critico: impossibile inizializzare il database.")
            return 1
    
    # Inizializza il processore dei file
    file_processor = initialize_file_processor(config, db_manager, args)
    if file_processor is None:
        if not args.quiet:
            print("Errore critico: impossibile inizializzare il processore dei file.")
        return 1
    
    # Scansiona la directory di origine e processa i file
    try:
        if not args.quiet:
            print("Inizio scansione della directory sorgente")
        file_processor.scan_directory()
        if not args.quiet:
            print("Scansione completata con successo")
        return 0
    except KeyboardInterrupt:
        if not args.quiet:
            print("\nOperazione interrotta dall'utente (Ctrl+C)")
        return 130  # Exit code standard per SIGINT
    except PermissionError as e:
        if not args.quiet:
            print(f"Errore di permessi: {e}")
        return 13  # Permission denied
    except OSError as e:
        if not args.quiet:
            print(f"Errore del sistema: {e}")
        return 5   # I/O error
    except Exception as e:
        if not args.quiet:
            print(f"Errore durante la scansione della directory: {e}")
        return 1   # General error


if __name__ == "__main__":
    sys.exit(main())