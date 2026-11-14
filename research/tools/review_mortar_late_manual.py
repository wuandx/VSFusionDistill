"""Human-anchor box proposals, never automatic annotation acceptance."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent/'_sonar_audit_deps'))
import review_paired_local as r
e=r.e
ROOT=r.ROOT/'DataSet/paired_assistant_mortar_late_component/2023-09-21_105017'
items={x['review_ordinal']:x for p in ROOT.glob('page-*.json') for x in e.read(p)['items']}
anchors={0:[5,217,92,377],12:[9,227,92,378],13:[9,227,90,372],17:[5,228,70,316],18:[6,228,65,303],24:[6,227,71,313],30:[6,228,75,320],36:[8,229,69,308],42:[14,238,65,309],88:[18,232,80,350],92:[16,232,82,363],99:[16,231,86,375]}
keys=sorted(anchors)
samples=[int(items[k]['sample'].rsplit('_',1)[1]) for k in keys]
base=e.body_options
def proposals(row,a,shuffle=False):
    opts=base(row,a,shuffle=False)
    n=int(row['sample'].rsplit('_',1)[1])
    if row['recording']=='2023-09-21_105017' and (n<=samples[keys.index(42)] or n>=samples[keys.index(88)]):
        opts['H']=[int(round(float(e.np.interp(n,samples,[anchors[k][i] for k in keys])))) for i in range(4)]
    return opts
e.body_options=proposals
r.OUT=r.ROOT/'DataSet/paired_assistant_mortar_late_manual'
if __name__=='__main__':
    r.OUT.mkdir(parents=True,exist_ok=True)
    e.save(r.OUT/'proposal-method.json',{'method':'assistant visual coordinate anchors, sample-index linear interpolation, each candidate needs new visual review','anchors':{items[k]['sample']:anchors[k] for k in keys},'precision_sync_certified':False})
    r.build('2023-09-21_105017',int(sys.argv[1]),int(sys.argv[2]),'H')
