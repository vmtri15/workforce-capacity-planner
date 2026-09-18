"""Fetch public timing metadata, then recruiting CSVs, without executing source code."""
import hashlib
import io
import json
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'


def get(url, headers=None):
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=40)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


class RemoteZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.cache_start, self.cache = 0, b''

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        if size <= 0:
            return b''
        start = self.position
        if not (self.cache_start <= start and start + size <= self.cache_start + len(self.cache)):
            end = min(self.size - 1, start + max(size, 65536) - 1)
            with get(self.url + f'?slice={start}-{end}', {'Range': f'bytes={start}-{end}'}) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
                    raise ValueError('Server did not honor requested byte range')
                self.cache = response.read()
            self.cache_start = start
        result = self.cache[start-self.cache_start:start-self.cache_start+size]
        self.position += len(result)
        return result


def record(rid):
    with get(f'https://zenodo.org/api/records/{rid}') as response:
        return json.load(response)


def main():
    destination = RAW / 'openpack_timing'
    destination.mkdir(exist_ok=True)
    metadata = record(8145223)
    (destination / 'zenodo_record.json').write_text(json.dumps(metadata, indent=2))
    manifest = []
    for item in sorted(metadata['files'], key=lambda f: f['key']):
        if not item['key'].startswith('U'):
            continue
        user = Path(item['key']).stem
        with zipfile.ZipFile(RemoteZip(item['links']['self'], item['size'])) as archive:
            for member in archive.infolist():
                parts = Path(member.filename).parts
                if member.is_dir() or not member.filename.endswith('.csv') or not any(
                    name in parts for name in ('openpack-operations', 'openpack-outliers', 'order-sheet')):
                    continue
                if '..' in parts or Path(member.filename).is_absolute():
                    raise ValueError('Unsafe archive path')
                path = destination / user / member.filename
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    payload = archive.read(member)
                    path.write_bytes(payload)
                payload = path.read_bytes()
                if zlib.crc32(payload) != member.CRC:
                    raise ValueError('ZIP member checksum mismatch')
                manifest.append(dict(path=str(path.relative_to(destination)), size=len(payload),
                                     sha256=hashlib.sha256(payload).hexdigest()))
        print(f'OpenPack {user}: timing metadata fetched', flush=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    destination = RAW / 'jth_data'
    destination.mkdir(exist_ok=True)
    metadata = record(21390581)
    (destination / 'zenodo_record.json').write_text(json.dumps(metadata, indent=2))
    for item in metadata['files']:
        if item['key'] not in ('history.csv', 'jobs.csv', 'candidates.csv', 'dataset_card.md'):
            continue
        with get(item['links']['self']) as response:
            payload = response.read()
        if 'md5:' + hashlib.md5(payload).hexdigest() != item['checksum']:
            raise ValueError('JTH checksum mismatch')
        (destination / item['key']).write_bytes(payload)
        print(f"JTH {item['key']}: checksum verified", flush=True)


if __name__ == '__main__':
    main()
