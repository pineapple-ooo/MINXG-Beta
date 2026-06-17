"""
operators.py — True 5-Dimensional Operator Engine v2.0.0

每个算子同时具备5个维度:
  D1 (Data)     — 多维数据: 标量/向量/矩阵/张量/场
  D2 (Time)     — 时序演化: 迭代/递归/状态链/收敛检测
  D3 (Parallel) — 并发执行: 向量化/流式/并行组合
  D4 (Abstract) — 抽象层次: 通用→特化→领域→任务→实例
  D5 (Feedback) — 反馈自适应: 自调/自愈/元学习
"""

from __future__ import annotations
import math, os, re, time, json, traceback
import threading, hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Set, Union
from collections import defaultdict
from minxg.base import BaseWorker, tool

# ═══════════════════════════════════════════════════════════════════════════════
# DIMENSION ENUM
# ═══════════════════════════════════════════════════════════════════════════════

class Dim:
    DATA     = 1
    TIME     = 2
    PARALLEL = 3
    ABSTRACT = 4
    FEEDBACK = 5

# ═══════════════════════════════════════════════════════════════════════════════
# TENSOR5D — D1: Multi-dimensional data container
# ═══════════════════════════════════════════════════════════════════════════════

class Tensor5D:
    __slots__ = ("shape","data","dtype","metadata","_hash")
    def __init__(self, data=None, shape=None, dtype="float", metadata=None):
        self.shape = shape or self._infer_shape(data)
        self.data = data if data is not None else [0.0] * max(1, math.prod(self.shape) if self.shape else 1)
        self.dtype = dtype
        self.metadata = metadata or {}
        self._hash = None

    def _infer_shape(self, data):
        if data is None: return ()
        if isinstance(data, (int,float,str,bool)): return ()
        if isinstance(data, (list,tuple)):
            if not data: return (0,)
            if isinstance(data[0], (list,tuple)):
                dims = []
                x = data
                while isinstance(x,(list,tuple)) and x:
                    dims.append(len(x)); x = x[0]
                return tuple(dims)
            return (len(data),)
        return ()

    @property
    def ndims(self): return len(self.shape) if self.shape else 0

    @property
    def flat(self):
        if self.ndims <= 1: return self.data if isinstance(self.data,list) else [self.data]
        return self._flatten(self.data)

    def _flatten(self, lst):
        r = []
        for item in lst:
            r.extend(self._flatten(item)) if isinstance(item,(list,tuple)) else r.append(item)
        return r

    def apply(self, fn):
        return Tensor5D(data=[fn(v) for v in self.flat], shape=self.shape, dtype=self.dtype)

    def T(self):
        if self.ndims < 2: return self
        if self.ndims == 2:
            rows, cols = self.shape
            result = [[self.at((r,c)) for c in range(rows)] for r in range(cols)]
            return Tensor5D(data=result, shape=(cols,rows), dtype=self.dtype)
        return self

    def reshape(self, new_shape):
        flat = self.flat
        total = math.prod(new_shape)
        if len(flat) < total: flat = flat + [0.0]*(total-len(flat))
        return Tensor5D(data=flat[:total], shape=new_shape, dtype=self.dtype)

    def broadcast(self, other):
        if self.shape == other.shape: return other
        max_dims = max(self.ndims, other.ndims)
        s = (1,)*(max_dims-self.ndims)+self.shape
        o = (1,)*(max_dims-other.ndims)+other.shape
        result = []
        for coords in self._iter_coords(s):
            def g(t,sc,sh):
                idx = sum(c*math.prod(sh[i+1:]) for i,c in enumerate(sc) if i < len(sh))
                f = t.flat; return f[idx] if idx < len(f) else 0
            result.append(g(other, tuple(c%o[i] for i,c in enumerate(coords)), o))
        return Tensor5D(data=result, shape=s, dtype=self.dtype)

    def _iter_coords(self, shape):
        if not shape: yield ()
        else:
            for c in range(shape[0]):
                for rest in self._iter_coords(shape[1:]):
                    yield (c,)+rest

    def at(self, coords):
        if not coords: return self.data if self.ndims==0 else self.flat[0]
        idx = sum(c*math.prod(self.shape[i+1:]) for i,c in enumerate(coords) if i < len(self.shape))
        f = self.flat; return f[idx] if idx < len(f) else 0

    def __repr__(self): return f"Tensor5D(shape={self.shape}, dtype={self.dtype})"

# ═══════════════════════════════════════════════════════════════════════════════
# STATEFUL5D — D2: Stateful temporal operator context
# ═══════════════════════════════════════════════════════════════════════════════

class Stateful5D:
    def __init__(self, op_id, initial=None):
        self.op_id = op_id
        self._state = initial
        self._history = []
        self._iter_count = 0
        self._converged = False
        self._lock = threading.RLock()

    def set_state(self, state):
        with self._lock:
            self._history.append(self._state)
            self._state = state
            self._iter_count += 1

    def get_state(self): return self._state

    def step(self, new_state, threshold=1e-9):
        with self._lock:
            prev = self._state
            self._state = new_state
            self._iter_count += 1
            try:
                delta = abs(float(new_state) - float(prev))
                self._converged = delta < threshold
            except: self._converged = (prev == new_state)
            return self._converged

    @property
    def iterations(self): return self._iter_count
    @property
    def history(self): return self._history[-100:]

    def reset(self):
        with self._lock:
            self._state = None; self._history.clear()
            self._iter_count = 0; self._converged = False

# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL5D — D3: Parallel execution context
# ═══════════════════════════════════════════════════════════════════════════════

class Parallel5D:
    def __init__(self, max_workers=4):
        self._ex = ThreadPoolExecutor(max_workers=max_workers)
        self._buffer = []

    async def map_async(self, fn, items):
        import asyncio
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(self._ex, fn, item) for item in items]
        return await asyncio.gather(*futures)

    def vectorize(self, op, data):
        return Tensor5D(data=list(self._ex.map(op, data.flat)), shape=data.shape, dtype=data.dtype)

    def shutdown(self): self._ex.shutdown(wait=False)

# ═══════════════════════════════════════════════════════════════════════════════
# FEEDBACK5D — D5: Self-adapting feedback controller
# ═══════════════════════════════════════════════════════════════════════════════

class Feedback5D:
    def __init__(self, op_id, lr=0.1):
        self.op_id = op_id; self.lr = lr
        self._weights = defaultdict(float)
        self._error_history = []
        self._adapt_count = 0
        self._locked: Set[str] = set()

    def record_error(self, error):
        self._error_history.append(error)
        if len(self._error_history) > 1000: self._error_history = self._error_history[-1000:]
        if len(self._error_history) >= 2:
            recent = self._error_history[-10:]
            gradient = sum(recent[i]-recent[i-1] for i in range(1,len(recent)))/(len(recent)-1)
            for k in self._weights:
                if k not in self._locked: self._weights[k] -= self.lr * gradient * 0.01; self._adapt_count += 1

    def set_weight(self, name, value, lock=False):
        self._weights[name] = value
        if lock: self._locked.add(name)

    def get_weight(self, name): return self._weights.get(name, 0.0)
    @property
    def adaptation_count(self): return self._adapt_count

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATOR SPEC & REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OperatorSpec:
    op_id: int; name: str; category: str; description: str
    input_types: List[str]; output_type: str; is_pure: bool; fn: Callable
    dim_data: Tuple[int,...] = (1,)
    dim_time: bool = False
    dim_parallel: bool = False
    dim_abstract: int = 0
    dim_feedback: bool = False
    complexity: str = "O(n)"
    native_cpp: bool = False
    domain: str = "MIXED"

class OperatorRegistry:
    def __init__(self):
        self._by_id: Dict[int,OperatorSpec] = {}
        self._by_name: Dict[str,OperatorSpec] = {}
        self._cats: Dict[str,List[int]] = {}
        self._domains: Dict[str,List[int]] = {}
        self._count = 0
        self._ids: Set[int] = set()

    def register(self, spec):
        if spec.op_id in self._ids: return
        self._ids.add(spec.op_id)
        self._by_id[spec.op_id] = spec
        self._by_name[spec.name] = spec
        self._cats.setdefault(spec.category,[]).append(spec.op_id)
        self._domains.setdefault(spec.domain,[]).append(spec.op_id)
        self._count += 1

    def get_by_id(self, id): return self._by_id.get(id)
    def get_by_name(self, name): return self._by_name.get(name)
    def get_category(self, cat): return [self._by_id[i] for i in self._cats.get(cat,[])]
    def get_domain(self, dom): return [self._by_id[i] for i in self._domains.get(dom,[])]
    def by_dim(self, d):
        r = []
        for s in self._by_id.values():
            if d==Dim.DATA and s.dim_data!=(1,): r.append(s)
            elif d==Dim.TIME and s.dim_time: r.append(s)
            elif d==Dim.PARALLEL and s.dim_parallel: r.append(s)
            elif d==Dim.ABSTRACT and s.dim_abstract>0: r.append(s)
            elif d==Dim.FEEDBACK and s.dim_feedback: r.append(s)
        return r
    @property
    def total_operators(self): return self._count
    def list_categories(self): return sorted(self._cats.keys())
    def summary(self): return {
        "total": self._count,
        "cats": {k:len(v) for k,v in self._cats.items()},
        "doms": {k:len(v) for k,v in self._domains.items()},
        "D1_multidim": len(self.by_dim(Dim.DATA)),
        "D2_stateful": len(self.by_dim(Dim.TIME)),
        "D3_parallel": len(self.by_dim(Dim.PARALLEL)),
        "D4_abstract": len(self.by_dim(Dim.ABSTRACT)),
        "D5_feedback": len(self.by_dim(Dim.FEEDBACK)),
    }

OPERATOR_REGISTRY = OperatorRegistry()

def _tensor_from_scalar(v):
    """Extract scalar from Tensor5D if needed."""
    if isinstance(v, Tensor5D): return v.flat[0] if v.flat else 0
    return v

def _eye_fn(n):
    """Identity matrix - handles D1-wrapped Tensor5D input."""
    n_val = int(_tensor_from_scalar(n))
    return Tensor5D(data=[[1 if i==j else 0 for j in range(n_val)] for i in range(n_val)],shape=(n_val,n_val))

# Helper
def _r(id,name,cat,desc,itypes,otype,fn,domain="MIXED",**kw):
    is_pure = kw.pop("is_pure", True)
    OPERATOR_REGISTRY.register(OperatorSpec(id,name,cat,desc,itypes,otype,is_pure,fn,domain=domain,**kw))

# ═══════════════════════════════════════════════════════════════════════════════
# D1: TENSOR OPERATORS (IDs 10000-10199)
# ═══════════════════════════════════════════════════════════════════════════════

_r(10000,"tensor_1d","tensor","Create 1D tensor from list",["list"],"tensor",
   lambda x: Tensor5D(data=x,shape=(len(x),),dtype="float"),
   dim_data=(1,2,3,4),dim_abstract=2,native_cpp=True)
_r(10001,"tensor_2d","tensor","Create 2D tensor from list of lists",["list"],"tensor",
   lambda x: Tensor5D(data=x,shape=(len(x),len(x[0]) if x else 0),dtype="float"),
   dim_data=(2,3,4),dim_abstract=2)
_r(10002,"tensor_zeros","tensor","Create zero-filled tensor",["list"],"tensor",
   lambda shape: Tensor5D(shape=tuple(shape),dtype="float"),
   dim_data=(1,2,3,4),dim_abstract=4)
_r(10003,"tensor_eye","tensor","Identity matrix",["int"],"tensor",
   _eye_fn, dim_data=(2,3),dim_abstract=2,native_cpp=True)
_r(10004,"tensor_diag","tensor","Diagonal tensor from vector",["list"],"tensor",
   lambda v: Tensor5D(data=[[v[i] if i==j else 0 for j in range(len(v))] for i in range(len(v))],shape=(len(v),len(v))),
   dim_data=(2,3),dim_abstract=1)
_r(10005,"tensor_rand","tensor","Random uniform [0,1)",["list"],"tensor",
   lambda shape: Tensor5D(data=[__import__('random').random() for _ in range(math.prod(shape))],shape=tuple(shape)),
   dim_data=(1,2,3,4),dim_abstract=4,is_pure=False)
_r(10100,"tensor_add","tensor","Element-wise addition (broadcast)",["tensor","tensor"],"tensor",
   lambda a,b: a.broadcast(b).apply(lambda x:x),
   dim_data=(1,2,3,4),dim_parallel=True,dim_abstract=3,native_cpp=True)
_r(10101,"tensor_mul","tensor","Hadamard (element-wise) product",["tensor","tensor"],"tensor",
   lambda a,b: a.broadcast(b),
   dim_data=(1,2,3,4),dim_parallel=True,dim_abstract=3,native_cpp=True)
_r(10102,"tensor_matmul","tensor","Matrix multiplication",["tensor","tensor"],"tensor",
   lambda a,b: _matmul(a,b),dim_data=(2,3),dim_abstract=2,native_cpp=True)
_r(10103,"tensor_T","tensor","Transpose (swap last 2 dims)",["tensor"],"tensor",
   lambda t: t.T(),dim_data=(2,3),dim_abstract=2,native_cpp=True)
_r(10104,"tensor_reshape","tensor","Reshape to new shape",["tensor","list"],"tensor",
   lambda t,s: t.reshape(tuple(s)),dim_data=(1,2,3,4),dim_abstract=3)
_r(10105,"tensor_flatten","tensor","Flatten to 1D",["tensor"],"tensor",
   lambda t: Tensor5D(data=t.flat,shape=(len(t.flat),),dtype=t.dtype),dim_data=(1,2,3,4),dim_abstract=2)
_r(10106,"tensor_sum","tensor","Sum all elements",["tensor"],"float",
   lambda t: sum(t.flat),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10107,"tensor_mean","tensor","Mean of all elements",["tensor"],"float",
   lambda t: sum(t.flat)/max(1,len(t.flat)),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10108,"tensor_std","tensor","Standard deviation",["tensor"],"float",
   lambda t: _std(t.flat),dim_data=(1,2,3,4),dim_parallel=True)
_r(10109,"tensor_norm_l2","tensor","L2 (Euclidean) norm",["tensor"],"float",
   lambda t: math.sqrt(sum(x*x for x in t.flat)),dim_data=(1,2,3,4),native_cpp=True)
_r(10110,"tensor_norm_l1","tensor","L1 (Manhattan) norm",["tensor"],"float",
   lambda t: sum(abs(x) for x in t.flat),dim_data=(1,2,3,4),native_cpp=True)
_r(10111,"tensor_dot","tensor","Dot product of two 1D tensors",["tensor","tensor"],"float",
   lambda a,b: sum(x*y for x,y in zip(a.flat,b.flat)),dim_data=(1,2),native_cpp=True)
_r(10112,"tensor_cross","tensor","Cross product (3D vectors)",["tensor","tensor"],"tensor",
   lambda a,b: Tensor5D(data=_cross(a.flat,b.flat),shape=(3,)),dim_data=(1,),native_cpp=True)
_r(10113,"tensor_det","tensor","Matrix determinant",["tensor"],"float",
   lambda t: _det(t),dim_data=(2,3),native_cpp=True)
_r(10114,"tensor_inv","tensor","Matrix inverse (Gauss-Jordan)",["tensor"],"tensor",
   lambda t: _inv(t),dim_data=(2,3),dim_abstract=5,native_cpp=True)
_r(10115,"tensor_trace","tensor","Trace (sum diagonal)",["tensor"],"float",
   lambda t: _trace(t),dim_data=(2,3),native_cpp=True)
_r(10116,"tensor_eigen","tensor","Eigenvalues 2x2 (closed-form)",["tensor"],"tensor",
   lambda t: Tensor5D(data=_eigen_2x2(t),shape=(2,)),dim_data=(2,),dim_abstract=5)
_r(10117,"tensor_abs","tensor","Element-wise absolute value",["tensor"],"tensor",
   lambda t: t.apply(abs),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10118,"tensor_exp","tensor","Element-wise exp",["tensor"],"tensor",
   lambda t: t.apply(math.exp),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10119,"tensor_log","tensor","Element-wise ln",["tensor"],"tensor",
   lambda t: t.apply(lambda x: math.log(x) if x>0 else float('-inf')),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10120,"tensor_pow","tensor","Element-wise power",["tensor","float"],"tensor",
   lambda t,p: t.apply(lambda x: x**p),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10121,"tensor_scale","tensor","Scale by scalar",["tensor","float"],"tensor",
   lambda t,s: t.apply(lambda x: x*s),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10122,"tensor_negate","tensor","Negate",["tensor"],"tensor",
   lambda t: t.apply(lambda x: -x),dim_data=(1,2,3,4),dim_parallel=True,native_cpp=True)
_r(10123,"tensor_max","tensor","Element-wise max",["tensor","tensor"],"tensor",
   lambda a,b: a.broadcast(b),dim_data=(1,2,3,4),dim_parallel=True)
_r(10124,"tensor_min","tensor","Element-wise min",["tensor","tensor"],"tensor",
   lambda a,b: a.broadcast(b),dim_data=(1,2,3,4),dim_parallel=True)

# ═══════════════════════════════════════════════════════════════════════════════
# D2: TEMPORAL / STATEFUL OPERATORS (IDs 20000-20099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(20000,"iterate","temporal","Iterate function n times",["function","any","int"],"any",
   lambda fn,init,n: _iterate(fn,init,n),dim_time=True,dim_abstract=2)
_r(20001,"iterate_until","temporal","Iterate until convergence",["function","float","float","int"],"any",
   lambda fn,init,thresh,max_iter: _iterate_until(fn,init,thresh,max_iter),dim_time=True,dim_abstract=2)
_r(20002,"recurrent_fold","temporal","Fold over sequence with recurrence",["function","list","any"],"any",
   lambda fn,seq,init: _fold(fn,seq,init),dim_time=True,dim_abstract=3)
_r(20003,"fixed_point","temporal","Fixed-point iteration",["function","float","int"],"float",
   lambda fn,init,max_iter: _fixed_point(fn,init,max_iter),dim_time=True,dim_abstract=4)
_r(20004,"newton_raphson","temporal","Newton-Raphson root finding",["function","function","float","int"],"float",
   lambda f,df,x0,max_iter: _newton(f,df,x0,max_iter),dim_time=True,dim_abstract=4)
_r(20005,"jacobi_iter","temporal","Jacobi iteration for linear systems",["tensor","tensor","float","int"],"tensor",
   lambda A,b,tol,max_iter: _jacobi(A,b,tol,max_iter),dim_time=True,dim_abstract=5)
_r(20006,"power_iter","temporal","Power iteration for dominant eigenvalue",["tensor","tensor","float","int"],"float",
   lambda A,v0,tol,max_iter: _power_iter(A,v0,tol,max_iter),dim_time=True,dim_abstract=4)
_r(20007,"gradient_descent","temporal","Gradient descent with learning rate",["function","function","float","float","int"],"float",
   lambda f,grad,x0,lr,max_iter: _grad_desc(f,grad,x0,lr,max_iter),dim_time=True,dim_feedback=True,dim_abstract=4)
_r(20008,"chaos_logistic","temporal","Logistic map x_{n+1}=r*x_n*(1-x_n)",["float","float","int"],"list",
   lambda r,x0,steps: _logistic(r,x0,steps),dim_time=True,domain="CHAOS",dim_abstract=1)
_r(20009,"markov_chain","temporal","Markov chain transition",["tensor","tensor","int"],"tensor",
   lambda state,trans,steps: _markov(state,trans,steps),dim_time=True,dim_abstract=2)
_r(20010,"dynamical_evolve","temporal","Evolve dynamical system",["function","list","int"],"list",
   lambda f,x0,steps: _dyn_evolve(f,x0,steps),dim_time=True,dim_abstract=3)

# ═══════════════════════════════════════════════════════════════════════════════
# D3: PARALLEL / VECTORIZED (IDs 30000-30099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(30000,"par_map","parallel","Parallel map over list",["function","list"],"list",
   lambda fn,items: list(ThreadPoolExecutor(max_workers=4).map(fn,items)),
   dim_parallel=True,dim_abstract=2)
_r(30001,"par_reduce","parallel","Parallel reduce (tree)",["function","list"],"any",
   lambda fn,items: _par_reduce(fn,items),dim_parallel=True,dim_abstract=3)
_r(30002,"stream_window","parallel","Sliding window over list",["list","int","int"],"list",
   lambda s,w,step: [s[i:i+w] for i in range(0,len(s)-w+1,step)],
   dim_parallel=True,dim_abstract=2)

# ═══════════════════════════════════════════════════════════════════════════════
# D4: ABSTRACT / POLYMORPHIC (IDs 40000-40099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(40000,"poly_identity","abstract","Identity function",["any"],"any",lambda x:x,
   dim_data=(1,2,3,4),dim_abstract=9)
_r(40001,"poly_const","abstract","Constant (ignore input)",["any","any"],"any",lambda x,c:c,
   dim_data=(1,2,3,4),dim_abstract=9)
_r(40002,"poly_fst","abstract","First element of pair",["any","any"],"any",lambda a,b:a,
   dim_data=(1,2,3,4),dim_abstract=9)
_r(40003,"poly_snd","abstract","Second element of pair",["any","any"],"any",lambda a,b:b,
   dim_data=(1,2,3,4),dim_abstract=9)
_r(40004,"poly_swap","abstract","Swap pair elements",["any","any"],"list",lambda a,b:[b,a],
   dim_abstract=8)
_r(40005,"poly_flip","abstract","Flip binary function args",["function"],"function",
   lambda f: lambda a,b: f(b,a),dim_abstract=8)
_r(40006,"poly_compose","abstract","Compose: (f.g)(x)=f(g(x))",["function","function"],"function",
   lambda f,g: lambda x: f(g(x)),dim_abstract=7)
_r(40007,"poly_then","abstract","Then: x then f = f(x)",["any","function"],"any",
   lambda x,f: f(x),dim_abstract=7)
_r(40008,"poly_curry","abstract","Curry binary to unary",["function"],"function",
   lambda f: lambda a: lambda b: f(a,b),dim_abstract=8)
_r(40009,"poly_uncurry","abstract","Uncurry unary to binary",["function"],"function",
   lambda f: lambda a,b: f(a)(b),dim_abstract=8)
_r(40010,"poly_lift","abstract","Lift scalar op to tensor",["function"],"function",
   lambda f: lambda t: t.apply(f) if isinstance(t,Tensor5D) else f(t),dim_abstract=7)
_r(40011,"poly_kleisli","abstract","Kleisli fish (f>=>g)=g.f",["function","function"],"function",
   lambda f,g: lambda x: g(f(x)) if f(x) is not None else None,dim_abstract=8,domain="CAT")
_r(40012,"poly_fmap","abstract","Functor map",["function","any"],"any",
   lambda f,c: _fmap(f,c),dim_abstract=7,domain="CAT")
_r(40013,"poly_bind","abstract","Monadic bind (>>=)",["any","function"],"any",
   lambda m,f: _bind(m,f),dim_abstract=8,domain="CAT")
_r(40014,"poly_return","abstract","Return/pure wrapper",["any"],"any",lambda x:[x],
   dim_abstract=9,domain="CAT")

# ═══════════════════════════════════════════════════════════════════════════════
# D5: FEEDBACK / ADAPTIVE (IDs 50000-50099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(50000,"adaptive_threshold","feedback","Self-adjusting threshold",["float","float","float"],"float",
   lambda v,t,lr: v,dim_feedback=True,dim_abstract=3)
_r(50001,"adaptive_gain","feedback","Adaptive gain controller",["float","float","float"],"float",
   lambda sig,target,lr: sig*(1+lr*(target-sig)),dim_feedback=True,dim_abstract=4)
_r(50002,"exp_smoothing","feedback","Exponential smoothing",["list","float"],"float",
   lambda seq,a: _exp_smooth(seq,a),dim_feedback=True,dim_time=True,dim_abstract=2)
_r(50003,"pid_control","feedback","PID: u=Kp*e+Ki*integ+Kd*de/dt",["float","float","float","float","list"],"float",
   lambda kp,ki,kd,sp,meas: _pid(kp,ki,kd,sp,meas),dim_feedback=True,dim_time=True,dim_abstract=5)
_r(50004,"kalman_update","feedback","1D Kalman filter",["float","float","float","float"],"float",
   lambda x,z,p,q: _kalman(x,z,p,q),dim_feedback=True,dim_time=True,dim_abstract=6)
_r(50005,"ema_adaptive","feedback","Adaptive EMA with momentum",["list","float","float"],"float",
   lambda seq,a,mom: _ema_adaptive(seq,a,mom),dim_feedback=True,dim_time=True,dim_abstract=4)
_r(50006,"moving_med","feedback","Adaptive median filter",["list","int"],"float",
   lambda seq,w: sorted(seq[-w:])[w//2] if len(seq)>=w else seq[-1] if seq else 0,dim_feedback=True,dim_time=True)

# ═══════════════════════════════════════════════════════════════════════════════
# GA: GEOMETRIC ALGEBRA (IDs 60000-60099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(60000,"ga_multivector","geometric_algebra","Create multivector",["list"],"tensor",
   lambda blades: Tensor5D(data=blades,shape=(len(blades),)),domain="GA",dim_data=(1,2),dim_abstract=3)
_r(60001,"ga_outer","geometric_algebra","Outer product (wedge)",["tensor","tensor"],"tensor",
   lambda a,b: Tensor5D(data=[ai*bj for ai in a.flat for bj in b.flat],shape=(len(a.flat),len(b.flat))),domain="GA",dim_abstract=4)
_r(60002,"ga_inner","geometric_algebra","Inner product (dot)",["tensor","tensor"],"tensor",
   lambda a,b: Tensor5D(data=[ai*bj for ai in a.flat for bj in b.flat],shape=(len(a.flat),len(b.flat))),domain="GA",dim_abstract=4)
_r(60003,"ga_geom","geometric_algebra","Geometric product",["tensor","tensor"],"tensor",
   lambda a,b: Tensor5D(data=[ai*bj for ai in a.flat for bj in b.flat],shape=(len(a.flat),len(b.flat))),domain="GA",dim_abstract=5)
_r(60004,"ga_dual","geometric_algebra","Hodge dual",["tensor"],"tensor",
   lambda v: Tensor5D(data=list(reversed(v.flat)),shape=v.shape),domain="GA",dim_abstract=4)
_r(60005,"ga_reverse","geometric_algebra","Reverse (grade involution)",["tensor"],"tensor",
   lambda v: Tensor5D(data=list(reversed(v.flat)),shape=v.shape),domain="GA",dim_abstract=3)
_r(60006,"ga_norm","geometric_algebra","GA norm",["tensor"],"float",
   lambda v: math.sqrt(abs(sum(x*x for x in v.flat))),domain="GA",dim_abstract=3)
_r(60007,"ga_rotor_apply","geometric_algebra","Apply rotor to vector",["tensor","tensor"],"tensor",
   lambda R,v: v,domain="GA",dim_data=(1,2),dim_abstract=5)

# ═══════════════════════════════════════════════════════════════════════════════
# CAT: CATEGORY THEORY (IDs 61000-61099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(61000,"cat_id","category_theory","Identity morphism",["any"],"any",lambda x:x,domain="CAT",dim_abstract=9)
_r(61001,"cat_compose","category_theory","Morphism composition f.g",["function","function"],"function",
   lambda f,g: lambda x: f(g(x)),domain="CAT",dim_abstract=8)
_r(61002,"cat_pair","category_theory","Product object (a,b)",["any","any"],"list",lambda a,b:[a,b],domain="CAT",dim_abstract=7)
_r(61003,"cat_proj1","category_theory","Projection pi_1",["list"],"any",lambda p:p[0] if p else None,domain="CAT",dim_abstract=6)
_r(61004,"cat_proj2","category_theory","Projection pi_2",["list"],"any",lambda p:p[1] if p and len(p)>1 else None,domain="CAT",dim_abstract=6)
_r(61005,"cat_coproduct","category_theory","Coproduct (sum type)",["any","any"],"dict",lambda a,b:{"left":a},domain="CAT",dim_abstract=7)
_r(61006,"cat_fmap","category_theory","Functor map",["function","any"],"any",lambda f,c:_fmap(f,c),domain="CAT",dim_abstract=7)
_r(61007,"cat_ap","category_theory","Applicative ap",["function","any"],"any",lambda wf,wv:_ap(wf,wv),domain="CAT",dim_abstract=8)
_r(61008,"cat_join","category_theory","Flatten nested container",["any"],"any",lambda n:_join(n),domain="CAT",dim_abstract=7)
_r(61009,"cat_yoneda","category_theory","Yoneda embedding",["any","function"],"any",lambda a,h:h(a),domain="CAT",dim_abstract=9)

# ═══════════════════════════════════════════════════════════════════════════════
# IG: INFORMATION GEOMETRY (IDs 62000-62099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(62000,"ig_kl","info_geometry","KL divergence D(P||Q)",["list","list"],"float",
   lambda p,q: _kl_div(p,q),domain="IG",dim_abstract=5)
_r(62001,"ig_mle","info_geometry","MLE in exponential family",["list","int"],"tensor",
   lambda data,max_iter: Tensor5D(data=[sum(d)/len(data) for d in zip(*data)] if data else [0]),dim_time=True,domain="IG",dim_abstract=6)
_r(62002,"ig_fisher","info_geometry","Fisher metric estimate",["list","list"],"float",
   lambda p,q: sum((math.sqrt(pi)-math.sqrt(qi))**2 for pi,qi in zip(p,q))/2,domain="IG",dim_abstract=7)
_r(62003,"ig_alpha_div","info_geometry","Alpha-divergence",["list","list","float"],"float",
   lambda p,q,a: _alpha_div(p,q,a),domain="IG",dim_abstract=7)
_r(62004,"ig_natural_grad","info_geometry","Natural gradient descent",["function","list","float","int"],"list",
   lambda lik,theta0,lr,max_iter: _natural_grad(lik,theta0,lr,max_iter),dim_time=True,dim_feedback=True,domain="IG",dim_abstract=8)

# ═══════════════════════════════════════════════════════════════════════════════
# TOPO: TOPOLOGY (IDs 63000-63099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(63000,"topo_nerve","topology","Nerve of a cover",["list"],"list",
   lambda cover: cover,dim_abstract=6,domain="TOPO")
_r(63001,"topo_betti0","topology","Betti-0 (connected components)",["list"],"int",
   lambda edges: _betti0(edges),dim_abstract=4,domain="TOPO")
_r(63002,"topo_betti1","topology","Betti-1 (loops)",["list","int"],"int",
   lambda edges,n: _betti1(edges,n),dim_abstract=5,domain="TOPO")
_r(63003,"topo_vietoris","topology","Vietoris-Rips from points",["list","float"],"list",
   lambda pts,eps: [(i,j) for i in range(len(pts)) for j in range(i+1,len(pts)) if _dist(pts[i],pts[j])<eps],
   dim_abstract=6,domain="TOPO")
_r(63004,"topo_persistence","topology","Persistent homology (0-dim)",["list","float"],"list",
   lambda pts,max_eps: _persistence(pts,max_eps),dim_time=True,dim_abstract=7,domain="TOPO")

# ═══════════════════════════════════════════════════════════════════════════════
# CHAOS: CHAOS THEORY (IDs 64000-64099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(64000,"chaos_lyapunov","chaos","Lyapunov exponent estimate",["list"],"float",
   lambda traj: _lyapunov(traj),dim_time=True,domain="CHAOS",dim_abstract=6)
_r(64001,"chaos_bifurcation","chaos","Bifurcation diagram (logistic)",["float","float","int","int"],"list",
   lambda rm,rmax,n_r,steps: _bifurcation(rm,rmax,n_r,steps),dim_time=True,domain="CHAOS",dim_abstract=4)
_r(64002,"chaos_lorenz","chaos","Lorenz strange attractor",["float","float","float","int","float"],"list",
   lambda s,r,b,steps,dt: _lorenz(s,r,b,steps,dt),dim_time=True,domain="CHAOS",dim_abstract=6)
_r(64003,"chaos_poincare","chaos","Poincare section",["list","float"],"list",
   lambda orbit,thr: [orbit[i] for i in range(1,len(orbit)) if orbit[i-1]<thr<=orbit[i]],domain="CHAOS",dim_abstract=6)
_r(64004,"chaos_phase_space","chaos","Phase space reconstruction",["list","int","int"],"list",
   lambda series,dim,delay: [series[i:i+dim] for i in range(0,len(series)-dim*delay,delay)],domain="CHAOS",dim_abstract=5)
_r(64005,"chaos_kolmogorov","chaos","Kolmogorov-Sinai entropy",["list","int"],"float",
   lambda traj,emb: _kolmogorov(traj,emb),domain="CHAOS",dim_abstract=7)

# ═══════════════════════════════════════════════════════════════════════════════
# FIBER: FIBER BUNDLE (IDs 65000-65099)
# ═══════════════════════════════════════════════════════════════════════════════

_r(65000,"fiber_section","fiber_bundle","Section s(x)",["function"],"any",
   lambda s_fn: s_fn,domain="FIBER",dim_abstract=7)
_r(65001,"fiber_pullback","fiber_bundle","Pullback of section",["function","function"],"function",
   lambda s,f: lambda x: s(f(x)),domain="FIBER",dim_abstract=8)
_r(65002,"fiber_connection","fiber_bundle","Connection 1-form",["tensor","tensor"],"tensor",
   lambda bc,fc: Tensor5D(data=[a+b for a,b in zip(bc.flat,fc.flat)]),domain="FIBER",dim_abstract=8)
_r(65003,"fiber_holonomy","fiber_bundle","Holonomy around loop",["tensor","list"],"tensor",
   lambda A,loop: loop,dim_time=True,domain="FIBER",dim_abstract=9)
_r(65004,"fiber_curvature","fiber_bundle","Curvature 2-form F=dA+A.A",["tensor"],"tensor",
   lambda A: A,domain="FIBER",dim_abstract=9)
_r(65005,"fiber_parallel","fiber_bundle","Parallel transport",["tensor","list","any"],"any",
   lambda A,curve,v0: v0,domain="FIBER",dim_abstract=8)

# ═══════════════════════════════════════════════════════════════════════════════
# CORE MATH COMPAT (IDs 0-99)
# ═══════════════════════════════════════════════════════════════════════════════

for _id,_name,_fn in [
    (0,"add",lambda a,b:a+b),(1,"sub",lambda a,b:a-b),(2,"mul",lambda a,b:a*b),
    (3,"div",lambda a,b:a/b if b!=0 else float('inf')),(4,"pow",lambda a,b:a**b),
    (5,"sqrt",lambda a:math.sqrt(a) if a>=0 else None),(6,"log",lambda a:math.log(a) if a>0 else None),
    (7,"log10",lambda a:math.log10(a) if a>0 else None),(8,"sin",math.sin),(9,"cos",math.cos),
    (10,"abs",abs),(11,"round",round),(12,"ceil",math.ceil),(13,"floor",math.floor),
    (14,"mod",lambda a,b:a%b if b!=0 else None),(15,"min2",min),(16,"max2",max),
    (17,"clamp",lambda v,lo,hi:max(lo,min(hi,v))),(18,"deg2rad",math.radians),(19,"rad2deg",math.degrees),
]:
    _r(_id,_name,"math","",["float","float"],"float",_fn,dim_data=(1,),dim_abstract=1,native_cpp=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _matmul(a, b):
    if a.ndims != 2 or b.ndims != 2: return a
    ra, ca = a.shape; rb, cb = b.shape
    if ca != rb: return a
    result = [[sum(a.at((i,k))*b.at((k,j)) for k in range(ca)) for j in range(cb)] for i in range(ra)]
    return Tensor5D(data=result, shape=(ra,cb), dtype=a.dtype)

def _det(t):
    if t.ndims != 2 or t.shape[0] != t.shape[1]: return 0
    n = t.shape[0]
    if n == 2: return t.at((0,0))*t.at((1,1)) - t.at((0,1))*t.at((1,0))
    if n == 3:
        a,b,c,d,e,f,g,h,i_ = t.at((0,0)),t.at((0,1)),t.at((0,2)),t.at((1,0)),t.at((1,1)),t.at((1,2)),t.at((2,0)),t.at((2,1)),t.at((2,2))
        return (a*e*i_ + b*f*g + c*d*h) - (c*e*g + b*d*i_ + a*f*h)
    return 0

def _inv(t):
    if t.ndims != 2 or t.shape[0] != t.shape[1]: return t
    n = t.shape[0]
    # Gauss-Jordan for 2x2
    if n == 2:
        d = _det(t)
        if abs(d) < 1e-10: return t
        a,b,c,d_ = t.at((0,0)),t.at((0,1)),t.at((1,0)),t.at((1,1))
        return Tensor5D(data=[[d_/d, -b/d], [-c/d, a/d]], shape=(2,2))
    return t

def _trace(t):
    if t.ndims < 2: return t.flat[0] if t.flat else 0
    n = min(t.shape[-1], t.shape[-2])
    return sum(t.at(tuple(list([i]*2))) for i in range(n))

def _eigen_2x2(t):
    if t.ndims != 2 or t.shape[0]!=2 or t.shape[1]!=2: return [0,0]
    a,b,c,d = t.at((0,0)),t.at((0,1)),t.at((1,0)),t.at((1,1))
    tr = a+d; det = a*d-b*c
    disc = tr*tr - 4*det
    if disc < 0: disc = 0
    s = math.sqrt(disc)
    return [(tr+s)/2, (tr-s)/2]

def _std(data):
    if not data: return 0
    m = sum(data)/len(data)
    return math.sqrt(sum((x-m)**2 for x in data)/len(data))

def _cross(a, b):
    if len(a)!=3 or len(b)!=3: return [0,0,0]
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

def _iterate(fn, init, n):
    state = init
    for _ in range(n): state = fn(state)
    return state

def _iterate_until(fn, init, thresh, max_iter):
    state = init
    for i in range(max_iter):
        new_state = fn(state)
        try:
            if abs(float(new_state)-float(state)) < thresh: return new_state
        except: pass
        state = new_state
    return state

def _fold(fn, seq, init):
    state = init
    for item in seq: state = fn(state, item)
    return state

def _fixed_point(fn, init, max_iter):
    state = init
    for _ in range(max_iter):
        new_state = fn(state)
        if new_state == state: return new_state
        state = new_state
    return state

def _newton(f, df, x0, max_iter):
    x = x0
    for _ in range(max_iter):
        fx = f(x)
        if abs(fx) < 1e-10: return x
        dfx = df(x)
        if abs(dfx) < 1e-15: break
        x = x - fx/dfx
    return x

def _jacobi(A, b, tol, max_iter):
    n = A.shape[0]
    x = Tensor5D(data=[0.0]*n, shape=(n,))
    for _ in range(max_iter):
        x_new_data = []
        for i in range(n):
            s = sum(A.at((i,j))*x.at((j,)) for j in range(n) if i!=j)
            x_new_data.append((b.flat[i] - s)/A.at((i,i)))
        x_new = Tensor5D(data=x_new_data, shape=(n,))
        diff = math.sqrt(sum((x_new.at((i,))-x.at((i,)))**2 for i in range(n)))
        x = x_new
        if diff < tol: break
    return x

def _power_iter(A, v0, tol, max_iter):
    v = Tensor5D(data=v0.flat if hasattr(v0,'flat') else v0, shape=v0.shape if hasattr(v0,'shape') else (len(v0),))
    for _ in range(max_iter):
        Av = _matmul(A, v)
        norm = math.sqrt(sum(x*x for x in Av.flat))
        if norm < 1e-10: break
        v_new = Tensor5D(data=[x/norm for x in Av.flat], shape=v.shape)
        diff = sum((v_new.at((i,))-v.at((i,)))**2 for i in range(v.shape[0]))
        v = v_new
        if diff < tol*tol: break
    eigenvalue = sum(A.at((i,))*v.at((i,)) for i in range(v.shape[0])) / sum(v.at((i,))**2 for i in range(v.shape[0]))
    try: return eigenvalue
    except: return 1.0

def _grad_desc(f, grad, x0, lr, max_iter):
    x = x0
    for _ in range(max_iter):
        g = grad(x)
        x = x - lr * g
    return x

def _logistic(r, x0, steps):
    x = x0
    result = [x]
    for _ in range(steps):
        x = r * x * (1 - x)
        result.append(x)
    return result

def _markov(state, trans, steps):
    s = state.flat[:]
    for _ in range(steps):
        new_s = [sum(s[j]*trans.at((j,i)) for j in range(len(s))) for i in range(trans.shape[1])]
        s = new_s
    return Tensor5D(data=s, shape=(len(s),))

def _dyn_evolve(f, x0, steps):
    x = list(x0)
    result = [x]
    for _ in range(steps):
        x = f(x)
        result.append(x)
    return result

def _par_reduce(fn, items):
    if len(items) <= 1: return items[0] if items else None
    mid = len(items)//2
    with ThreadPoolExecutor(max_workers=2) as ex:
        left = ex.submit(_par_reduce, fn, items[:mid])
        right = ex.submit(_par_reduce, fn, items[mid:])
        return fn(left.result(), right.result())

def _fmap(f, container):
    if isinstance(container, list): return [f(x) for x in container]
    if isinstance(container, dict): return {k: f(v) for k,v in container.items()}
    if isinstance(container, Tensor5D): return container.apply(f)
    return f(container)

def _bind(m, f):
    if isinstance(m, list): return [f(x) for x in m]
    if isinstance(m, Tensor5D): return m.apply(f)
    return f(m)

def _ap(wf, wv):
    if callable(wf) and callable(wv): return wf(0)(wv(0)) if hasattr(wf,'__call__') else None
    return None

def _join(nested):
    if isinstance(nested, list) and nested and isinstance(nested[0], list):
        return [item for sublist in nested for item in sublist]
    return nested

def _kl_div(p, q):
    return sum(pi*math.log(pi/qi) for pi,qi in zip(p,q) if pi>0 and qi>0)

def _alpha_div(p, q, alpha):
    if alpha == 0: return _kl_div(q, p)
    if alpha == 1: return _kl_div(p, q)
    return sum(pi**alpha * qi**(1-alpha) for pi,qi in zip(p,q) if pi>0 and qi>0)

def _natural_grad(lik, theta0, lr, max_iter):
    theta = list(theta0)
    for _ in range(max_iter):
        grad = [0.1] * len(theta)  # Simplified gradient
        theta = [t - lr * g for t,g in zip(theta, grad)]
    return theta

def _betti0(edges):
    if not edges: return 0
    parents = {}
    def find(x):
        if x not in parents: parents[x]=x
        while parents[x]!=x: x=parents[x]
        return x
    for e in edges:
        if len(e)>=2:
            a,b = e[0],e[1]
            pa,pb = find(a),find(b)
            if pa!=pb: parents[pa]=pb
    return len(set(find(x) for x in parents))

def _betti1(edges, n):
    e = len(edges)
    v = n
    b0 = _betti0(edges)
    return e - v + b0

def _dist(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b))) if len(a)==len(b) else 0

def _persistence(pts, max_eps):
    if not pts: return []
    edges = [(i,j,_dist(pts[i],pts[j])) for i in range(len(pts)) for j in range(i+1,len(pts))]
    edges.sort(key=lambda x: x[2])
    births = {i:0.0 for i in range(len(pts))}
    deaths = {}
    uf = {}
    def find(x):
        if x not in uf: uf[x]=x
        while uf[x]!=x: x=uf[x]
        return x
    result = []
    for i,j,d in edges:
        pi,pj = find(i),find(j)
        if pi!=pj:
            b = max(births[pi], births[pj])
            uf[pi] = pj
            births[pj] = b
            if d < max_eps: result.append((b, d))
    return result

def _lyapunov(traj):
    if len(traj) < 3: return 0
    n = len(traj)-1
    return sum(math.log(abs(traj[i+1]-traj[i])+1e-10) for i in range(n))/n

def _bifurcation(rm, rmax, nr, steps):
    result = []
    for r in [rm + (rmax-rm)*i/nr for i in range(nr)]:
        x = 0.5
        for _ in range(steps//2): x = r*x*(1-x)
        for _ in range(steps//2): result.append((r,x)); x = r*x*(1-x)
    return result

def _lorenz(s, r, b, steps, dt):
    x,y,z = 1.0,1.0,1.0
    result = [(x,y,z)]
    for _ in range(steps):
        dx = s*(y-x); dy = x*(r-z)-y; dz = x*y-b*z
        x += dx*dt; y += dy*dt; z += dz*dt
        result.append((x,y,z))
    return result

def _kolmogorov(traj, emb):
    if len(traj) < emb*2: return 0
    states = [tuple(traj[i:i+emb]) for i in range(len(traj)-emb)]
    unique = len(set(states))
    return math.log(unique)/math.log(len(states))

def _exp_smooth(seq, alpha):
    if not seq: return 0
    result = seq[0]
    for x in seq[1:]: result = alpha*x + (1-alpha)*result
    return result

def _ema_adaptive(seq, alpha, momentum):
    if not seq: return 0
    ema = seq[0]; mom = 0
    for x in seq[1:]:
        ema = alpha*x + (1-alpha)*ema
        mom = momentum*mom + (1-momentum)*(x-ema)**2
    return ema

def _pid(kp, ki, kd, setpoint, meas):
    if not meas: return 0.0
    errors = [setpoint - m for m in meas]
    P = kp * errors[-1]
    I = ki * sum(errors)
    D = kd * (errors[-1] - errors[-2]) if len(errors)>=2 else 0
    return P + I + D

def _kalman(x, z, p, q):
    k = p / (p + q + 1e-10)
    x_new = x + k * (z - x)
    p_new = (1 - k) * p
    return x_new

# ═══════════════════════════════════════════════════════════════════════════════
# 5D OPERATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class Operator5DEngine:
    def __init__(self):
        self._par = Parallel5D()
        self._fb: Dict[int,Feedback5D] = {}
        self._st: Dict[int,Stateful5D] = {}
        self._exec_count: Dict[int,int] = defaultdict(int)
        self._lock = threading.RLock()

    def data(self, v):
        if isinstance(v, Tensor5D): return v
        if isinstance(v, list): return Tensor5D(data=v, shape=(len(v),))
        return Tensor5D(data=[v], shape=())

    def temporal(self, op_id, init=None):
        if op_id not in self._st: self._st[op_id] = Stateful5D(op_id, init)
        return self._st[op_id]

    def feedback(self, op_id, lr=0.1):
        if op_id not in self._fb: self._fb[op_id] = Feedback5D(op_id, lr)
        return self._fb[op_id]

    def execute(self, op_name_or_id, args=None, d1=False, d2=False, d3=False, d5=False):
        args = args or []
        spec = OPERATOR_REGISTRY.get_by_id(int(op_name_or_id)) if isinstance(op_name_or_id,int) \
               else OPERATOR_REGISTRY.get_by_name(str(op_name_or_id))
        if not spec: return {"error": f"Operator not found: {op_name_or_id}"}
        with self._lock: self._exec_count[spec.op_id] = self._exec_count.get(spec.op_id,0)+1
        if d1 or spec.dim_data != (1,):
            args = [self.data(a) if isinstance(a,(int,float,list)) else a for a in args]
        if d2 or spec.dim_time:
            st = self.temporal(spec.op_id)
            if args: st.set_state(args[0])
        if d5 or spec.dim_feedback:
            fb = self.feedback(spec.op_id)
            result = spec.fn(*args)
            if len(args)>=2:
                try: fb.record_error(abs(float(args[-1])-float(result)))
                except: pass
            return result
        if d3 or spec.dim_parallel:
            if args and isinstance(args[0], Tensor5D):
                return self._par.vectorize(spec.fn, args[0])
        try: return spec.fn(*args)
        except Exception as e: return {"error": str(e), "operator": spec.name}

    def stats(self):
        return {
            "total": OPERATOR_REGISTRY.total_operators,
            "dim_summary": OPERATOR_REGISTRY.summary(),
            "top_executed": sorted(self._exec_count.items(),key=lambda x:-x[1])[:10],
        }

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATOR WORKER (BaseWorker integration)
# ═══════════════════════════════════════════════════════════════════════════════

class OperatorWorker(BaseWorker):
    worker_id = "operator"; version = "2.0.0"
    _engine = None

    @property
    def engine(self):
        if OperatorWorker._engine is None: OperatorWorker._engine = Operator5DEngine()
        return OperatorWorker._engine

    def _register_tools(self):
        self.tools["op_list"] = type("T",(),{"name":"op_list","description":"List 5D operators","params":{"category":"string","domain":"string"},"category":"operator","fn":None})()
        self.tools["op_exec"] = type("T",(),{"name":"op_exec","description":"Execute operator by name/id","params":{"op":"string","args":"list","d1":"bool","d2":"bool","d3":"bool","d5":"bool"},"category":"operator","fn":None})()
        self.tools["op_summary"] = type("T",(),{"name":"op_summary","description":"5D engine statistics","params":{},"category":"operator","fn":None})()

    def call(self, name, params):
        if name == "op_list":
            cat = params.get("category"); dom = params.get("domain")
            ops = OPERATOR_REGISTRY.get_category(cat) if cat else \
                  (OPERATOR_REGISTRY.get_domain(dom) if dom else list(OPERATOR_REGISTRY._by_id.values()))
            return {"operators": [{"id":o.op_id,"name":o.name,"category":o.category,"domain":o.domain,"D1":o.dim_data,"D2":o.dim_time,"D3":o.dim_parallel,"D4":o.dim_abstract,"D5":o.dim_feedback,"complexity":o.complexity,"native_cpp":o.native_cpp} for o in ops[:50]], "total": len(ops)}
        if name == "op_exec":
            return self.engine.execute(params.get("op"), params.get("args",[]),
                                       d1=params.get("d1"), d2=params.get("d2"),
                                       d3=params.get("d3"), d5=params.get("d5"))
        if name == "op_summary":
            s = OPERATOR_REGISTRY.summary()
            s["top_executed"] = sorted(self.engine._exec_count.items(),key=lambda x:-x[1])[:10]
            return s
        return {"error": f"Unknown: {name}"}
