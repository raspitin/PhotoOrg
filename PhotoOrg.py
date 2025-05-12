from config.config_loader import ConfigLoader
from loggingSetup.logging_setup import LoggingSetup
from database.database_manager import DatabaseManager
from processing.file_processor import FileProcessor
from pathlib import Path
import sys


def main():
    # Carica configurazione
    try:
        config = ConfigLoader.load_config()
    except FileNotFoundError:
        print("Errore: Il file di configurazione 'config.yaml' non è stato trovato.")
        return
    except Exception as e:
        print(f"Errore durante il caricamento della configurazione: {e}")
        return

    # Verifica se la directory di destinazione esiste
    dest_dir = Path(config["destination"])
    if not dest_dir.exists():
        response = input(f"La directory di destinazione '{dest_dir}' non esiste. Vuoi crearla? [s/N]: ").strip().lower()
        if response == "s":
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                print(f"Directory '{dest_dir}' creata con successo.")
            except Exception as e:
                print(f"Errore durante la creazione della directory di destinazione: {e}")
                return
        else:
            print("Operazione annullata. Nessuna directory creata.")
            return

    # Setup logging
    LoggingSetup.setup_logging(config["log"])

    # Inizializza il database manager
    db_manager = DatabaseManager(config["database"])

    # Inizializza il processore dei file con i nuovi parametri di esclusione
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

    # Modalità di reset
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_environment(config["database"], config["log"], config["destination"])
        return

    # Scansiona la directory di origine e processa i file
    try:
        file_processor.scan_directory()
    except Exception as e:
        print(f"Errore durante la scansione della directory: {e}")


def reset_environment(database_path, log_path, dest_dir):
    """
    Ripristina l'ambiente eliminando il database, i log e le directory di destinazione.
    """
    from shutil import rmtree
    from pathlib import Path

    # Elimina il database
    db_path = Path(database_path)
    if db_path.exists():
        db_path.unlink()
        print(f"Database eliminato: {db_path}")

    # Elimina il file di log
    log_file = Path(log_path)
    if log_file.exists():
        log_file.unlink()
        print(f"File di log eliminato: {log_file}")

    # Elimina le directory di destinazione
    dest_path = Path(dest_dir)
    for folder in ["PHOTO", "VIDEO", "PHOTO_DUPLICATES", "VIDEO_DUPLICATES", "ToReview"]:
        folder_path = dest_path / folder
        if folder_path.exists():
            rmtree(folder_path)
            print(f"Cartella eliminata: {folder_path}")


if __name__ == "__main__":
    main()