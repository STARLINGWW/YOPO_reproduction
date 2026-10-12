"""Keras MobileNet/Conv1D network with exact exported official parameters.

Layer wrappers retain channel-last logical shapes, Keras asymmetric SAME
padding, BatchNorm epsilon, ReLU6, LeakyReLU slopes and flatten ordering.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class Layer(nn.Module):
    def __init__(self,record,weights):
        super().__init__();self.kind=record['class'];self.c=record['config']
        values=[weights[k] for k in record['weights']]
        for i,value in enumerate(values):self.register_buffer(f'w{i}',torch.from_numpy(np.asarray(value).copy()))
        if self.kind=='Conv2D':self.register_buffer('kernel',self.w0.permute(3,2,0,1).contiguous())
        elif self.kind=='DepthwiseConv2D':
            self.register_buffer('kernel',self.w0.permute(2,3,0,1).reshape(-1,1,*self.w0.shape[:2]).contiguous())
        elif self.kind=='Conv1D':self.register_buffer('kernel',self.w0.permute(2,1,0).contiguous())
        elif self.kind not in ['InputLayer','BatchNormalization','ReLU','LeakyReLU','ZeroPadding2D']:
            raise ValueError(f'Unsupported original layer: {self.kind}')
        self.count=len(values)

    def forward(self,x):
        c=self.c
        if self.kind=='InputLayer':return x
        if self.kind in ['Conv2D','DepthwiseConv2D','Conv1D']:
            dims=1 if self.kind=='Conv1D' else 2
            y=x.permute(0,2,1) if dims==1 else x.permute(0,3,1,2)
            stride=tuple(c['strides']);dilation=tuple(c['dilation_rate']);kernel=tuple(c['kernel_size'])
            if c['padding']=='same':
                padding=[]
                for length,k,s,d in zip(y.shape[2:],kernel,stride,dilation):
                    total=max(0,(math.ceil(length/s)-1)*s+(k-1)*d+1-length)
                    if total>(k-1)*d:raise ValueError('SAME padding exceeds kernel extent')
                    padding.append((total//2,total-total//2))
                y=F.pad(y,tuple(v for pair in padding[::-1] for v in pair))
            elif c['padding']!='valid':raise ValueError(c['padding'])
            bias=self.w1 if c['use_bias'] else None
            groups=x.shape[-1] if self.kind=='DepthwiseConv2D' else int(c.get('groups',1))
            function=F.conv1d if dims==1 else F.conv2d
            y=function(y,self.kernel,bias,stride=stride,dilation=dilation,groups=groups)
            return y.permute(0,2,1) if dims==1 else y.permute(0,2,3,1)
        if self.kind=='BatchNormalization':
            assert c['center'] and c['scale'] and self.count==4 and c['axis'] in [3,[3],-1,[-1]]
            y=F.batch_norm(x.permute(0,3,1,2),self.w2,self.w3,self.w0,self.w1,training=False,eps=float(c['epsilon']))
            return y.permute(0,2,3,1)
        if self.kind=='ReLU':
            assert float(c.get('negative_slope',0))==0 and float(c.get('threshold',0))==0
            return torch.clamp(x,min=0,max=c.get('max_value'))
        if self.kind=='LeakyReLU':return F.leaky_relu(x,negative_slope=float(c['alpha']))
        if self.kind=='ZeroPadding2D':
            (top,bottom),(left,right)=c['padding']
            return F.pad(x.permute(0,3,1,2),(left,right,top,bottom)).permute(0,2,3,1)
        raise AssertionError(self.kind)


class AgileNetwork(nn.Module):
    def __init__(self,export_path):
        super().__init__();root=Path(export_path);self.manifest=json.loads((root/'manifest.json').read_text())
        assert self.manifest['config']['seq_len']==1 and self.manifest['config']['use_depth'] and not self.manifest['config']['use_rgb']
        if hashlib.sha256((root/'weights.npz').read_bytes()).hexdigest()!=self.manifest['weights_file_sha256']:raise ValueError('Export weight file hash mismatch')
        weights=np.load(root/'weights.npz');hashes=[]
        for records in self.manifest['groups'].values():
            for record in records:
                hashes.extend(hashlib.sha256(weights[k].tobytes()).hexdigest() for k in record['weights'])
        if hashes!=self.manifest['ordered_weight_sha256']:raise ValueError('Export variable hashes mismatch')
        self.groups=nn.ModuleDict({name:nn.Sequential(*(Layer(record,weights) for record in records)) for name,records in self.manifest['groups'].items()})
        weights.close();self.eval()

    def forward(self,depth,imu):
        if depth.ndim!=5 or depth.shape[1:]!=(1,224,224,3) or imu.shape[1:]!=(1,21):raise ValueError('Expected official single-frame224depth/21state interface')
        x=depth[:,0]/127.5-1.
        x=self.groups['backbone'](x)
        x=x.reshape(x.shape[0],-1,x.shape[-1]);x=self.groups['resize_op'](x)
        x=x.reshape(x.shape[0],1,-1);x=self.groups['img_mergenet'](x)
        x=self.groups['resize_op_2'](x.transpose(1,2)).transpose(1,2)
        state=self.groups['states_conv'](imu[:,:,3:])
        state=self.groups['resize_op_3'](state.transpose(1,2)).transpose(1,2)
        return self.groups['plan_module'](torch.cat([x,state],dim=-1))
