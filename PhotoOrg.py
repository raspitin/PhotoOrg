from config.config_loader import ConfigLoader
from loggingSetup.logging_setup import LoggingSetup
from database.database_manager import DatabaseManager
from processing.file_processor import FileProcessor
from pathlib import Path
import sys
import logging
import shutil
from typing import Dict, Any, Optional


def setup_minimal_logging():
    """
    Configura logging minimo per tracciare eventi prima della configurazione completa.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )


def validate_config(config: Dict[str, Any]) -> None:
    """
    Valida che la configurazione contenga tutte le chiavi richieste.
    
    Args:
        config: Dizionario di configurazione da validare
        
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
        raise ValueError(f"Il percorso sorgente non è una directory: {source_path}")
    
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
            raise ValueError(f"Il percorso di destinazione esiste ma non è una directory: {dest_path}")
        
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
            raise ValueError(f"'{ext_key}' non può essere una lista vuota")
    
    # Verifica che photographic_prefixes sia una lista (se presente)
    if "photographic_prefixes" in config and not isinstance(config["photographic_prefixes"], list):
        raise ValueError("'photographic_prefixes' deve essere una lista")
    
    # Verifica che exclude_patterns sia una lista (se presente)
    if "exclude_patterns" in config and not isinstance(config["exclude_patterns"], list):
        raise ValueError("'exclude_patterns' deve essere una lista")
    
    logging.info("✅ Configurazione validata con successo")


def create_destination_directory(dest_dir: Path) -> bool:
    """
    Gestisce la creazione della directory di destinazione con gestione errori robusta.
    
    Args:
        dest_dir: Path della directory di destinazione
        
    Returns:
        bool: True se la directory esiste o è stata creata, False altrimenti
    """
    if dest_dir.exists():
        if not dest_dir.is_dir():
            logging.error(f"Il percorso di destinazione esiste ma non è una directory: {dest_dir}")
            print(f"Errore: '{dest_dir}' esiste ma non è una directory.")
            return False
        logging.info(f"Directory di destinazione già esistente: {dest_dir}")
        return True
    
    try:
        response = input(f"La directory di destinazione '{dest_dir}' non esiste. Vuoi crearla? [s/N]: ").strip().lower()
        if response == "s":
            dest_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"✅ Directory '{dest_dir}' creata con successo")
            print(f"Directory '{dest_dir}' creata con successo.")
            return True
        else:
            logging.info("Operazione annullata dall'utente")
            print("Operazione annullata. Nessuna directory creata.")
            return False
            
    except PermissionError as e:
        logging.error(f"Permesso negato per creare la directory '{dest_dir}': {e}")
        print(f"Errore: Permesso negato per creare la directory '{dest_dir}': {e}")
        return False
    except OSError as e:
        logging.error(f"Errore del sistema operativo durante la creazione di '{dest_dir}': {e}")
        print(f"Errore del sistema durante la creazione della directory '{dest_dir}': {e}")
        return False
    except KeyboardInterrupt:
        logging.warning("Operazione interrotta dall'utente (Ctrl+C)")
        print("\nOperazione interrotta dall'utente.")
        return False
    except Exception as e:
        logging.error(f"Errore imprevisto durante la creazione della directory '{dest_dir}': {e}")
        print(f"Errore imprevisto durante la creazione della directory '{dest_dir}': {e}")
        return False


def reset_environment(database_path: str, log_path: str, dest_dir: str) -> None:
    """
    Ripristina l'ambiente eliminando il database, i log e le directory di destinazione.
    Con gestione completa delle eccezioni e conferma utente.
    
    Args:
        database_path: Percorso del file database
        log_path: Percorso del file di log
        dest_dir: Percorso della directory di destinazione
    """
    logging.info("🔄 Richiesta procedura di reset dell'ambiente")
    print("🔄 ATTENZIONE: Procedura di Reset dell'Ambiente")
    print("Questa operazione eliminerà:")
    print(f"  - Database: {database_path}")
    print(f"  - File di log: {log_path}")
    print(f"  - Directory: {dest_dir}/PHOTO")
    print(f"  - Directory: {dest_dir}/VIDEO") 
    print(f"  - Directory: {dest_dir}/PHOTO_DUPLICATES")
    print(f"  - Directory: {dest_dir}/VIDEO_DUPLICATES")
    print(f"  - Directory: {dest_dir}/ToReview")
    print()
    
    try:
        response = input("Sei sicuro di voler procedere? [s/N]: ").strip().lower()
        if response != "s":
            logging.info("Reset annullato dall'utente")
            print("Reset annullato.")
            return
    except KeyboardInterrupt:
        logging.info("Reset interrotto dall'utente (Ctrl+C)")
        print("\nReset interrotto.")
        return
    
    logging.info("🔄 Inizio procedura di reset dell'ambiente")
    print("🔄 Inizio procedura di reset dell'ambiente")
    
    reset_success = True
    
    # Elimina il database
    db_path = Path(database_path)
    if db_path.exists():
        try:
            db_path.unlink()
            logging.info(f"✅ Database eliminato: {db_path}")
            print(f"Database eliminato: {db_path}")
        except PermissionError as e:
            logging.error(f"❌ Permesso negato per eliminare il database '{db_path}': {e}")
            print(f"Errore: Permesso negato per eliminare il database '{db_path}': {e}")
            reset_success = False
        except OSError as e:
            logging.error(f"❌ Errore del sistema operativo eliminando il database '{db_path}': {e}")
            print(f"Errore del sistema eliminando il database '{db_path}': {e}")
            reset_success = False
        except Exception as e:
            logging.error(f"❌ Errore imprevisto eliminando il database '{db_path}': {e}")
            print(f"Errore imprevisto eliminando il database '{db_path}': {e}")
            reset_success = False
    else:
        logging.info(f"ℹ️ Database non trovato (già eliminato?): {db_path}")
        print(f"Database non trovato (già eliminato?): {db_path}")

    # Elimina il file di log
    log_file = Path(log_path)
    if log_file.exists():
        try:
            log_file.unlink()
            logging.info(f"✅ File di log eliminato: {log_file}")
            print(f"File di log eliminato: {log_file}")
        except PermissionError as e:
            logging.error(f"❌ Permesso negato per eliminare il log '{log_file}': {e}")
            print(f"Errore: Permesso negato per eliminare il log '{log_file}': {e}")
            reset_success = False
        except OSError as e:
            logging.error(f"❌ Errore del sistema operativo eliminando il log '{log_file}': {e}")
            print(f"Errore del sistema eliminando il log '{log_file}': {e}")
            reset_success = False
        except Exception as e:
            logging.error(f"❌ Errore imprevisto eliminando il log '{log_file}': {e}")
            print(f"Errore imprevisto eliminando il log '{log_file}': {e}")
            reset_success = False
    else:
        logging.info(f"ℹ️ File di log non trovato (già eliminato?): {log_file}")
        print(f"File di log non trovato (già eliminato?): {log_file}")

    # Elimina le directory di destinazione
    dest_path = Path(dest_dir)
    folders_to_remove = ["PHOTO", "VIDEO", "PHOTO_DUPLICATES", "VIDEO_DUPLICATES", "ToReview"]
    
    for folder in folders_to_remove:
        folder_path = dest_path / folder
        if folder_path.exists():
            try:
                shutil.rmtree(folder_path)
                logging.info(f"✅ Cartella eliminata: {folder_path}")
                print(f"Cartella eliminata: {folder_path}")
            except PermissionError as e:
                logging.error(f"❌ Permesso negato per eliminare '{folder_path}': {e}")
                print(f"Errore: Permesso negato per eliminare '{folder_path}': {e}")
                reset_success = False
            except OSError as e:
                logging.error(f"❌ Errore del sistema operativo eliminando '{folder_path}': {e}")
                print(f"Errore del sistema eliminando '{folder_path}': {e}")
                reset_success = False
            except Exception as e:
                logging.error(f"❌ Errore imprevisto eliminando '{folder_path}': {e}")
                print(f"Errore imprevisto eliminando '{folder_path}': {e}")
                reset_success = False
        else:
            logging.info(f"ℹ️ Cartella non trovata (già eliminata?): {folder_path}")
            print(f"Cartella non trovata (già eliminata?): {folder_path}")
    
    if reset_success:
        logging.info("✅ Reset dell'ambiente completato con successo")
        print("✅ Reset dell'ambiente completato con successo")
    else:
        logging.warning("⚠️ Reset dell'ambiente completato con alcuni errori. Controlla i log sopra.")
        print("⚠️ Reset dell'ambiente completato con alcuni errori. Controlla i messaggi sopra.")


def initialize_logging(config: Dict[str, Any]) -> None:
    """
    Inizializza il sistema di logging usando la configurazione fornita.
    
    Args:
        config: Dizionario di configurazione
    """
    try:
        LoggingSetup.setup_logging(config["log"])
        logging.info("✅ Sistema di logging completo inizializzato")
    except Exception as e:
        logging.error(f"❌ Errore durante l'inizializzazione del logging completo: {e}")
        logging.info("ℹ️ Continuo con il logging di base")


def initialize_database(config: Dict[str, Any]) -> Optional[DatabaseManager]:
    """
    Inizializza il database manager con gestione errori.
    
    Args:
        config: Dizionario di configurazione
        
    Returns:
        DatabaseManager istanziato o None in caso di errore
    """
    try:
        db_manager = DatabaseManager(config["database"])
        logging.info("✅ Database manager inizializzato")
        return db_manager
    except Exception as e:
        logging.error(f"❌ Errore durante l'inizializzazione del database: {e}")
        return None


def initialize_file_processor(config: Dict[str, Any], db_manager: DatabaseManager) -> Optional[FileProcessor]:
    """
    Inizializza il processore dei file con gestione errori.
    
    Args:
        config: Dizionario di configurazione
        db_manager: Istanza del database manager
        
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
            exclude_patterns=config.get("exclude_patterns", [])
        )
        logging.info("✅ File processor inizializzato")
        return file_processor
    except Exception as e:
        logging.error(f"❌ Errore durante l'inizializzazione del file processor: {e}")
        return None


def main():
    """
    Funzione principale con gestione completa degli errori e logging anticipato.
    """
    # Setup logging minimo per tracciare tutto fin dall'inizio
    setup_minimal_logging()
    logging.info("🚀 Avvio Photo and Video Organizer")
    
    # Carica e valida la configurazione
    try:
        config = ConfigLoader.load_config()
        logging.info("✅ Configurazione caricata")
    except FileNotFoundError:
        logging.error("❌ Il file di configurazione 'config.yaml' non è stato trovato")
        print("Errore: Il file di configurazione 'config.yaml' non è stato trovato.")
        return
    except Exception as e:
        logging.error(f"❌ Errore durante il caricamento della configurazione: {e}")
        print(f"Errore durante il caricamento della configurazione: {e}")
        return
    
    # Valida la configurazione
    try:
        validate_config(config)
    except ValueError as e:
        logging.error(f"❌ Configurazione non valida: {e}")
        print(f"Errore di configurazione: {e}")
        return
    except Exception as e:
        logging.error(f"❌ Errore imprevisto durante la validazione: {e}")
        print(f"Errore durante la validazione della configurazione: {e}")
        return
    
    # Modalità di reset - gestita prima di altre inizializzazioni
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        logging.info("🔄 Modalità reset attivata")
        # Inizializza logging completo per il reset
        initialize_logging(config)
        reset_environment(config["database"], config["log"], config["destination"])
        return
    
    # Inizializza il logging completo
    initialize_logging(config)
    
    # Verifica/crea la directory di destinazione
    dest_dir = Path(config["destination"])
    if not create_destination_directory(dest_dir):
        logging.error("❌ Impossibile procedere senza directory di destinazione")
        print("Operazione annullata. Impossibile procedere senza directory di destinazione.")
        return
    
    # Inizializza il database manager
    db_manager = initialize_database(config)
    if db_manager is None:
        logging.error("❌ Impossibile procedere senza database manager")
        print("Errore critico: impossibile inizializzare il database.")
        return
    
    # Inizializza il processore dei file
    file_processor = initialize_file_processor(config, db_manager)
    if file_processor is None:
        logging.error("❌ Impossibile procedere senza file processor")
        print("Errore critico: impossibile inizializzare il processore dei file.")
        return
    
    # Scansiona la directory di origine e processa i file
    try:
        logging.info("📁 Inizio scansione della directory sorgente")
        file_processor.scan_directory()
        logging.info("✅ Scansione completata con successo")
    except KeyboardInterrupt:
        logging.warning("⚠️ Operazione interrotta dall'utente (Ctrl+C)")
        print("\nOperazione interrotta dall'utente.")
    except PermissionError as e:
        logging.error(f"❌ Permesso negato durante la scansione: {e}")
        print(f"Errore di permessi: {e}")
    except OSError as e:
        logging.error(f"❌ Errore del sistema operativo durante la scansione: {e}")
        print(f"Errore del sistema: {e}")
    except Exception as e:
        logging.error(f"❌ Errore imprevisto durante la scansione: {e}")
        print(f"Errore durante la scansione della directory: {e}")


if __name__ == "__main__":
    main()
