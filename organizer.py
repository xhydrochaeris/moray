import glob
import os, re
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

cwd = os.getcwd()
mp3s = glob.glob(cwd+ '/*.mp3')

def sanitize_filename(name: str) -> str:
    # Replace Windows/Unix illegal characters and control chars with underscore
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)
    return name

for mp3f in mp3s:
    audio = MP3(mp3f)
    if audio.tags is None:
        print(f"ERROR: No ID3 tags found in: {mp3f}")
        continue
    tags = audio.tags

    def get_tag(frame_id):
        if frame_id in tags:
            return str(tags[frame_id].text[0])
        return None

    year = get_tag('TDRC')
    if year is None:
        year = get_tag('TYER')
    if year is None:
        year = "UNKNOWN"
    title = get_tag('TIT2')
    if title is None:
        print(f"ERROR: No title for: {mp3f}")
        continue
    track_nr = get_tag('TRCK')
    if track_nr is None:
        track_nr = ""
    artist = get_tag('TPE1')
    if artist is None:
        artist = get_tag('TPE2')
    if artist is None:
        print(f"ERROR: No artist for: {mp3f}")
        continue
    album = get_tag('TALB')
    if album is None:
        print(f"ERROR: No album name for: {mp3f}")
        continue

    ARTIST_DIR = cwd+'/'+sanitize_filename(artist)
    try:
        os.mkdir(ARTIST_DIR)
    except FileExistsError:
        pass

    ALBUM_DIR = ARTIST_DIR+'/'+sanitize_filename("["+year+"] "+album)
    try:
        os.mkdir(ALBUM_DIR)
    except FileExistsError:
        pass

    new_track_name = sanitize_filename(track_nr+". "+title+".mp3")
    os.rename(mp3f, ALBUM_DIR+'/'+new_track_name)

logs = glob.glob(cwd+ '/*.log')
for logf in logs:
    os.remove(logf)
