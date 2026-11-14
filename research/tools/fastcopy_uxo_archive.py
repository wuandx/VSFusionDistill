"""Fast resume copy of the read-only UXO archive to D:/pby.

Why this exists: transfer.py re-read the destination block-by-block *interleaved*
with writing, which on the 9p/drvfs mount collapsed throughput to 4-26 MB/s and
kept the flaky USB enclosure under load for hours. Here the two jobs are split:

  phase 1 (read-only): stream source 0..P and the existing partial in lockstep,
                       compare block by block, stop at the first mismatch and
                       remember that offset (resume_at);
  phase 2 (append)   : truncate the partial to resume_at and append the rest,
                       hashing the source stream as it goes.

Together both phases read the source exactly once, so the full-source MD5 falls
out for free. The target MD5 is then computed from the local copy only (no USB).
"""
from pathlib import Path
import hashlib, json, os, time, traceback

SRC = Path('/mnt/uxo_external_ro/datasets/uxo-dataset2024/data_processed.7z')
DST = Path('/mnt/d/pby/data_processed.7z')
PART = DST.with_suffix('.7z.partial')
STATE = Path('/mnt/d/pby/.uxo-transfer/status.json')
EXPECTED = '2b9ef16c763a6964c608ed99a9cd1edb'
SIZE = 61513277947
BLOCK = 16 * 1024 * 1024
START = time.time()


def status(phase, done, **extra):
    row = {
        'phase': phase,
        'bytes_done': done,
        'total_bytes': SIZE,
        'elapsed_seconds': round(time.time() - START, 1),
        'source': str(SRC),
        'target': str(DST),
        'expected_md5': EXPECTED,
        'source_deleted': False,
        **extra,
    }
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(row, indent=2), encoding='utf-8')
    tmp.replace(STATE)
    print(json.dumps(row), flush=True)


def hash_file(path, phase):
    h = hashlib.md5()
    done = 0
    last = 0
    with path.open('rb', buffering=0) as stream:
        while block := stream.read(BLOCK):
            h.update(block)
            done += len(block)
            if time.time() - last >= 30:
                status(phase, done)
                last = time.time()
    return h.hexdigest()


def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    status('checking_paths', 0)

    if DST.exists():
        assert DST.stat().st_size == SIZE, 'Existing destination has wrong size; not overwritten'
        actual = hash_file(DST, 'verifying_existing_target')
        assert actual == EXPECTED, 'Existing destination MD5 differs; not overwritten'
        status('complete', SIZE, target_md5=actual, target_verified=True)
        return

    assert SRC.stat().st_size == SIZE, 'Source size differs'
    existing = PART.stat().st_size if PART.exists() else 0
    assert existing <= SIZE, 'Partial file too large; retained without overwriting'
    print(f'partial={existing}', flush=True)

    digest = hashlib.md5()
    done = 0
    last = 0
    resume_at = existing

    # Phase 1: compare the existing partial against the source, read-only.
    if existing:
        with SRC.open('rb', buffering=0) as source, PART.open('rb', buffering=0) as partial:
            while done < existing:
                want = min(BLOCK, existing - done)
                sblk = source.read(want)
                pblk = partial.read(len(sblk))
                if not sblk:
                    raise AssertionError('Source ended before partial length')
                digest.update(sblk)
                if pblk != sblk:
                    resume_at = done
                    status('partial_mismatch', done, resume_at=resume_at)
                    print(f'mismatch at {done}', flush=True)
                    break
                done += len(sblk)
                if time.time() - last >= 30:
                    status('comparing_existing_partial', done)
                    last = time.time()
        print(f'compare pass done, verified={done} resume_at={resume_at}', flush=True)
        status('compared', done, resume_at=resume_at)

    # Phase 2: truncate to the last consistent offset and append the remainder.
    with SRC.open('rb', buffering=0) as source, PART.open('r+b' if PART.exists() else 'w+b',
                                                          buffering=0) as target:
        source.seek(resume_at)
        target.seek(resume_at)
        target.truncate(resume_at)
        done = resume_at
        while block := source.read(BLOCK):
            digest.update(block)
            target.write(block)
            done += len(block)
            if time.time() - last >= 30:
                status('copying_and_hashing_source', done)
                last = time.time()
        target.flush()
        os.fsync(target.fileno())

    actual = digest.hexdigest()
    assert done == SIZE and actual == EXPECTED, 'Source MD5 mismatch; partial retained'
    status('source_verified', done, source_md5=actual)

    target_md5 = hash_file(PART, 'verifying_target')
    assert target_md5 == EXPECTED, 'Target MD5 mismatch; partial retained'
    assert not DST.exists(), 'Destination appeared; not overwritten'
    PART.rename(DST)
    status('complete', SIZE, source_md5=actual, target_md5=target_md5,
           source_verified=True, target_verified=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        status('failed', 0, error=repr(error))
        traceback.print_exc()
        raise
