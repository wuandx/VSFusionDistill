"""175905 visual boundary edits from inspected sheets, immutable re-render."""
import sys
sys.path[:0]=['tools','tools/_sonar_audit_deps']
import review_paired_local as r
import json
from pathlib import Path
oldroot=r.ROOT/'DataSet/paired_assistant_bomb_primary_return'
strong=r.ROOT/'DataSet/paired_assistant_bomb_remaining_strong'
boxes={}
for p in (oldroot/'2023-09-20_175905').glob('page-*.json'):
    old=json.loads(p.read_text('utf-8'))['items']
    es={v['sample']:v for v in json.loads((strong/'2023-09-20_175905'/p.name).read_text('utf-8'))['items']}
    for v in old:
        n=v['review_ordinal']; b=v['proposed_box'].copy();eb=es[v['sample']]['proposed_box']
        # Explicit visually chosen lower boundary offsets; review again after rendering.
        if n<=12 or 100<=n<=112:b[3]=eb[3]+24
        elif n<=20 or 113<=n<=119:b[3]=eb[3]+14
        elif n<=29:b[3]=eb[3]-3
        elif n<=65:b[3]=b[3]-13
        else:b[3]=eb[3]+14
        boxes[v['sample']]=b
orig=r.e.body_options
def edited(row,a,shuffle=False):
    opts=orig(row,a,shuffle=False)
    opts['H']=boxes[row['sample']]
    return opts
r.e.body_options=edited
r.OUT=r.ROOT/'DataSet/paired_assistant_bomb_visual_revision'
r.save(r.OUT/'visual-proposed-boxes.json',boxes)
if __name__=='__main__':r.build('2023-09-20_175905',0,120,'H')
