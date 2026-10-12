"""Geometry QA retaining subpixel silhouette ambiguity as explicit evidence.

Rendered depth is discontinuous at silhouettes. A 0.001-pixel ray perturbation
may switch surfaces while the camera pose is correct to float precision. Only
independently ray-confirmed alternatives qualify; arbitrary edge pixels do not.
No depth values are changed or discarded by this check.
"""
import numpy as np
from yopo_repro.forest import ray_depth


def assess_depth(depth,position,rotation,scene,pixels,index):
    pixels=np.asarray(pixels)
    def rays(p):
        return np.column_stack([np.ones(len(p)),-(p[:,0]+.5-80)/80,-(p[:,1]+.5-45)/80])@rotation.T
    expected=ray_depth(position,rays(pixels),scene)
    actual=depth[pixels[:,1],pixels[:,0]]
    errors=np.abs(expected-actual)
    ambiguous=[];unresolved=[]
    offsets=np.array([(u,v) for u in [-.001,0,.001] for v in [-.001,0,.001]])
    for j in np.flatnonzero(errors>.1):
        alternatives=ray_depth(position,rays(pixels[j][None]+offsets),scene)
        closest=float(np.min(abs(alternatives-actual[j])))
        row={'pixel':pixels[j].tolist(),'expected_m':float(expected[j]),'rendered_m':float(actual[j]),
             'raw_error_m':float(errors[j]),'closest_subpixel_error_m':closest,'alternative_span_m':float(np.ptp(alternatives))}
        if np.ptp(alternatives)>.1 and closest<=.01:ambiguous.append(row)
        else:unresolved.append(row)
    return {'index':int(index),'checks':len(pixels),'p99_m':float(np.percentile(errors,99)),
            'max_m':float(errors.max()),'status':'passed' if not unresolved and len(ambiguous)<=2 else 'failed',
            'qa_rule':'ray_match_with_explicit_0.001_pixel_silhouette_bound_v1',
            'ambiguous_pixels':ambiguous,'unresolved_pixels':unresolved}
