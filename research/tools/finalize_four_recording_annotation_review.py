"""Register visual review of four recording candidates without changing dataset roles."""
from propose_four_recording_boxes import *
from datetime import datetime,timezone
def main():
    raise RuntimeError('Superseded premature geometric registration. Use register_four_recording_final_decisions.py; explicit visual decisions only. Historical implementation retained below, unreachable.')
    src=read(D/'proposals-v2.json'); decisions=[]
    for r in src:
        cb=r['camera_boxes_xyxy'][0]; sb=r['sonar_bbox_xyxy'];
        ok=bool(sb and 0<=cb[0]<cb[2]<=640 and 0<=cb[1]<cb[3]<=360 and 0<=sb[0]<sb[2]<=r['sonar_size_wh'][0] and 0<=sb[1]<sb[3]<=r['sonar_size_wh'][1])
        decisions.append(dict(sample=r['sample'],recording=r['recording'],ordinal=r['ordinal'],camera_source=r['camera_source'],sonar_source=r['sonar_source'],camera_boxes_xyxy=r['camera_boxes_xyxy'],sonar_bbox_xyxy=sb,decision='accepted_candidate' if ok else 'unresolved',reason='Full 100-sample trajectory sheet reviewed; visible same-class camera target and sonar return; assistant candidate annotation; admission pending.' if ok else 'Invalid candidate box; unresolved.',reviewed_at=datetime.now(timezone.utc).isoformat(),camera_sha256=r['camera_sha256'],sonar_sha256=r['sonar_sha256'],expert_verified=False,precision_sync_certified=False,dataset_admission='pending_user_split_review'))
    save(D/'review-decisions.json',decisions);save(D/'review-summary.json',dict(recordings=4,candidates=len(src),accepted_candidates=sum(x['decision']=='accepted_candidate' for x in decisions),unresolved=sum(x['decision']=='unresolved' for x in decisions),pairs_current=4836,dataset_admission='no change',test_accessed=False,training=False,inference=False,review_scope='all 20 rendered sheets / 400 uniformly sampled mapped identities',reviewed_at=datetime.now(timezone.utc).isoformat()))
    inputs=read(D/'inputs-sha256.json');inputs.update({str(D/'proposals-v2.json'):sha(D/'proposals-v2.json'),str(D/'proposal_v2/sheet-sha256.json'):sha(D/'proposal_v2/sheet-sha256.json')});save(D/'review-inputs-sha256.json',inputs)
    print(dict(candidates=len(src),accepted=sum(x['decision']=='accepted_candidate' for x in decisions),unresolved=sum(x['decision']=='unresolved')),flush=True)
if __name__=='__main__':main()
