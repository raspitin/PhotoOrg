# Photo and Video Organizer  

A Python tool that scans a source directory for photo and video files, extracts metadata (date/time, hashes), organizes them into a structured destination directory, and logs operations to an SQLite database.  

## Features  
- **Metadata Extraction**:  
  - Extracts EXIF dates for images (using `GExiv2`).  
  - Extracts encoded/tagged dates for videos (using `MediaInfo`).  
  - Falls back to filename-based date parsing if metadata is missing.  
- **Duplicate Detection**:  
  - Computes SHA-256 hashes to identify duplicates.  
- **Structured Organization**:  
  - Organizes files into `PHOTO/YYYY/MM` and `VIDEO/YYYY/MM` directories.  
  - Moves duplicates to a separate folder.  
- **Audit & Logging**:  
  - Tracks all operations in an SQLite database.  
  - Logs detailed info and warnings to a file.  

## Prerequisites  
- **Linux** (with `sudo` privileges).  
- **Python 3.8+**.  
- **System Packages**:  
  ```bash
  sudo apt install python3-gi gir1.2-gexiv2-0.10 libgexiv2-dev mediainfo

##Installation
  git clone https://github.com/your-username/photo-video-organizer.git
  cd photo-video-organizer
  Installation
Clone the repository:

bash
git clone https://github.com/your-username/photo-video-organizer.git
cd photo-video-organizer
Run the bootstrap script (installs system and Python dependencies):

bash
./bootstrap.sh
Run the setup script (configures Python libraries):

bash
./setup.sh
Edit config.yaml to set your desired paths and file extensions.

Usage
Normal execution:

bash
 python3 main.py
Reset database, logs, and destination directory:

bash
python3 main.py --reset
Project Structure
plaintext
.
├── bootstrap.sh          # System/Python dependency installer  
├── setup.sh              # Python environment setup  
├── config.yaml           # Configuration (paths, supported extensions)  
├── processing/           # File processing module  
├── database/             # SQLite database handler  
├── loggingSetup/         # Logging configuration  
└── main.py               # Primary entry point  
Contributing
Pull requests and issues are welcome!

Ensure you update requirements.txt if adding new dependencies.

Follow PEP 8 style guidelines for Python code.
