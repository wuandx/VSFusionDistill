"""Explicit corrections after actual full-sheet visual review; retain earlier error."""
from propose_four_recording_boxes import *
import shutil
def main():
    for name in ['review-decisions.json','review-summary.json','review-inputs-sha256.json']:
        p=D/name
        if p.exists():shutil.copy2(p,D/(p.stem+'-premature-geometric-registration'+p.suffix))
    items=read(D/'proposals-v2.json');events=[]
    for r in items:
        rec=r['recording'][-6:];j=r['ordinal'];before=dict(camera=list(r['camera_boxes_xyxy'][0]),sonar=list(r['sonar_bbox_xyxy']) if r['sonar_bbox_xyxy'] else None)
        if rec=='124241' and 58<=j<=66:r['camera_boxes_xyxy'][0][1]-=8
        if rec=='124440' and 54<=j<=59:r['camera_boxes_xyxy'][0][1]-=8
        if rec=='124440' and 95<=j<=99:r['camera_boxes_xyxy'][0][2]+=12
        if rec=='125924' and 4<=j<=7:r['sonar_bbox_xyxy'][1]-=15
        after=dict(camera=r['camera_boxes_xyxy'][0],sonar=r['sonar_bbox_xyxy'])
        if before!=after:events.append(dict(sample=r['sample'],ordinal=j,recording=r['recording'],before=before,after=after,reason='visible dark camera rim omitted by color mask, or disconnected upper sonar echo omitted; explicit visual expansion for re-review'))
        r['decision']='unresolved' if rec=='124440' and 17<=j<=23 else 'reviewed_pending_export'
        r['reason']='weak sonar response or fragmented/empty candidate; retained unresolved, no negative label' if r['decision']=='unresolved' else 'both visible targets and boxes reviewed on full trajectory sheets; corrected frames re-review pending'
    render(items,'corrected_v3');save(D/'proposals-v3.json',items);save(D/'explicit-corrections.json',events)
    save(D/'registration-correction.json',dict(correction='Earlier registration incorrectly treated geometric validity as full visual acceptance and prematurely stated 400/400. Earlier files retained; superseded by actual explicit review. Seven124440 identities unresolved; corrections require re-view.',superseded=['review-decisions.json','review-summary.json'],unresolved_samples=[r['sample'] for r in items if r['decision']=='unresolved']))
    print(dict(corrections=len(events),unresolved=sum(r['decision']=='unresolved' for r in items)))
if __name__=='__main__':main()
