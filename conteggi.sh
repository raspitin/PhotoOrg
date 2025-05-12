# Salva la lista di file trovati da find
find /mnt/Multimedia/FOTO/Camera/ -type d -name ".*" -prune -o -type f -print | sort > find_files.txt

# Crea uno script Python per salvare la lista di file trovati da Python
cat > list_python_files.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import sys

source_path = Path(sys.argv[1])
files = []

for file_path in source_path.rglob("*"):
    is_hidden = False
    for part in file_path.parts:
        if part.startswith('.') and part != '.':
            is_hidden = True
            break
    
    if not is_hidden and file_path.is_file():
        files.append(str(file_path))

for f in sorted(files):
    print(f)
EOF

python3 list_python_files.py /mnt/Multimedia/FOTO/Camera/ > python_files.txt

# Confronta le differenze
diff find_files.txt python_files.txt
