Photo and Video Organizer
This tool scans a source directory for photo and video files, extracts metadata (date/time, hashes), organizes them into a structured destination directory, logs operations and tracks records in an SQLite database.

Features
Extracts EXIF dates for images (via GExiv2) and encoded/tagged dates for videos (via MediaInfo).

Falls back to filename-based date parsing when metadata is missing.

Computes SHA-256 hash to detect duplicates.

Organizes files into PHOTO/YYYY/MM and VIDEO/YYYY/MM, moves duplicates into separate folders.

Stores all operations in an SQLite database for audit.

Logs detailed info and warnings to file.

Prerequisites
Linux with sudo privileges

Python 3.8+

System packages: python3-gi, gir1.2-gexiv2-0.10, libgexiv2-dev, mediainfo

Installation
Clone the repository
git clone https://github.com/tuo-username/duplicati-foto-video.git
cd duplicati-foto-video

Esegui lo script di bootstrap (installa dipendenze di sistema e Python)
./bootstrap.sh

Esegui lo script di setup (installa librerie Python)
./setup.sh

Configura config.yaml con i percorsi desiderati.

Usage
Avvio normale:
python3 main.py

Per ripulire database, log e directory di destinazione:
python3 main.py --reset

Project structure
bootstrap.sh, setup.sh – script di installazione e setup

config.yaml – configurazione dei percorsi e estensioni supportate

processing/ – modulo Python per elaborazione file

database/ – modulo per gestione SQLite

loggingSetup/ – modulo per configurazione logging

main.py – punto di ingresso primario

Contributing
Pull request e issue sono benvenute. Assicurati di aggiornare requirements.txt se aggiungi nuove dipendenze.