import gi
gi.require_version('GExiv2', '0.10')
from gi.repository import GExiv2
from pymediainfo import MediaInfo
import re
import logging

class DateExtractor:
    @staticmethod
    def extract_date(file_path, image_exts=None, video_exts=None):
        if file_path is None:
            return None
        image_exts = image_exts or []
        video_exts = video_exts or []
        suffix = file_path.suffix.lower()

        try:
            if suffix in image_exts:
                meta = GExiv2.Metadata()
                meta.open_path(str(file_path))
                if meta.has_tag("Exif.Photo.DateTimeOriginal"):
                    date_str = meta.get_tag_string("Exif.Photo.DateTimeOriginal")
                    y, m, d = date_str.split(" ")[0].split(":")
                    return y, m, f"{y}{m}{d}"

            elif suffix in video_exts:
                media_info = MediaInfo.parse(file_path)
                for track in media_info.tracks:
                    if track.track_type == "General":
                        date_str = track.encoded_date or track.tagged_date
                        if date_str:
                            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
                            if match:
                                y, m, d = match.groups()
                                return y, m, f"{y}{m}{d}"
        except Exception as e:
            logging.warning(f"Metadata parsing failed for {file_path}: {e}")

        name = file_path.name
        match = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", name)
        if match:
            y, m, d = match.groups()
            return y, m, f"{y}{m}{d}"

        return None
