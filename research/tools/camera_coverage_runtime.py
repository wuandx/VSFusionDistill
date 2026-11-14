"""Camera-only augmentation and fixed-compute sampler for recording coverage controls."""
import numpy as np
import torch
import cv2
from mmcv.transforms import BaseTransform
from mmengine.registry import DATA_SAMPLERS, TRANSFORMS
from torch.utils.data import Sampler

@DATA_SAMPLERS.register_module()
class CameraCoverageSampler(Sampler):
    def __init__(self,dataset,shuffle=True,seed=0,num_samples=2472):
        self.dataset=dataset;self.shuffle=shuffle;self.seed=seed;self.num_samples=num_samples;self.epoch=0
        assert len(dataset)>=num_samples
    def __len__(self):return self.num_samples
    def set_epoch(self,epoch):self.epoch=epoch
    def __iter__(self):
        g=torch.Generator();g.manual_seed(self.seed+self.epoch)
        ids=torch.randperm(len(self.dataset),generator=g).tolist() if self.shuffle else list(range(len(self.dataset)))
        return iter(ids[:self.num_samples])

def geometry(image,boxes,flip,scale,tx,ty):
    h,w=image.shape[:2];b=np.asarray(boxes,dtype=np.float32).copy()
    if flip:
        image=image[:,::-1].copy();b[:,0]=w-b[:,0]-b[:,2]
    # Scale about image center, then translate; boxes must remain inside the frame.
    ox=(1-scale)*w/2+tx;oy=(1-scale)*h/2+ty
    b[:,:2]=b[:,:2]*scale+np.array([ox,oy]);b[:,2:]*=scale
    assert np.all(b[:,:2]>=0) and np.all(b[:,0]+b[:,2]<=w+1e-4) and np.all(b[:,1]+b[:,3]<=h+1e-4)
    out=cv2.warpAffine(image,np.array([[scale,0,ox],[0,scale,oy]],dtype=np.float32),(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(114,114,114))
    return out,b.tolist()

@TRANSFORMS.register_module()
class CameraCoverageAugment(BaseTransform):
    def transform(self,results):
        assert results.get('img_sonar') is None
        image=results['img_camera'];boxes=results['boxes_camera'];h,w=image.shape[:2]
        flip=np.random.random()<.5
        # Reject spatial draws that would create a new clipped box. Existing truncation is retained.
        for _ in range(20):
            scale=float(np.random.uniform(.9,1.1));tx=float(np.random.uniform(-.05,.05)*w);ty=float(np.random.uniform(-.05,.05)*h)
            try:out,b=geometry(image,boxes,flip,scale,tx,ty);break
            except AssertionError:continue
        else:out,b=geometry(image,boxes,flip,1.,0.,0.)
        contrast=float(np.random.uniform(.8,1.2));brightness=float(np.random.uniform(-20.,20.))
        results['img_camera']=np.clip(out.astype(np.float32)*contrast+brightness,0,255).astype(np.uint8)
        results['boxes_camera']=b
        return results
