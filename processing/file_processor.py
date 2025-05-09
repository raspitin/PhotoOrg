from pathlib import Path
from processing.hash_utils import HashUtils
from processing.date_extractor import DateExtractor
from processing.file_utils import FileUtils
from database.database_manager import DatabaseManager
import logging
from time import time
from multiprocessing import Pool, cpu_count
import sqlite3
import threading
import queue
from collections import Counter
from tqdm import tqdm

def process_file_data_external(args):
    file_path, file_hash, image_extensions, video_extensions, photographic_prefixes, dest_dir = args
    from processing.date_extractor import DateExtractor
    date_extracted = DateExtractor.extract_date(file_path, image_extensions, video_extensions)
    if date_extracted is None:
        year = month = yyyymmdd = None
    else:
        year, month, yyyymmdd = date_extracted

    media_type = "PHOTO" if file_path.suffix.lower() in image_extensions else "VIDEO"
    file_name = file_path.name

    review_dir = dest_dir / "ToReview"
    review_dir.mkdir(parents=True, exist_ok=True)

    if year is None or month is None:
        new_path = FileUtils.safe_copy(file_path, review_dir, file_name)
        return (str(file_path), file_hash, year, month, media_type, "to_review", str(new_path.parent), new_path.name, f"Moved to review: {new_path} - Hash: {file_hash}")

    dest_dir_media = dest_dir / media_type / year / month
    dup_dir = dest_dir / f"{media_type}_DUPLICATES" / year / month
    dest_dir_media.mkdir(parents=True, exist_ok=True)
    dup_dir.mkdir(parents=True, exist_ok=True)

    is_photo_name = any(file_name.startswith(prefix) for prefix in photographic_prefixes)
    return (str(file_path), file_hash, year, month, media_type, "candidate", file_name, is_photo_name, dest_dir_media, dup_dir, None)


class FileProcessor:
    def __init__(self, source_dir, dest_dir, db_manager, supported_extensions, photographic_prefixes, image_extensions, video_extensions):
        self.source_dir = Path(source_dir)
        self.dest_dir = Path(dest_dir)
        self.db_manager = db_manager
        self.supported_extensions = supported_extensions
        self.photographic_prefixes = photographic_prefixes
        self.image_extensions = image_extensions
        self.video_extensions = video_extensions
        self.log_queue = queue.Queue()

    def log_writer(self):
        while True:
            record = self.log_queue.get()
            if record is None:
                break
            logging.info(record)

    def scan_directory(self):
        start_time = time()
        conn = self.db_manager.create_db()
        logger_thread = threading.Thread(target=self.log_writer)
        logger_thread.start()

        all_files = []
        ignored = []
        for path in self.source_dir.rglob("*"):
            if path.is_file():
                if path.suffix.lower() in self.supported_extensions:
                    all_files.append(path)
                else:
                    ignored.append(path)

        if not all_files:
            self.log_queue.put("No files found in source directory.")
            self.log_queue.put(None)
            logger_thread.join()
            conn.close()
            return

        if ignored:
            self.log_queue.put(f"Ignored unsupported files: {len(ignored)}")
            for p in ignored:
                self.log_queue.put(f"Ignored: {p} (extension: {p.suffix})")

        required = sum(p.stat().st_size for p in all_files)
        free = FileUtils.available_space(self.dest_dir)
        if free < required:
            self.log_queue.put(f"Insufficient space: needed {required}, available {free}")
            self.log_queue.put(None)
            logger_thread.join()
            conn.close()
            return

        hash_results = [HashUtils.compute_hash(file) for file in all_files]
        hash_map = dict(hash_results)

        with Pool(processes=cpu_count()) as pool:
            results = list(tqdm(
                pool.imap_unordered(process_file_data_external, [
                    (file, hash_map[str(file)], self.image_extensions, self.video_extensions, self.photographic_prefixes, self.dest_dir)
                    for file in all_files
                ]),
                total=len(all_files),
                desc="Elaborazione",
                unit="file"
            ))

        cursor = conn.cursor()
        cursor.execute("SELECT hash FROM files WHERE status = 'migrated'")
        migrated_hashes = set(row[0] for row in cursor.fetchall())

        stats = {"migrated": 0, "duplicates": 0, "to_review": 0}
        hash_counter = {}
        batch_records = []
        all_migrated_hashes = []

        for result in results:
            if result[5] == "to_review":
                batch_records.append(result[:-1])
                stats["to_review"] += 1
                continue

            file_path, file_hash, year, month, media_type, _, file_name, is_photo, dest_dir, dup_dir, _ = result
            first_occurrence = file_hash not in migrated_hashes
            if first_occurrence:
                hash_counter[file_hash] = []
            hash_counter[file_hash].append((Path(file_path), is_photo))

        for file_hash, entries in hash_counter.items():
            selected = sorted(entries, key=lambda x: not x[1])[0][0]
            for file_path, is_photo in entries:
                file_name = file_path.name
                date_extracted = DateExtractor.extract_date(file_path)
                if date_extracted is None:
                    year = month = None
                else:
                    year, month, _ = date_extracted
                media_type = "PHOTO" if file_path.suffix.lower() in [".jpg", ".jpeg", ".png"] else "VIDEO"
                dest_dir = self.dest_dir / media_type / year / month
                dup_dir = self.dest_dir / f"{media_type}_DUPLICATES" / year / month
                dest_dir.mkdir(parents=True, exist_ok=True)
                dup_dir.mkdir(parents=True, exist_ok=True)

                if file_path == selected:
                    status = "migrated"
                    target_dir = dest_dir
                    stats["migrated"] += 1
                    migrated_hashes.add(file_hash)
                    all_migrated_hashes.append(file_hash)
                else:
                    status = "duplicate"
                    target_dir = dup_dir
                    stats["duplicates"] += 1

                new_path = FileUtils.safe_copy(file_path, target_dir, file_name)
                batch_records.append((str(file_path), file_hash, year, month, media_type, status, str(new_path.parent), new_path.name))

        cursor.executemany(
            """
            INSERT INTO files (original_path, hash, year, month, media_type, status, destination_path, final_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch_records
        )

        duplicates_check = Counter(all_migrated_hashes)
        for h, count in duplicates_check.items():
            if count > 1:
                self.log_queue.put(f"WARNING: hash {h} migrated {count} times")

        conn.commit()
        conn.close()
        elapsed = time() - start_time

        summary = (
            f"Summary:\n"
            f"  Migrated files: {stats['migrated']}\n"
            f"  Duplicate files: {stats['duplicates']}\n"
            f"  Files to review: {stats['to_review']}\n"
            f"  Unsupported files: {len(ignored)}\n"
            f"  Total time: {elapsed:.2f} seconds"
        )
        self.log_queue.put(summary)
        self.log_queue.put(None)
        logger_thread.join()
        print("\n" + summary)
