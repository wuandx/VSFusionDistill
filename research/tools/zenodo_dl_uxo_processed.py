#!/usr/bin/env python3
"""从 Zenodo 下载 data_processed.7z（61,513,277,947 B）并校验 MD5。

- 多线程 HTTP Range 分块下载，断点续传（状态 json）
- 落盘目标 <out>.partial，MD5 通过后才改名 <out>
- 只读源站，不改动官方内容；不解压
"""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request

URL = "https://zenodo.org/api/records/13778485/files/data_processed.7z/content"
EXPECT_SIZE = 61513277947
EXPECT_MD5 = "2b9ef16c763a6964c608ed99a9cd1edb"
PROXY = "http://127.0.0.1:7897"

OUT = r"D:\pby\data_processed.7z"
PART = OUT + ".partial"
WORKDIR = r"D:\pby\.uxo-transfer"
STATE = os.path.join(WORKDIR, "zenodo_dl_state.json")
STATUS = os.path.join(WORKDIR, "zenodo_dl_status.json")
LOG = os.path.join(WORKDIR, "zenodo_dl.log")

CHUNK = 8 * 1024 * 1024
THREADS = 24

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
_lock = threading.Lock()
_loglock = threading.Lock()


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    with _loglock:
        print(line, flush=True)
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def build_opener():
    handlers = []
    if PROXY:
        handlers.append(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def fetch_range(opener, start, end, tries=8):
    want = end - start + 1
    last = None
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                URL,
                headers={
                    "Range": "bytes=%d-%d" % (start, end),
                    "User-Agent": "dsh-zenodo-dl/1.0",
                    "Accept-Encoding": "identity",
                },
            )
            with opener.open(req, timeout=180) as resp:
                if resp.status not in (200, 206):
                    raise RuntimeError("HTTP %s" % resp.status)
                data = resp.read()
            if len(data) != want:
                raise RuntimeError("short read %d/%d" % (len(data), want))
            return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError("range %d-%d failed: %r" % (start, end, last))


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    nchunks = (EXPECT_SIZE + CHUNK - 1) // CHUNK
    done = set()
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                st = json.load(f)
            if st.get("size") == EXPECT_SIZE:
                done = set(st.get("done", []))
                log("resume: %d/%d chunks already done" % (len(done), nchunks))
        except Exception as exc:  # noqa: BLE001
            log("state unreadable (%r), starting fresh" % (exc,))

    fresh = not os.path.exists(PART)
    f = open(PART, "r+b" if not fresh else "w+b")
    if fresh:
        f.truncate(EXPECT_SIZE)
        log("created %s sized %d" % (PART, EXPECT_SIZE))
    else:
        f.seek(0, os.SEEK_END)
        cur = f.tell()
        if cur != EXPECT_SIZE:
            f.truncate(EXPECT_SIZE)
        log("existing partial %d bytes, done chunks %d" % (cur, len(done)))

    pending = [i for i in range(nchunks) if i not in done]
    log("total %d chunks, pending %d, threads %d" % (nchunks, len(pending), THREADS))

    qlock = threading.Lock()
    counter = {"bytes": len(done) * CHUNK, "n": len(done)}
    if len(done) == nchunks:
        counter["bytes"] = EXPECT_SIZE
    stop = threading.Event()
    errors = []

    # progress thread
    def reporter():
        t0 = time.time()
        start_bytes = counter["bytes"]
        last_bytes = counter["bytes"]
        last_t = t0
        while not stop.is_set():
            time.sleep(5)
            with qlock:
                b = min(counter["bytes"], EXPECT_SIZE)
                n = counter["n"]
            now = time.time()
            inst = (b - last_bytes) / max(now - last_t, 0.001)
            avg = (b - start_bytes) / max(now - t0, 0.001)
            rate = max(inst, 1.0)
            remain = EXPECT_SIZE - b
            eta = remain / rate if rate > 1e5 else 0
            payload = {
                "bytes_done": b,
                "chunks_done": n,
                "chunks_total": nchunks,
                "pct": round(100.0 * b / EXPECT_SIZE, 3),
                "speed_MBps_avg": round(avg / 1e6, 3),
                "speed_MBps_recent": round(inst / 1e6, 3),
                "eta_hours": round(eta / 3600.0, 2),
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            try:
                tmp = STATUS + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False)
                os.replace(tmp, STATUS)
            except Exception:
                pass
            last_bytes, last_t = b, now

    rep = threading.Thread(target=reporter, daemon=True)
    rep.start()

    def save_state():
        tmp = STATE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"size": EXPECT_SIZE, "done": sorted(done)}, fh)
        os.replace(tmp, STATE)

    state_lock = threading.Lock()

    def worker():
        opener = build_opener()
        while True:
            with qlock:
                if not pending:
                    return
                idx = pending.pop()
            start = idx * CHUNK
            end = min(start + CHUNK, EXPECT_SIZE) - 1
            try:
                data = fetch_range(opener, start, end)
            except Exception as exc:  # noqa: BLE001
                with qlock:
                    errors.append((idx, repr(exc)))
                log("chunk %d failed: %r" % (idx, exc))
                continue
            with _lock:
                f.seek(start)
                f.write(data)
                f.flush()
            with qlock:
                counter["bytes"] += len(data)
                counter["n"] += 1
                done.add(idx)
                if counter["n"] % 128 == 0:
                    save_state()
            del data

    t_start = time.time()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stop.set()
    rep.join(timeout=10)
    f.flush()
    os.fsync(f.fileno())
    save_state()
    log("all workers finished in %.1f s, chunks done %d/%d, errors %d"
        % (time.time() - t_start, counter["n"], nchunks, len(errors)))

    if errors:
        log("FATAL: %d chunks failed; rerun to resume" % len(errors))
        for idx, msg in errors[:10]:
            log("  chunk %d: %s" % (idx, msg))
        f.close()
        return 2

    f.close()
    size = os.path.getsize(PART)
    log("size %d (expected %d)" % (size, EXPECT_SIZE))
    if size != EXPECT_SIZE:
        log("FATAL: size mismatch")
        return 3

    log("computing md5 ...")
    h = hashlib.md5()
    with open(PART, "rb") as fh:
        while True:
            blk = fh.read(16 * 1024 * 1024)
            if not blk:
                break
            h.update(blk)
    digest = h.hexdigest()
    log("md5 %s (expected %s)" % (digest, EXPECT_MD5))
    if digest != EXPECT_MD5:
        log("FATAL: md5 mismatch, keeping %s" % PART)
        return 4
    os.replace(PART, OUT)
    log("OK: %s verified, renamed from partial" % OUT)
    try:
        os.remove(STATE)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
