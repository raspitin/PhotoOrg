#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

def analyze_directory(source_dir):
    """Analizza una directory e mostra statistiche dettagliate sui file."""
    source_path = Path(source_dir)
    
    # Estensioni supportate dal programma
    supported_extensions = {
        '.jpg', '.jpeg', '.png', '.heic', 
        '.mp4', '.mov', '.avi', '.mkv', '.m2t', '.3gp'
    }
    
    all_files = []
    hidden_files = []
    supported_files = []
    unsupported_files = []
    files_without_extension = []
    
    print(f"Analizzando directory: {source_dir}")
    print("=" * 50)
    
    # Analizza tutti i file
    for file_path in source_path.rglob("*"):
        if file_path.is_file():
            all_files.append(file_path)
            
            # Controlla se è in una directory nascosta
            is_hidden = False
            for part in file_path.parts:
                if part.startswith('.') and part != '.':
                    is_hidden = True
                    break
            
            if is_hidden:
                hidden_files.append(file_path)
            else:
                # File non nascosto - controlla estensione
                if not file_path.suffix:
                    files_without_extension.append(file_path)
                elif file_path.suffix.lower() in supported_extensions:
                    supported_files.append(file_path)
                else:
                    unsupported_files.append(file_path)
    
    # Stampa statistiche
    print(f"File totali trovati: {len(all_files)}")
    print(f"File in directory nascoste: {len(hidden_files)}")
    print(f"File visibili: {len(all_files) - len(hidden_files)}")
    print(f"  - File supportati: {len(supported_files)}")
    print(f"  - File non supportati: {len(unsupported_files)}")
    print(f"  - File senza estensione: {len(files_without_extension)}")
    print(f"\nTotale file visibili: {len(supported_files) + len(unsupported_files) + len(files_without_extension)}")
    
    # Mostra esempi di file non supportati
    if unsupported_files:
        print("\nEsempi di file non supportati:")
        extensions_count = {}
        for f in unsupported_files[:10]:  # Mostra solo i primi 10
            ext = f.suffix.lower()
            extensions_count[ext] = extensions_count.get(ext, 0) + 1
            print(f"  {f.name}")
        
        print("\nEstensioni non supportate trovate:")
        for ext, count in sorted(extensions_count.items()):
            print(f"  {ext}: {count} file")
    
    # Mostra file senza estensione
    if files_without_extension:
        print(f"\nFile senza estensione: {len(files_without_extension)}")
        for f in files_without_extension[:5]:  # Mostra solo i primi 5
            print(f"  {f.name}")
    
    # Confronto con find
    print("\n" + "=" * 50)
    print("Confronto con comando find:")
    print(f'find {source_dir} -type d -name ".*" -prune -o -type f | wc -l')
    print(f"Dovrebbe mostrare: {len(all_files) - len(hidden_files)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_directory(sys.argv[1])
    else:
        print("Uso: python debug_files.py /path/to/directory")