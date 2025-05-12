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
