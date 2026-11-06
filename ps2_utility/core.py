import os
import sys
import re

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller _MEIPASS"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def extract_game_id(file_path):
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024 * 1024 * 15)  
            byte_pattern = re.compile(b'[S|B|P|M][L|C|E|P|A|K|O|W|V][U|S|E|I|A|D|M]S?_\\d{3}\\.\\d{2}', re.IGNORECASE)
            match = byte_pattern.search(chunk)
            if match:
                raw_id = match.group(0).decode('ascii', errors='ignore').upper()
                clean_id = raw_id.replace('_', '').replace('.', '').replace('-', '').upper()
                return clean_id, raw_id
    except Exception as e:
        print(f"Error scanning file headers: {e}")
        
    filename = os.path.basename(file_path)
    fallback_pattern = re.compile(r'[S|B|P|M][L|C|E|P|A|K|O|W|V][U|S|E|I|A|D|M]S?[-_]\d{3}\.?\d{2}', re.IGNORECASE)
    match = fallback_pattern.search(filename)
    if match:
        raw_id = match.group(0).upper()
        clean_id = raw_id.replace('_', '').replace('.', '').replace('-', '').upper()
        std_raw_id = f"{clean_id[:4]}_{clean_id[4:7]}.{clean_id[7:]}" 
        return clean_id, std_raw_id
        
    return None, None

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0