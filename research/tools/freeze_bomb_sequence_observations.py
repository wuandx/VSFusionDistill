"""Freeze assistant observations made on unboxed bomb frames, before any new fit."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/_sonar_audit_deps'))
import numpy as np
from PIL import Image,ImageDraw
from check_official_sonar_coordinates import Geometry,load_beam_tables,beam_count
OUT=ROOT/'DataSet/sonar_bomb_sequence_observations'

# Fixed manual readouts from no-overlay full raw gain1/3 and sequence views.
# Each triplet is raw column edge coordinate, near-side main-echo range-bin interval.
CURVES={
 622:[(20.5,246,253),(28.5,224,231),(36.5,204,211),(44.5,183,192),
      (52.5,171,178),(60.5,162,168),(68.5,156,162),(76.5,152,158),
      (84.5,148,154),(92.5,139,145),(100.5,138,144),(108.5,145,153)],
 981:[(12.5,187,194),(20.5,181,187),(28.5,179,184),(36.5,178,183),
      (44.5,178,183),(52.5,178,184),(60.5,179,185),(68.5,180,186),
      (76.5,182,188),(84.5,184,190),(92.5,186,193),(100.5,189,196),
      (108.5,192,199),(116.5,195,203)],
 1336:[(12.5,97,104),(20.5,94,100),(28.5,95,102),(36.5,97,104),
       (44.5,100,108),(52.5,105,113),(60.5,115,125),(68.5,133,144),
       (76.5,160,173),(84.5,190,204),(92.5,225,240)]}

# Visible coherent echo envelopes, NOT complete physical silhouette/GT boxes.
BOXES={622:[10,138,118,292],626:[10,138,118,290],630:[10,139,118,287],
       973:[0,178,128,217],977:[0,178,128,217],981:[0,178,128,217],
       985:[0,178,128,219],989:[0,178,128,221],
       1328:[5,94,104,261],1332:[5,94,102,258],1336:[5,94,101,257]}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    result=OUT/'observations.json';assert not result.exists(),'Never revise frozen observations after fitting'
    source=OUT/'source-provenance.json';pro=json.loads(source.read_text(encoding='utf-8'));tables=load_beam_tables();frames=[]
    for rec in pro['records']:
        f=rec['aris_frame'];g=Geometry(rec['metadata_row'],tables[beam_count(rec['metadata_row']['PingMode'])]);center=rec['center']
        points=[]
        for u,v0,v1 in CURVES.get(f,[]):
            v=(v0+v1)/2;r,b=g.raw_edges_to_points(np.array([u,v]));ri,bi=g.raw_edges_to_points(np.array([[u-1,v0],[u+1,v1]]))
            points.append(dict(raw_uv_edge=[u,v],tolerance_uv=[1,(v1-v0)/2],near_range_bin_interval=[v0,v1],
                               range_m=float(r),beam_table_angle_deg=float(b),range_interval_m=ri.tolist(),beam_interval_deg=bi.tolist(),
                               confidence='medium' if v1-v0>8 else 'medium_high',
                               meaning='near-side boundary of main coherent echo; candidate for acoustic envelope approximation, not a known mesh point or target long axis'))
        if center==622:
            lateral={'left':[8,20],'right':[110,120]};clipped=[]
            note='Strong curved body-like return persists over 3 neighboring frames. Far-range taper at small raw columns is weak, so its end is only a visible echo interval. Dark interior and trailing diffuse scatter do not provide exclusion evidence.'
            uncertain=[{'raw_xyxy_edge':[8,265,30,300],'reason':'weak far-range taper; cannot identify physical tail/nose endpoint'},{'raw_xyxy_edge':[45,180,100,245],'reason':'diffuse backscatter; not a hard silhouette or exclusion constraint'}]
            edge_intervals={'left':[8,20],'top':[137,143],'right':[110,120],'bottom':[278,300]}
        elif center==981:
            lateral={'left':None,'right':None};clipped=['left_possible','right_observed']
            note='Main coherent near-range return spans almost all beams and persists over five neighbors. Right continuation reaches raw field of view; left onset is weak near the field edge. Neither side is a certified full-object endpoint. Separate returns at larger range are excluded from the body-envelope box without asserting their physical cause.'
            uncertain=[{'raw_xyxy_edge':[0,189,14,218],'reason':'left FOV/low-signal onset; complete boundary unknown'},{'raw_xyxy_edge':[118,195,128,224],'reason':'right continuation touches FOV boundary; physical endpoint unknown'},{'raw_xyxy_edge':[30,220,90,255],'reason':'separate lower patches may be support/background; not used as body envelope'}]
            edge_intervals={'left':None,'top':[177,184],'right':None,'bottom':[208,224]}
        else:
            lateral={'left':[3,14],'right':[91,106]};clipped=[]
            note='Near-range bulb-like return and curved taper persist over three neighbors. Far-range taper is dim and blends into noise, so the visible right/bottom edge is weak. Surface brightness does not reveal hidden geometry.'
            uncertain=[{'raw_xyxy_edge':[86,225,106,270],'reason':'weak far-range taper; physical endpoint remains unknown'},{'raw_xyxy_edge':[38,130,82,215],'reason':'dim interior/trailing return; no exclusion constraint'}]
            edge_intervals={'left':[3,14],'top':[92,101],'right':[91,106],'bottom':[245,270]}
        frames.append(dict(sample=rec['sample'],aris_frame=f,recording=rec['recording'],role='fit_observation_development',center_window=center,
                           visible_echo_bbox_raw_xyxy_edge=BOXES[f],visible_echo_bbox_edge_intervals=edge_intervals,
                           bbox_status='assistant candidate enclosing visible coherent body-like echo; not full physical GT',
                           lateral_visible_echo_edge_intervals_raw_u=lateral,possible_fov_truncation=clipped,
                           physical_boundary_intervals={'left':None,'right':None,'top':None,'bottom':None},physical_head_tail_identity=None,
                           near_echo_curve_points=points,points=points,uncertain_regions=uncertain,notes=note,
                           camera_role='identity/support context only; no camera bbox or projection used',
                           raw_source_sha256=rec['raw_source_sha256'],camera_source_sha256=rec['camera_source_sha256'],approved_for_training=False))
    payload=dict(status='frozen unboxed assistant observations before new bomb model fitting',frames=frames,
                 coordinate_convention='native raw pixel-edge xy; actual shape 780x128; pixel center (column+0.5,row+0.5)',
                 method='Visual raw gain1/3, source-compatible full polar2 and paired SD images; local sequence continuity; manually sampled near-side echo intervals at three centers. No peak fitting, model, old labels or check data.',
                 caveat='Near-return envelope is an acoustic observation; identifying it with nearest mesh surface is a separate modeling assumption. Visible echo bboxes are not certified complete target bboxes.',
                 hard_exclusion_constraints=False,old_boxes_or_new_fit_viewed=False,check_recording_viewed=False,
                 source_provenance_sha256=sha(source),preregistration_sha256=sha(ROOT/'experiment/sonar-bomb-sequence-observation-plan.md'),
                 observation_script_sha256=sha(Path(__file__)),history='Center frames have prior development exposure; this is not blind expert annotation.')
    result.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    # Observation-only overlays for verification; never draw a model projection.
    for frame in frames:
        sid=frame['sample'];a=np.asarray(Image.open(OUT/(sid+'-raw.png')));a=np.minimum(a.astype(np.uint16)*3,255).astype(np.uint8)
        im=Image.new('RGB',(1120,790),'white');im.paste(Image.fromarray(a[90:310]).convert('RGB').resize((1024,660),Image.Resampling.NEAREST),(65,55));d=ImageDraw.Draw(im)
        d.text((8,8),sid+' | observation only | orange visible echo candidate; pink near-return intervals',fill='black')
        def xy(p):return (65+p[0]*8,55+(p[1]-90)*3)
        for x in range(0,129,8):
            xp=65+x*8;d.line((xp,55,xp,715),fill=(55,65,70));d.text((xp-5,38),str(x),fill='black')
        for y in range(90,311,20):
            yp=55+(y-90)*3;d.line((65,yp,1089,yp),fill=(55,65,70));d.text((22,yp-5),str(y),fill='black')
        x0,y0,x1,y1=frame['visible_echo_bbox_raw_xyxy_edge'];d.rectangle((*xy((x0,y0)),*xy((x1,y1))),outline=(255,170,0),width=2)
        for p in frame['points']:
            u,v=p['raw_uv_edge'];lo,hi=p['near_range_bin_interval'];d.line((*xy((u,lo)),*xy((u,hi))),fill=(255,50,190),width=3);xx,yy=xy((u,v));d.ellipse((xx-3,yy-3,xx+3,yy+3),fill=(255,50,190))
        im.save(OUT/(sid+'-observations.png'))
    print(json.dumps({'observations_sha256':sha(result),'frames':len(frames),'center_curve_counts':{f['sample']:len(f['points']) for f in frames if f['points']}},indent=2))

if __name__=='__main__':main()
