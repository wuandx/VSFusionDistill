"""Verify frame-start mismatch using source-video timestamps and decoded pixels.

Diagnostic output only. All boxes, original images, splits and labels untouched.
"""
from pathlib import Path
from fractions import Fraction
import json
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "复现/camera-baseline/annotation-issues/sd-fhd"
VIDEOS = ROOT / "DataSet/camera_annotation_trace"
RAW = Path(r"D:\pby\uxo-full\extracted\recordings\15cm_mortar")
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)


def cmd(args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def video_data(path):
    meta = json.loads(cmd(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    stream = next(x for x in meta["streams"] if x["codec_type"] == "video")
    raw = cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vf", "scale=160:90", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"])
    assert len(raw) // (90*160) == int(stream['nb_frames']), "decoder frame count must match original stream"
    frames = np.frombuffer(raw, dtype=np.uint8).reshape((-1, 90*160)).astype(np.float32)
    frames -= frames.mean(axis=1)[:, None]
    return meta, stream, frames


def exact_frame(path, index):
    raw = cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vf", f"select=eq(n\\,{index}),scale=640:360", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
    return Image.frombytes("RGB", (640,360), raw)


def panel(image, box, title, second):
    image = image.copy()
    ImageDraw.Draw(image).rectangle(box, outline="#ffcb3b", width=2)
    out = Image.new("RGB", (640,416), "#101821")
    out.paste(image, (0,56));draw=ImageDraw.Draw(out)
    draw.text((8,8), title, font=FONT, fill="white")
    draw.text((8,31), second, font=FONT, fill="#ffcb3b")
    return out


def main():
    traces = json.loads((OUT / "frame-correspondence.json").read_text(encoding="utf-8"))
    results = []
    for trace in traces:
        rec = trace["recording"];name = Path(trace["clip"]).name
        sdpath, fhdpath = VIDEOS / "sd_clips" / name, VIDEOS / "fhd_clips" / name
        sm, ss, sd = video_data(sdpath);fm, fs, fhd = video_data(fhdpath)
        (OUT / (rec + "-fhd-ffprobe.json")).write_text(json.dumps(fm, indent=2), encoding="utf-8")
        fps = float(Fraction(ss["avg_frame_rate"]))
        assert ss["avg_frame_rate"] == fs["avg_frame_rate"]
        delta_seconds = float(fs["start_time"]) - float(ss["start_time"])
        delta = round(delta_seconds * fps)
        indices = np.arange(0, len(fhd), 10)
        indices = indices[(indices+delta >= 0) & (indices+delta < len(sd))]
        timed = np.mean((fhd[indices]-sd[indices+delta])**2, axis=1)
        plain = indices[indices < len(sd)]
        same_index = np.mean((fhd[plain]-sd[plain])**2, axis=1)
        queries=[]
        for row in trace["frames"]:
            frame=row["frame"]
            with Image.open(RAW/rec/'gopro'/f'{frame:04d}.jpg') as im:
                q=np.asarray(im.convert('L').resize((160,90),Image.Resampling.BICUBIC),dtype=np.float32).reshape(-1)
            q-=q.mean()
            mse=np.mean((fhd-q[None,:])**2,axis=1)
            best=int(np.argmin(mse))
            queries.append({"frame":frame,"best_fhd_index":best,"time_rule_index":row['predicted_sd_index'],"best_fhd_minus_rule":best-row['predicted_sd_index'],"best_sd_index":row['best_sd_index'],"best_sd_minus_best_fhd":row['best_sd_index']-best,"fhd_match_centered_mse":float(mse[best])})
        images=[]
        for native_frame in ([822] if rec.endswith('101622') else [223,309]):
            query=next(r for r in queries if r['frame']==native_frame)
            k=query['time_rule_index'];aligned=k-delta
            label=json.loads((RAW/rec/'labels'/f'{native_frame:04d}.json').read_text())
            box=[label[x] for x in ['x_min','y_min','x_max','y_max']]
            assert 0<=k<len(sd) and 0<=k<len(fhd) and 0<=aligned<len(fhd)
            panes=[panel(exact_frame(sdpath,k),box,f'SD source frame {k}',f'native box, unchanged; ARIS frame {native_frame}'),
                   panel(exact_frame(fhdpath,k),box,f'FHD source, same frame index {k}','different moment; same native box'),
                   panel(exact_frame(fhdpath,aligned),box,f'FHD at same timestamp, index {aligned}','DIAGNOSTIC ONLY; same native box')]
            canvas=Image.new('RGB',(1920,416))
            for n,p in enumerate(panes):canvas.paste(p,(640*n,0))
            fn=f'{rec}_{native_frame:04d}-source-timing-proof.jpg';canvas.save(OUT/fn,quality=94);images.append(fn)
        results.append({"recording":rec,"sd":{"start_time":ss['start_time'],"duration":ss['duration'],"frames":len(sd)},"fhd":{"start_time":fs['start_time'],"duration":fs['duration'],"frames":len(fhd)},"fps":fps,"fhd_start_minus_sd_seconds":delta_seconds,"fhd_start_minus_sd_frames_rounded":delta,"frame_count_sd_minus_fhd":len(sd)-len(fhd),"aligned_pairs_sampled":len(indices),"timestamp_aligned_mse_median":float(np.median(timed)),"same_index_mse_median":float(np.median(same_index)),"fhd_jpg_queries":queries,"images":images,"limits":"This establishes a difference in published clip temporal coverage and inherited JPEG/label association, not which historical editing command caused it; no annotations or dataset roles changed."})
        print(json.dumps({k:results[-1][k] for k in ['recording','fhd_start_minus_sd_seconds','fhd_start_minus_sd_frames_rounded','frame_count_sd_minus_fhd','timestamp_aligned_mse_median','same_index_mse_median']},ensure_ascii=False),flush=True)
        del sd,fhd
    (OUT/'source-timing-verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
