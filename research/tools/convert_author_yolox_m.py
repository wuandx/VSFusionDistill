import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
import torch
from mmdet.models.backbones import CSPDarknet
from mmdet.models.necks import YOLOXPAFPN

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assets/checkpoints'
REF=ROOT/'assets/yolox_author_reference'

def main():
    torch.set_num_threads(4)
    source=BASE/'yolox_m_author.pth'
    original=torch.load(source,map_location='cpu',weights_only=False)['model']
    b=CSPDarknet(deepen_factor=.67,widen_factor=.75)
    n=YOLOXPAFPN([192,384,768],192,num_csp_blocks=2)
    converted={}; mapping={}
    def csp(k):
        return k.replace('.main_conv.','.conv1.').replace('.short_conv.','.conv2.').replace('.final_conv.','.conv3.').replace('.blocks.','.m.')
    for k,v in b.state_dict().items():
        old=re.sub(r'^stage([1-4])',lambda m:'dark'+str(int(m[1])+1),k)
        old='backbone.backbone.'+csp(old)
        assert original[old].shape==v.shape,(k,old)
        converted['backbone.'+k]=original[old]; mapping['backbone.'+k]=old
    names={'reduce_layers.0':'backbone.lateral_conv0','reduce_layers.1':'backbone.reduce_conv1','top_down_blocks.0':'backbone.C3_p4','top_down_blocks.1':'backbone.C3_p3','downsamples.0':'backbone.bu_conv2','downsamples.1':'backbone.bu_conv1','bottom_up_blocks.0':'backbone.C3_n3','bottom_up_blocks.1':'backbone.C3_n4','out_convs.0':'head.stems.0','out_convs.1':'head.stems.1','out_convs.2':'head.stems.2'}
    for k,v in n.state_dict().items():
        prefix=next(p for p in names if k.startswith(p+'.'))
        old=csp(names[prefix]+k[len(prefix):])
        assert original[old].shape==v.shape,(k,old)
        converted['neck.'+k]=original[old]; mapping['neck.'+k]=old
    b.load_state_dict({k[len('backbone.'):]:v for k,v in converted.items() if k.startswith('backbone.')},strict=True)
    n.load_state_dict({k[len('neck.'):]:v for k,v in converted.items() if k.startswith('neck.')},strict=True)
    # Fetch only official reference modules for numerical conversion control.
    for folder in [REF/'yolox',REF/'yolox/models']:
        folder.mkdir(parents=True,exist_ok=True); (folder/'__init__.py').write_text('')
    for name in ['network_blocks.py','darknet.py','yolo_pafpn.py']:
        dest=REF/'yolox/models'/name
        if not dest.exists():
            urllib.request.urlretrieve('https://raw.githubusercontent.com/Megvii-BaseDetection/YOLOX/main/yolox/models/'+name,dest)
    sys.path.insert(0,str(REF))
    from yolox.models.yolo_pafpn import YOLOPAFPN
    from yolox.models.network_blocks import BaseConv
    ref=YOLOPAFPN(depth=.67,width=.75)
    ref.load_state_dict({k[len('backbone.'):]:v for k,v in original.items() if k.startswith('backbone.')},strict=True)
    stems=torch.nn.ModuleList([BaseConv(c,192,1,1) for c in [192,384,768]])
    stems.load_state_dict({k[len('head.stems.'):]:v for k,v in original.items() if k.startswith('head.stems.')},strict=True)
    # Author Exp.get_model applies these BN settings after construction.
    for model in [ref,stems]:
        for module in model.modules():
            if isinstance(module,torch.nn.BatchNorm2d):
                module.eps=.001; module.momentum=.03
    ref.eval(); stems.eval(); b.eval(); n.eval()
    torch.manual_seed(2026)
    x=torch.rand(1,3,128,192)*255
    with torch.no_grad():
        expected=[s(f) for s,f in zip(stems,ref(x))]; actual=n(b(x))
    errors=[float((a-e).abs().max()) for a,e in zip(actual,expected)]
    for a,e in zip(actual,expected): torch.testing.assert_close(a,e,rtol=1e-4,atol=1e-4)
    output=BASE/'yolox_m_coco_backbone_neck.pth'
    torch.save(dict(state_dict=converted),output)
    report=dict(passed=True,source_url='https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.pth',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),converted_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),tensor_count=len(converted),forward_max_abs_errors=errors,mapping=mapping,reference_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (REF/'yolox/models').glob('*.py')})
    (BASE/'yolox_m_conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Converted and numerically verified',len(converted),errors)

if __name__=='__main__': main()
