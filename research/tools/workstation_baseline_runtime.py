import numpy as np
from mmcv.transforms import BaseTransform
from mmengine.registry import TRANSFORMS

@TRANSFORMS.register_module()
class WorkflowFixedCanvas(BaseTransform):
    """Pad packed CHW only; preserve unpadded img_shape and scale_factor."""
    def transform(self, results):
        for side in ['camera','sonar']:
            key='img_'+side
            a=results.get(key)
            if a is None: continue
            c,h,w=a.shape
            assert h<=640 and w<=640
            out=np.full((c,640,640),114,dtype=a.dtype)
            out[:,:h,:w]=a
            results[key]=out
        return results
