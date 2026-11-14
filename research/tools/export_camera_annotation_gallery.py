"""Render existing camera GT for manual review, with no inference or GT edits.

Scope: all current paired train/val/val_id samples, plus every labelled native
camera frame in approved current/partial-development recordings. Test images are not opened.
Mixed COCO annotation objects are decoded only for explicitly allowed IDs.
"""
from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import csv
import hashlib
import html
import json
import re
import time
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(r"D:\pby\uxo-full")
PAIRED = DATA / "paired"
RAW = DATA / "extracted/recordings"
OUT = ROOT / "DataSet/camera_annotation_review"
GROUPS = {"100lbs_bomb": "100lbs_aircraft_bomb",
          "100lbs_bomb_(floor)": "100lbs_aircraft_bomb",
          "15cm_mortar": "mortar_shell", "20lbs_incendiary": "incindiary_grenade"}
COLORS = {"paired": "#18d96b", "native": "#35b6ff"}
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
SMALL_FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def inventory():
    split_path = DATA / "repro/frame_split.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    allowed = set(split["recordings"]["train"]) | set(split["recordings"]["val"])
    current_recordings = set(allowed)
    partial_manifest = ROOT / "DataSet/camera_recording_disjoint_v1/recording_manifest.csv"
    partial_roles = {}
    if partial_manifest.is_file():
        with partial_manifest.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["split"] not in {"train", "val"}:
                    raise ValueError("Partial manifest contains an unapproved role; stop")
                partial_roles[row["recording"]] = row["split"]
        allowed.update(partial_roles)
    meta = {}
    split_counts = Counter()
    skipped_test = 0
    with (PAIRED / "frame_meta.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["split"] == "test":
                skipped_test += 1
                continue
            if row["split"] not in {"train", "val", "val_id"}:
                raise ValueError("unexpected role")
            assert row["recording"] in allowed
            meta[int(row["camera_image_id"])] = row
            split_counts[row["split"]] += 1

    # This converter's annotations are flat objects (bbox/segmentation arrays,
    # no nested object values). Skip disallowed objects before JSON decoding.
    text = (PAIRED / "camera.json").read_text(encoding="utf-8")
    section = text.split('"annotations":', 1)[1].split('"categories":', 1)[0]
    annotations = {}
    for match in re.finditer(r"\{[^{}]*\}", section):
        raw = match.group(0)
        key = re.search(r'"image_id"\s*:\s*(\d+)', raw)
        if key and int(key.group(1)) in meta:
            ann = json.loads(raw)
            annotations.setdefault(ann["image_id"], []).append(ann)
    del text, section
    category_names = {1: "100lbs_aircraft_bomb", 2: "incindiary_grenade", 3: "mortar_shell"}
    items = []
    for image_id, row in meta.items():
        anns = annotations.get(image_id, [])
        assert anns, f"allowed image missing GT: {image_id}"
        source = PAIRED / "images/camera" / (row["sample_id"] + ".jpg")
        assert source.is_file(), str(source)
        items.append({"dataset": "paired", "id": "paired/" + row["sample_id"],
                      "sample": row["sample_id"], "recording": row["recording"],
                      "frame": int(row["frame_idx"]), "split": row["split"],
                      "category": category_names[anns[0]["category_id"]],
                      "source": str(source), "source_url": source.as_uri(),
                      "annotation_source": str(PAIRED / "camera.json"),
                      "annotation_ids": [a["id"] for a in anns],
                      "boxes": [a["bbox"] for a in anns], "box_format": "xywh",
                      "annotation_policy": "existing paired camera GT; unchanged"})
    found_recordings = set()
    for group, category in GROUPS.items():
        for recording in sorted(allowed):
            rec = RAW / group / recording
            if not rec.is_dir():
                continue
            found_recordings.add(recording)
            for label in sorted((rec / "labels").glob("*.json")):
                if not label.stem.isdigit():
                    continue
                source = rec / "gopro" / (label.stem + ".jpg")
                if not source.is_file():
                    continue
                raw = label.read_bytes()
                ann = json.loads(raw)
                assert ann["class"] == category
                x1, y1, x2, y2 = [float(ann[k]) * 3 for k in ("x_min", "y_min", "x_max", "y_max")]
                sample = recording + "_" + label.stem
                items.append({"dataset": "native", "id": "native/" + sample,
                              "sample": sample, "recording": recording, "frame": int(label.stem),
                              "split": "native_full_sequence", "category": category,
                              "source": str(source), "source_url": source.as_uri(),
                              "annotation_source": str(label),
                              "annotation_sha256": hashlib.sha256(raw).hexdigest(),
                              "boxes": [[x1, y1, x2 - x1, y2 - y1]], "box_format": "xywh",
                              "annotation_policy": "native SD coordinates multiplied by 3; no clipping or correction"})
    assert found_recordings == allowed
    items.sort(key=lambda r: (r["dataset"], r["category"], r["recording"], r["frame"]))
    for item in items:
        folder = f"{item['dataset']}/{item['category']}/{item['recording']}"
        item["image"] = f"annotated/{folder}/{item['sample']}.jpg"
        item["thumb"] = f"thumbnails/{folder}/{item['sample']}.jpg"
    provenance = {"source_split": str(split_path), "source_split_sha256": digest(split_path),
                  "paired_camera_json_sha256": digest(PAIRED / "camera.json"),
                  "approved_recordings": sorted(allowed), "current_paired_split_counts": dict(split_counts),
                  "current_paired_recordings": sorted(current_recordings),
                  "additional_partial_development_recordings": sorted(allowed - current_recordings),
                  "partial_manifest": str(partial_manifest),
                  "partial_manifest_sha256": digest(partial_manifest) if partial_manifest.is_file() else None,
                  "excluded_test_metadata_rows": skipped_test,
                  "datasets": dict(Counter(i["dataset"] for i in items)),
                  "native_missing_image_labels": "labels without corresponding shipped JPG are not rendered",
                  "test_images_opened": 0, "model_inference": False,
                  "access_note": "Earlier head inspection of the single-line camera.json read the complete mixed annotation file. This is recorded, not described as zero test-annotation access. Export decodes allowed GT objects only; test images are excluded."}
    return items, provenance


def render(item):
    target, thumb = OUT / item["image"], OUT / item["thumb"]
    if target.exists() and thumb.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(item["source"]) as opened:
        im = opened.convert("RGB")
    width, height = im.size
    if item["dataset"] == "native" and (width, height) != (1920, 1080):
        raise ValueError(f"Native x3 assumption invalid for {item['source']}: {im.size}")
    banner = 48
    canvas = Image.new("RGB", (width, height + banner), "#101821")
    canvas.paste(im, (0, banner))
    draw = ImageDraw.Draw(canvas)
    color = COLORS[item["dataset"]]
    draw.text((12, 10), f"{item['dataset']} GT | {item['category']} | {item['sample']} | {item['split']}", font=FONT, fill="white")
    for box in item["boxes"]:
        x, y, w, h = box
        if w <= 0 or h <= 0:
            raise ValueError(f"Invalid GT box: {item['id']}")
        # Draw only on the image region; renderer boundary clipping is not a
        # label correction. Original numeric box is retained in manifest.
        overlay = ImageDraw.Draw(im)
        overlay.rectangle((x, y, x + w, y + h), outline=color, width=4)
        label = f"GT x={x:g} y={y:g} w={w:g} h={h:g}"
        tx, ty = max(1, min(width - 430, x)), max(1, min(height - 24, y - 25))
        overlay.rectangle((tx, ty, tx + 430, ty + 24), fill="#101821")
        overlay.text((tx + 3, ty + 1), label, font=SMALL_FONT, fill=color)
    canvas.paste(im, (0, banner))
    temporary = target.with_suffix(".tmp")
    canvas.save(temporary, format="JPEG", quality=90, subsampling=0)
    temporary.replace(target)
    canvas.thumbnail((480, 282), Image.Resampling.LANCZOS)
    temporary = thumb.with_suffix(".tmp")
    canvas.save(temporary, format="JPEG", quality=80)
    temporary.replace(thumb)
    return True


PAGE = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Camera 标注逐帧检查</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10151d;color:#e9eef7;font:15px system-ui,sans-serif}header{position:sticky;top:0;background:#18212f;z-index:3;padding:16px 24px;border-bottom:1px solid #364256}h1{margin:0 0 8px;font-size:23px}p{margin:7px 0;color:#abbcd0}select,input,button{background:#253247;color:#fff;border:1px solid #536581;border-radius:5px;padding:8px;margin:4px}button{cursor:pointer}a{color:#86c8ff}.controls{display:flex;flex-wrap:wrap;align-items:center}.grid{padding:18px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}.card{background:#1a2535;border:1px solid #394b65;border-radius:7px;overflow:hidden;cursor:pointer}.card img{width:100%;display:block}.caption{padding:8px;font-size:12px;word-break:break-all}.status{float:right;color:#ffda70}.pager{text-align:center;padding:15px}.modal{display:none;position:fixed;inset:0;z-index:10;background:#0c1119;overflow:auto;padding:12px}.modal.open{display:block}.viewer{display:grid;grid-template-columns:1fr 1fr;gap:12px}.viewer img{width:100%;cursor:zoom-in;background:#000}.viewer img.zoom{width:auto;max-width:none}.pane{overflow:auto}.bar{position:sticky;top:0;background:#162133;padding:8px;z-index:11}.details{white-space:pre-wrap;font-size:13px;color:#bdcee1}.badge{background:#283a54;padding:5px;border-radius:4px}label{color:#bdcee1}@media(max-width:900px){.viewer{grid-template-columns:1fr}}</style>
<header><h1>Camera 标注逐帧检查</h1><p>已有GT可视化，无模型预测、无标签修正。paired：当前训练数据中的实际框（绿）；native：__RECORDINGS__条允许检查录音的完整原始标注×3（蓝），含未完成开发副本的额外录音。test图像未导出。</p>
<div class="controls"><label>数据 <select id="dataset"><option value="paired">当前 paired：__PAIRED_COUNT__张</option><option value="native">原始完整序列：__NATIVE_COUNT__张</option><option value="">两套全部（含重复帧）</option></select></label><select id="category"><option value="">全部类别</option></select><select id="recording"><option value="">全部录音</option></select><select id="split"><option value="">全部角色</option><option>train</option><option>val</option><option>val_id</option><option>native_full_sequence</option></select><input id="search" placeholder="输入帧号或sample_id"><select id="review"><option value="">全部检查状态</option><option value="unseen">尚未标记</option><option value="bad">仅疑似问题</option></select><button onclick="downloadReviews()">导出检查CSV</button><span id="counts"></span></div>
<p>点击图片并排查看原图/标注图；← →翻帧，Esc返回，G标正常，B标疑似问题。检查标记保存在本机浏览器，请导出CSV留档。</p></header>
<div class="pager"><button onclick="pageBy(-1)">上一页</button><span id="pageInfo"></span><button onclick="pageBy(1)">下一页</button></div><main id="grid" class="grid"></main><div class="pager"><button onclick="pageBy(-1)">上一页</button><button onclick="pageBy(1)">下一页</button></div>
<div class="modal" id="modal"><div class="bar"><button onclick="closeViewer()">返回网格</button><button onclick="step(-1)">← 上一张</button><button onclick="step(1)">下一张 →</button><button onclick="mark('正常')">正常 G</button><button onclick="mark('疑似框偏小')">框偏小</button><button onclick="mark('疑似框偏移')">框偏移</button><button onclick="mark('疑似漏框/框不全')">漏框/框不全</button><button onclick="mark('不确定')">不确定 B</button><button onclick="mark('')">清除标记</button><input id="note" placeholder="可填写具体问题" oninput="saveNote()"><span id="viewerCount"></span></div><h3 id="title"></h3><div class="viewer"><div class="pane"><p>原图（未加框）</p><img id="original" onclick="this.classList.toggle('zoom')"></div><div class="pane"><p>现有标注（点击可按原尺寸放大）</p><img id="annotated" onclick="this.classList.toggle('zoom')"></div></div><pre id="details" class="details"></pre></div>
<script src="gallery-data.js"></script><script>
const $=id=>document.getElementById(id),KEY='uxo-camera-annotation-review-v1';let marks={};try{marks=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}let filtered=[],page=0,current=-1;const size=48;
function persist(){try{localStorage.setItem(KEY,JSON.stringify(marks))}catch(e){alert('无法保存浏览器检查记录，请及时导出CSV')}}
function options(id,values){for(const value of values){const o=document.createElement('option');o.value=value;o.textContent=value;$(id).appendChild(o)}}
options('category',[...new Set(ITEMS.map(x=>x.category))].sort());options('recording',[...new Set(ITEMS.map(x=>x.recording))].sort());
function filter(){const d=$('dataset').value,c=$('category').value,r=$('recording').value,s=$('split').value,q=$('search').value.trim().toLowerCase(),v=$('review').value;filtered=ITEMS.filter(x=>(!d||x.dataset===d)&&(!c||x.category===c)&&(!r||x.recording===r)&&(!s||x.split===s)&&(!q||x.sample.toLowerCase().includes(q))&&(!v||(v==='unseen'?!marks[x.id]?.status:!!marks[x.id]?.status&&marks[x.id].status!=='正常')));page=0;draw()}
function draw(){const grid=$('grid');grid.replaceChildren();$('counts').textContent=`匹配 ${filtered.length} 张 / 已标记 ${Object.keys(marks).filter(k=>marks[k].status).length} 张`;$('pageInfo').textContent=`第 ${page+1} / ${Math.max(1,Math.ceil(filtered.length/size))} 页`;filtered.slice(page*size,(page+1)*size).forEach((x,k)=>{const card=document.createElement('article');card.className='card';const im=document.createElement('img');im.loading='lazy';im.src=x.thumb;const caption=document.createElement('div');caption.className='caption';caption.textContent=`${x.category} | ${x.recording}\n${x.sample} · ${x.dataset}/${x.split} · ${marks[x.id]?.status||'未标记'}`;card.append(im,caption);card.onclick=()=>show(page*size+k);grid.append(card)})}
function pageBy(n){page=Math.max(0,Math.min(Math.max(0,Math.ceil(filtered.length/size)-1),page+n));draw();window.scrollTo(0,0)}
function show(i){if(!filtered.length)return;current=Math.max(0,Math.min(filtered.length-1,i));const x=filtered[current];$('modal').classList.add('open');$('title').textContent=`${x.category} | ${x.sample} | ${x.dataset}/${x.split} | ${marks[x.id]?.status||'未标记'}`;$('original').src=x.source_url;$('annotated').src=x.image;$('original').classList.remove('zoom');$('annotated').classList.remove('zoom');$('note').value=marks[x.id]?.note||'';$('viewerCount').textContent=`${current+1}/${filtered.length}`;$('details').textContent=`GT来源：${x.annotation_source}\n处理规则：${x.annotation_policy}\n原图像素坐标 bbox (x,y,w,h)：${JSON.stringify(x.boxes)}\n显示图上方增加48px标题条，图像内容及框坐标未缩放/修正。`}
function step(n){show(current+n)}function closeViewer(){$('modal').classList.remove('open');draw()}function mark(status){const x=filtered[current];marks[x.id]={status,note:$('note').value};if(!status&&!marks[x.id].note)delete marks[x.id];persist();show(current)}function saveNote(){const x=filtered[current];marks[x.id]={status:marks[x.id]?.status||'',note:$('note').value};persist()}
function csvCell(x){return '"'+String(x??'').replaceAll('"','""')+'"'}function downloadReviews(){const lines=[['dataset','category','recording','sample_id','status','note','annotation_source','bbox_xywh']];for(const x of ITEMS){const m=marks[x.id];if(m&&(m.status||m.note))lines.push([x.dataset,x.category,x.recording,x.sample,m.status,m.note,x.annotation_source,JSON.stringify(x.boxes)])}const blob=new Blob(['\ufeff'+lines.map(r=>r.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='camera-annotation-review.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
for(const id of ['dataset','category','recording','split','review'])$(id).onchange=filter;$('search').oninput=filter;document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;if(!$('modal').classList.contains('open'))return;if(e.key==='ArrowRight'){e.preventDefault();step(1)}if(e.key==='ArrowLeft'){e.preventDefault();step(-1)}if(e.key==='Escape')closeViewer();if(e.key.toLowerCase()==='g')mark('正常');if(e.key.toLowerCase()==='b')mark('不确定')});filter();
</script></html>'''


def contact_sheet(items, name):
    canvas = Image.new("RGB", (1440, 3 * 320), "#101821")
    draw = ImageDraw.Draw(canvas)
    for i, item in enumerate(items):
        with Image.open(OUT / item["image"]) as image:
            image.thumbnail((480, 282), Image.Resampling.LANCZOS)
            x, y = (i % 3) * 480, (i // 3) * 320
            canvas.paste(image, (x, y))
            draw.text((x + 5, y + 285), item["sample"], font=SMALL_FONT, fill="white")
            draw.text((x + 5, y + 305), item["category"], font=SMALL_FONT, fill=COLORS[item["dataset"]])
    canvas.save(OUT / name, quality=90)


def main():
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    items, provenance = inventory()
    counts = dict(Counter(i["dataset"] for i in items))
    print(json.dumps({"status": "inventory", "counts": counts, "recordings": len(provenance['approved_recordings'])}), flush=True)
    atomic_json(OUT / "progress.json", {"status": "rendering", "total": len(items), "done": 0})
    failures = []
    rendered = 0
    def safe_render(item):
        try:
            return render(item), None
        except Exception as error:
            return False, {"id": item["id"], "error": repr(error)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for done, (created, error) in enumerate(pool.map(safe_render, items), 1):
            rendered += int(created)
            if error:
                failures.append(error)
            if done % 500 == 0 or done == len(items):
                atomic_json(OUT / "progress.json", {"status": "rendering", "total": len(items), "done": done, "failed": len(failures)})
                print(f"Rendered/checked {done}/{len(items)}; errors={len(failures)}", flush=True)
    if failures:
        atomic_json(OUT / "errors.json", failures)
        raise RuntimeError(f"{len(failures)} images failed; see errors.json")
    atomic_json(OUT / "manifest.json", {"provenance": provenance, "items": items})
    (OUT / "gallery-data.js").write_text("const ITEMS=" + json.dumps(items, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    page = PAGE.replace('__RECORDINGS__', str(len(provenance['approved_recordings']))).replace('__PAIRED_COUNT__', f"{counts['paired']:,}").replace('__NATIVE_COUNT__', f"{counts['native']:,}")
    (OUT / "index.html").write_text(page, encoding="utf-8")
    with (OUT / "image-index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["id", "dataset", "category", "recording", "frame", "sample", "split", "image", "source", "annotation_source", "boxes"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow({**item, "boxes": json.dumps(item["boxes"])})
    preview = []
    for category in sorted(set(i["category"] for i in items)):
        candidates = [i for i in items if i["dataset"] == "paired" and i["category"] == category]
        recordings = sorted(set(i["recording"] for i in candidates))
        for recording in [recordings[0], recordings[len(recordings)//2], recordings[-1]]:
            group = [i for i in candidates if i["recording"] == recording]
            preview.append(group[len(group)//2])
    contact_sheet(preview, "overview.jpg")
    atomic_json(OUT / "verification.json", {"annotated_images": len(items), "thumbnails": len(items), "missing_outputs": sum(not (OUT / i["image"]).is_file() or not (OUT / i["thumb"]).is_file() for i in items), "errors": failures, "counts": counts, "preview_ids": [i["id"] for i in preview]})
    summary = {"status": "complete", "total": len(items), "datasets": counts,
               "newly_rendered": rendered, "elapsed_seconds": round(time.time()-started, 1),
               "test_images_opened": 0, "errors": 0, "gallery": str(OUT / "index.html")}
    atomic_json(OUT / "progress.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
