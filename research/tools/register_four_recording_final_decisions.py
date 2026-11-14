"""Register explicit visual decisions after review; never accept from geometry."""
from propose_four_recording_boxes import *
from datetime import datetime, timezone

ACCEPTED = {
    RECS[0]: set(range(100)),
    RECS[1]: set(range(100)),
    RECS[2]: set(range(17)) | set(range(24, 100)),
    RECS[3]: set(range(100)),
}


def main():
    src = read(D/'proposals-v3.json')
    sheets = {Path(x['path']).as_posix(): x['sha256'] for x in read(D/'corrected_v3/sheet-sha256.json')}
    assert len(src) == 400 and len(sheets) == 20
    assert all(sha(D/p) == h for p, h in sheets.items())
    prior={x['sample']:x for x in read(D/'proposals-v2.json')}
    # Reconstruct diffs independently: the intermediate log used a shared list
    # reference for sonar boxes and missed four in-place edits.
    edits=[]
    for r in src:
        p=prior[r['sample']]
        before=dict(camera=p['camera_boxes_xyxy'][0],sonar=p['sonar_bbox_xyxy'])
        after=dict(camera=r['camera_boxes_xyxy'][0],sonar=r['sonar_bbox_xyxy'])
        if before!=after:
            edits.append(dict(sample=r['sample'],recording=r['recording'],ordinal=r['ordinal'],
                before=before,after=after,reason='Explicit visible camera rim or detached upper sonar echo correction, then re-viewed.'))
    save(D/'explicit-corrections-final.json',edits)
    corrected={x['sample'] for x in edits}
    assert len(corrected)==24
    stamp = datetime.now(timezone.utc).isoformat()
    decisions = []
    for r in src:
        accepted = r['ordinal'] in ACCEPTED[r['recording']]
        assert r['decision'] == ('reviewed_pending_export' if accepted else 'unresolved')
        # Registration time is not a fabricated per-sheet viewing time.
        rec, page = r['recording'], r['ordinal']//20
        initial = 'proposal_v1' if page == 0 and rec != RECS[3] else 'proposal_v2'
        evidence = [dict(sheet=str(D/initial/f'{rec}-{page}.jpg'),
                         sha256=sha(D/initial/f'{rec}-{page}.jpg'),
                         scope='both modalities, full image and box crops')]
        if r['sample'] in corrected:
            evidence.append(dict(sheet=str(D/r['sheet']), sha256=sheets[r['sheet']],
                                 scope='explicitly corrected boundaries re-viewed'))
        decisions.append(dict(sample=r['sample'], recording=rec, ordinal=r['ordinal'],
            decision='accepted' if accepted else 'unresolved', author='assistant',
            reason=('Visible camera target and sonar echo reviewed; corrected boundaries re-viewed where applicable.'
                    if accepted else 'Weak, fragmented or missing sonar return at ordinals 17–23; retained unresolved, never a negative sample.'),
            camera_boxes_xyxy=r['camera_boxes_xyxy'], sonar_bbox_xyxy=r['sonar_bbox_xyxy'],
            final_sheet=str(D/r['sheet']), final_sheet_sha256=sheets[r['sheet']],
            visual_evidence=evidence, explicit_boundary_correction=r['sample'] in corrected,
            registered_at=stamp, expert_verified=False, precision_sync_certified=False,
            annotation_origin='assistant_new_visible_target_annotation',
            dataset_admission='train' if accepted else 'excluded_unresolved'))
    assert sum(x['decision']=='accepted' for x in decisions) == 393
    save(D/'review-decisions-final.json', decisions)
    summary = dict(candidates=400, accepted=393, unresolved=7, recordings=4,
        per_recording={rec:dict(accepted=len(ids), unresolved=100-len(ids)) for rec,ids in ACCEPTED.items()},
        corrected_samples=len(corrected), full_reviewed_identities=400,
        registered_at=stamp, earlier_registration_superseded=True,
        expert_verified=False, precision_sync_certified=False, training=False, inference=False)
    save(D/'review-summary-final.json', summary)
    save(D/'review-events-final.json', dict(registration_time=stamp,
        initial_review='400 identities actually viewed on trajectory sheets; not inferred from valid geometry',
        corrected_pages_re_viewed=['124241 pages 2,3', '124440 pages 2,4', '125924 page 0'],
        correction='Earlier 400/400 report and 399 geometric registrations are superseded; earlier files retained.',
        decisions=decisions))
    correction=read(D/'registration-correction.json')
    correction.update(final_decisions='review-decisions-final.json', final_summary='review-summary-final.json',
                      final_accepted=393, final_unresolved=7, corrected_pages_re_viewed=True)
    save(D/'registration-correction.json', correction)
    print(summary)


if __name__ == '__main__':
    main()
