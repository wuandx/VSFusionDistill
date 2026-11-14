"""Read-only complete identity/pixel/format/provenance verification of exported copy."""
from prepare_sonar_visible_candidates import *
from collections import Counter
def main():
    out=OUT/'export';m=read(out/'manifest.json');c=read(out/'annotations.coco.json')
    allow={r['sample']:r for r in read(ROOT/'DataSet/camera_temporal_all/manifest-resolved.json')['items']}
    assert len(m)==len(c['images'])==len(c['annotations']) and len({r['sample'] for r in m})==len(m)
    maxdelta=0.;truncated=0
    for r,im,ann in zip(m,c['images'],c['annotations']):
        sid=r['sample'];assert sid in allow and allow[sid].get('paired_role') in (None,'train','val','val_id')
        assert r['recording']==allow[sid]['recording'] and r['category']==allow[sid]['category']
        a=arr(r['source']);h,w=a.shape;x0,y0,x1,y1=r['bbox_xyxy'];assert 0<=x0<x1<=w and 0<=y0<y1<=h
        assert sha(r['source'])==r['source_sha256'] and sha(out/r['export_image'])==r['export_image_sha256']
        assert np.array_equal(np.array(Image.open(out/r['export_image'])),a)
        assert [im['height'],im['width']]==[h,w] and im['file_name']==r['export_image'] and ann['image_id']==im['id']
        assert ann['bbox']==[x0,y0,x1-x0,y1-y0] and ann['area']==(x1-x0)*(y1-y0)
        tokens=(out/r['yolo_file']).read_text().split();cls=int(tokens[0]);cx,cy,bw,bh=map(float,tokens[1:])
        assert cls+1==ann['category_id'] and c['categories'][cls]['name']==r['category']
        back=np.array([(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h]);delta=float(np.abs(back-r['bbox_xyxy']).max());maxdelta=max(maxdelta,delta);assert delta<1e-6
        ds=r['ds'];assert ds and sha(OUT/ds['response_file'])==ds['response_sha256']
        if r['annotation_author']=='deepseek-v4.1-flash':assert ds['confidence']=='high' and ds['choice']!='unresolved' and r['bbox_xyxy']==ds['bbox_xyxy']
        else:
            d=r['assistant_review'];assert d and d['final_xyxy']==r['bbox_xyxy'];assert sha(OUT/'review/sheets'/(d['review_sheet_sha256']+'.jpg'))==d['review_sheet_sha256']
        q=r['qa'];assert q['decision']=='pass' and sha(OUT/'ds_qa'/f"r{r['overview_index']:02d}.jpg")==q['sheet_sha256']
        assert r['training_split'] is None and not r['expert_verified'];truncated+=r['truncated']
        Image.open(out/'previews'/f'{sid}.jpg').verify()
    assert {p.stem for p in (out/'images').glob('*.png')}=={r['sample'] for r in m}
    assert {p.stem for p in (out/'labels').glob('*.txt')}=={r['sample'] for r in m}
    report=dict(status='passed',samples=len(m),source_and_png_pixel_exact=True,all_allowlisted=True,coco_yolo_roundtrip_max_abs_pixels=maxdelta,review_and_response_hashes_verified=True,truncated_boundary_count=truncated,by_author=dict(Counter(r['annotation_author'] for r in m)),scope='Complete numerical and provenance check, not an independent expert semantic review')
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    # Representative delivery sheet from actual exported previews.
    selected=[]
    for cat in ['100lbs_aircraft_bomb','mortar_shell','incindiary_grenade']:
        rows=[r for r in m if r['category']==cat];selected+= [rows[len(rows)//3],rows[2*len(rows)//3]]
    canvas=Image.new('RGB',(1200,1050),'white')
    for k,r in enumerate(selected):
        t=tile(r,box=r['bbox_xyxy'],size=(600,350));canvas.paste(t,((k%2)*600,(k//2)*350))
    canvas.save(out/'examples.jpg',quality=96)
    print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
