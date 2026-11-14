"""Reproduce CRC-validated recovery of matches.csv from a solid archive tail.

Only metadata is written. Temporary LZMA2 dictionary-prefix bytes are never
saved as source data. Neighbouring MP4 containers are not decoded as videos.
"""
from pathlib import Path
import urllib.request
import lzma
import zlib
import json
import csv
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "related_work/uxo/sd-fhd-trace"
END = 61512100409
LENGTH = 20 * 1024 * 1024
CSV_SIZE, CSV_CRC = 23048, 2231209736


def run_length(raw, pos):
    unpacked = chunks = 0
    while pos < len(raw):
        control = raw[pos]
        if control == 0:
            return (unpacked, chunks) if pos == len(raw)-1 else None
        if control in (1,2):
            size = int.from_bytes(raw[pos+1:pos+3], 'big')+1
            pos += 3+size;unpacked += size
        elif control >= 128:
            size = ((control&31)<<16)+int.from_bytes(raw[pos+1:pos+3], 'big')+1
            packed = int.from_bytes(raw[pos+3:pos+5], 'big')+1
            pos += (6 if control>=192 else 5)+packed;unpacked += size
        else: return None
        chunks += 1
    return None


def main():
    path = OUT/'matches-dictionary-tail.bin'
    if not path.is_file():
        start=END-LENGTH
        url=f'https://zenodo.org/records/13778485/files/data_processed.7z?download=1&audit_tail20={start}'
        with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':f'bytes={start}-{END-1}'}),timeout=45) as response:
            assert response.status==206
            path.write_bytes(response.read(LENGTH+1))
    raw=path.read_bytes();assert len(raw)==LENGTH
    candidates=[]
    for pos in range(65540):
        if raw[pos] in (1,2):
            parsed=run_length(raw,pos)
            if parsed and parsed[1]>200:candidates.append(pos)
    for pos in candidates:
        for prefix in range(1,5):
            trial=b'\x01'+(prefix-1).to_bytes(2,'big')+bytes(prefix)+raw[pos:]
            if raw[pos]==1:trial=raw[pos:]
            try:
                data=lzma.decompress(trial,format=lzma.FORMAT_RAW,filters=[{'id':lzma.FILTER_LZMA2,'dict_size':1<<24}])[-CSV_SIZE:]
            except lzma.LZMAError:continue
            if len(data)==CSV_SIZE and zlib.crc32(data)==CSV_CRC:
                (OUT/'matches.csv').write_bytes(data)
                rows=list(csv.DictReader(data.decode('utf-8').splitlines()))
                selected=[r for r in rows if r['aris_file'].split('/')[-1] in {'2023-09-21_101622','2023-09-21_103140'}]
                assert len(selected)==2
                log={'archive_range_start':END-LENGTH,'archive_range_end':END-1,'cached_range_sha256':hashlib.sha256(raw).hexdigest(),'csv_size':len(data),'csv_crc32':zlib.crc32(data),'csv_sha256':hashlib.sha256(data).hexdigest(),'decoder_start':pos,'temporary_prefix_size':prefix,'selected_match_rows':selected,'operation':'only CSV materialized; container bytes traversed in solid-stream reconstruction, no unrelated image/video decoded'}
                (OUT/'matches-metadata-verification.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({'csv_size_crc_verified':True,'selected_match_rows':len(selected)}));return
    raise RuntimeError('No metadata passing the official CRC check')


if __name__=='__main__':main()
