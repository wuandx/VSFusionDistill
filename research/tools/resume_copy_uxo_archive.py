#!/usr/bin/env python3
"""Resumable copy of the UXO archive from the read-only Btrfs external disk to D:/pby.

Design (2026-11-10, after the 5-7 MB/s sustained / device-dropout findings):
  * single sequential reader, 64 MiB blocks (small blocks measured ~1.3 MB/s, large ~400 MB/s burst)
  * commit point every 256 MiB: flush + fsync + atomic state file, so a dropout costs <= 256 MiB
  * on first start with an existing partial and no state file, compare the last 512 MiB of the
    partial against the source and truncate at the first mismatch (torn tail from the crashed run)
  * no source-side MD5: the deliverable is verified by hashing the LOCAL copy and requiring the
    official MD5, which by definition proves the copy is bit-identical to the official archive
  * read/write errors are retried; persistent failure exits with the committed state saved
"""
import hashlib
import json
import os
import sys
import time

SRC = "/mnt/uxo_external_ro/datasets/uxo-dataset2024/data_processed.7z"
DST = "/mnt/d/pby/data_processed.7z.partial"
FINAL = "/mnt/d/pby/data_processed.7z"
STATE_DIR = "/mnt/d/pby/.uxo-transfer"
STATE = os.path.join(STATE_DIR, "append_state.json")
STATUS = os.path.join(STATE_DIR, "status.json")
LOG = os.path.join(STATE_DIR, "append.log")

EXPECTED_MD5 = "2b9ef16c763a6964c608ed99a9cd1edb"
SRC_SIZE = 61513277947

BLOCK = 64 * 1024 * 1024
COMMIT_EVERY = 256 * 1024 * 1024
TAIL_CHECK = 512 * 1024 * 1024
RETRIES = 3


def log(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def status(phase, done=0, total=SRC_SIZE, started=None, extra=None):
    now = time.time()
    data = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "phase": phase,
        "bytes_done": done,
        "bytes_total": total,
        "percent": round(done * 100.0 / total, 3) if total else 0,
        "elapsed_seconds": round(now - started, 1) if started else 0,
        "source": SRC,
        "target": DST,
        "pid": os.getpid(),
    }
    if started and done:
        rate = done / max(now - started, 1e-9)
        data["rate_MBps"] = round(rate / 1e6, 2)
        data["eta_seconds"] = round((total - done) / max(rate, 1), 0)
    if extra:
        data.update(extra)
    write_json(STATUS, data)


def read_block(fh, offset, size):
    last = None
    for attempt in range(RETRIES):
        try:
            fh.seek(offset)
            buf = fh.read(size)
            if len(buf) != size:
                raise IOError("short read at %d: %d != %d" % (offset, len(buf), size))
            return buf
        except OSError as exc:
            last = exc
            log("read error at offset %d (attempt %d/%d): %s" % (offset, attempt + 1, RETRIES, exc))
            time.sleep(5)
    raise last


def tail_check(src_fh, dst_fh, existing):
    """Return the byte offset from which the copy must be redone."""
    floor = max(0, existing - TAIL_CHECK)
    log("tail check: comparing %d..%d of existing partial against source" % (floor, existing))
    step = 8 * 1024 * 1024
    off = floor
    while off < existing:
        n = min(step, existing - off)
        a = read_block(src_fh, off, n)
        dst_fh.seek(off)
        b = dst_fh.read(n)
        if a != b:
            for i in range(0, n, 4096):
                if a[i:i + 4096] != b[i:i + 4096]:
                    bad = off + i
                    log("tail check: first mismatch at %d (partial extends to %d)" % (bad, existing))
                    return bad
            return off
        off += n
    log("tail check: existing %d bytes all match source" % existing)
    return existing


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    started = time.time()

    if not os.path.exists(SRC):
        log("FATAL source not mounted: %s" % SRC)
        status("failed", extra={"error": "source_missing"})
        return 3

    src_size = os.path.getsize(SRC)
    if src_size != SRC_SIZE:
        log("WARNING source size %d differs from expected %d" % (src_size, SRC_SIZE))

    committed = 0
    if os.path.exists(STATE):
        with open(STATE) as fh:
            state = json.load(fh)
        committed = int(state.get("committed_bytes", 0))
        log("resume: state file says committed=%d" % committed)
    elif os.path.exists(DST):
        existing = os.path.getsize(DST)
        log("no state file, existing partial=%d" % existing)
        if existing >= src_size:
            log("existing partial is already full length; skipping straight to verification")
            committed = src_size
        else:
            with open(SRC, "rb", buffering=0) as sfh, open(DST, "r+b") as dfh:
                committed = tail_check(sfh, dfh, existing)
            log("tail check decided committed=%d" % committed)
            write_json(STATE, {"committed_bytes": committed, "note": "after tail check"})

    if not os.path.exists(DST):
        if committed:
            log("state claimed committed=%d but partial is gone; restarting from 0" % committed)
        committed = 0
    else:
        cur = os.path.getsize(DST)
        if cur < committed:
            log("partial (%d) is shorter than committed (%d); backing off to %d" % (cur, committed, cur))
            committed = cur
        elif cur != committed:
            log("truncating partial from %d to committed=%d" % (cur, committed))
            os.truncate(DST, committed)

    if committed < src_size:
        if not os.path.exists(DST):
            log("creating new partial at committed=0")
            open(DST, "wb").close()
        status("copying", committed, src_size, started)
        with open(SRC, "rb", buffering=0) as sfh, open(DST, "r+b") as dfh:
            pos = committed
            next_commit = min(((pos // COMMIT_EVERY) + 1) * COMMIT_EVERY, src_size)
            window_start, window_bytes = time.time(), 0
            while pos < src_size:
                n = min(BLOCK, src_size - pos)
                buf = read_block(sfh, pos, n)
                dfh.seek(pos)
                dfh.write(buf)
                pos += n
                window_bytes += n
                if pos >= next_commit or pos == src_size:
                    dfh.flush()
                    os.fsync(dfh.fileno())
                    committed = pos
                    write_json(STATE, {"committed_bytes": committed,
                                       "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
                    now = time.time()
                    applied = pos
                    status("copying", applied, src_size, started)
                    window_start, window_bytes = now, 0
                    next_commit = min(((pos // COMMIT_EVERY) + 1) * COMMIT_EVERY, src_size)
                    log("committed %d / %d (%.2f%%)" % (pos, src_size, pos * 100.0 / src_size))
            dfh.flush()
            os.fsync(dfh.fileno())

    size = os.path.getsize(DST) if os.path.exists(DST) else 0
    if size != src_size:
        log("FATAL size mismatch after copy: %d != %d" % (size, src_size))
        status("failed", size, src_size, started, {"error": "size_mismatch"})
        return 4

    log("copy complete (%d bytes); hashing local copy" % size)
    status("verifying", 0, size, started)
    md5 = hashlib.md5()
    done = 0
    with open(DST, "rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            md5.update(chunk)
            done += len(chunk)
            if done % (1024 * 1024 * 1024) < 8 * 1024 * 1024:
                log("hashed %d / %d (%.1f%%)" % (done, size, done * 100.0 / size))
                status("verifying", done, size, started)
    digest = md5.hexdigest()
    log("md5(local copy) = %s" % digest)

    if digest != EXPECTED_MD5:
        log("MD5 MISMATCH: expected %s" % EXPECTED_MD5)
        status("failed", size, size, started,
               {"error": "md5_mismatch", "md5_actual": digest, "md5_expected": EXPECTED_MD5})
        return 5

    if os.path.exists(FINAL):
        log("FATAL final file already exists: %s" % FINAL)
        return 6
    os.replace(DST, FINAL)
    try:
        os.remove(STATE)
    except OSError:
        pass
    log("DONE: %s verified md5=%s" % (FINAL, digest))
    status("complete", size, size, started, {"md5": digest, "file": FINAL})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # keep the committed checkpoint for the next attempt
        log("ABORTED: %r" % (exc,))
        status("failed", extra={"error": repr(exc)})
        raise
