import hashlib
from mutagen import File

BLACKLIST = {
    "wizkid",
    "davido",
    "burna boy",
    "asake",
    "rema",
    "ayra starr",
}

def sha256(file_path):
    h = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def metadata(file_path):
    audio = File(file_path, easy=True)

    if not audio:
        return {}

    return {
        "title": audio.get("title", [""])[0],
        "artist": audio.get("artist", [""])[0],
        "album": audio.get("album", [""])[0],
    }


def copyright_warning(meta):
    artist = meta.get("artist", "").lower()

    return any(name in artist for name in BLACKLIST)
