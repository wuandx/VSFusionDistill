"""Copy an existing read-only archive to D:/pby, verify source + target MD5.

Resume-safe: while the source is streamed for hashing, any existing partial is
re-checked block-by-block; on the first mismatch the partial is truncated at
that point and copying continues from there (self-healing, logged in status).
"""
from pathlib import Path
import hashlib,json,time,os,traceback
SRC=Path('/mnt/uxo_external_ro/datasets/uxo-dataset2024/data_processed.7z')
DST=Path('/mnt/d/pby/data_processed.7z')
PART=DST.with_suffix('.7z.partial')
STATE=Path('/mnt/d/pby/.uxo-transfer/status.json')
EXPECTED='2b9ef16c763a6964c608ed99a9cd1edb'
SIZE=61513277947
START=time.time()
def status(phase,done=0,**extra):
    row={'phase':phase,'bytes_done':done,'total_bytes':SIZE,'elapsed_seconds':round(time.time()-START,1),'source':str(SRC),'target':str(DST),'expected_md5':EXPECTED,'source_deleted':False,**extra}
    p=STATE.with_suffix('.tmp');p.write_text(json.dumps(row,indent=2),encoding='utf-8');p.replace(STATE)
    print(json.dumps(row),flush=True)
def hash_file(path,phase):
    h=hashlib.md5();done=0;last=0
    with path.open('rb',buffering=0) as stream:
        while block:=stream.read(16*1024*1024):
            h.update(block);done+=len(block)
            if time.time()-last>=30:status(phase,done);last=time.time()
    return h.hexdigest()
def main():
    STATE.parent.mkdir(parents=True,exist_ok=True);status('checking_paths')
    if DST.exists():
        assert DST.stat().st_size==SIZE,'Existing destination has wrong size; not overwritten'
        actual=hash_file(DST,'verifying_existing_target');assert actual==EXPECTED,'Existing destination MD5 differs; not overwritten'
        status('complete',SIZE,target_md5=actual,target_verified=True);return
    assert SRC.stat().st_size==SIZE,'Source size differs'
    existing=PART.stat().st_size if PART.exists() else 0
    assert existing<=SIZE,'Partial file too large; retained without overwriting'
    digest=hashlib.md5();done=0;last=0;verify_existing=existing>0
    with SRC.open('rb',buffering=0) as source,PART.open('r+b' if PART.exists() else 'w+b',buffering=0) as target:
        while block:=source.read(16*1024*1024):
            digest.update(block)
            if verify_existing and done<existing:
                n=min(len(block),existing-done)
                if target.read(n)!=block[:n]:
                    status('truncating_partial_at_mismatch',done,partial_bytes=existing)
                    target.seek(done);target.truncate(done);target.write(block);verify_existing=False
                elif n<len(block):
                    target.write(block[n:])
            else:
                target.write(block)
            done+=len(block)
            if time.time()-last>=30:
                status('verifying_existing_partial' if verify_existing and done<existing else 'copying_and_hashing_source',done);last=time.time()
        target.flush();os.fsync(target.fileno())
    actual=digest.hexdigest();assert done==SIZE and actual==EXPECTED,'Source MD5 mismatch; partial retained'
    status('source_verified',done,source_md5=actual)
    target_md5=hash_file(PART,'verifying_target')
    assert target_md5==EXPECTED,'Target MD5 mismatch; partial retained'
    assert not DST.exists(),'Destination appeared; not overwritten'
    PART.rename(DST)
    status('complete',SIZE,source_md5=actual,target_md5=target_md5,source_verified=True,target_verified=True)
if __name__=='__main__':
    try:main()
    except Exception as error:
        status('failed',error=repr(error));traceback.print_exc();raise
