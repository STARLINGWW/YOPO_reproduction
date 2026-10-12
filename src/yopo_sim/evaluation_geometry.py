"""Truth geometry for scoring only; never imported by an online planner."""
import numpy as np


class ForestEvaluator:
    def __init__(self,scene):
        self.trees=np.asarray(scene['trees'],float).reshape(-1,4)
        self.shrubs=np.asarray(scene['shrubs'],float).reshape(-1,6)

    def distance(self,p):
        p=np.asarray(p);best=float(p[2])
        if len(self.trees):
            radial=np.linalg.norm(self.trees[:,:2]-p[:2],axis=1)-self.trees[:,2]
            vertical=np.abs(p[2]-self.trees[:,3]/2)-self.trees[:,3]/2
            d=np.column_stack([radial,vertical])
            best=min(best,float((np.minimum(d.max(axis=1),0)+np.linalg.norm(np.maximum(d,0),axis=1)).min()))
        if len(self.shrubs):
            d=np.abs(p-self.shrubs[:,:3])-self.shrubs[:,3:]/2
            best=min(best,float((np.minimum(d.max(axis=1),0)+np.linalg.norm(np.maximum(d,0),axis=1)).min()))
        return best
