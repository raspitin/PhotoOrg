import hashlib

class HashUtils:
    @staticmethod
    def compute_hash(file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(4096), b""):
                hasher.update(block)
        return str(file_path), hasher.hexdigest()