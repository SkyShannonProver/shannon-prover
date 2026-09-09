require import AllCore Ring Distr FMap PROM.

require   Matrix.

clone import Matrix as Matrix_.

instance ring with R
  op rzero = ZR.zeror
  op rone  = ZR.oner
  op add   = ZR.( + )
  op opp   = ZR.([-])
  op mul   = ZR.( * )
  op expr  = ZR.exp
  op ofint = ZR.ofint

  proof oner_neq0 by apply ZR.oner_neq0
  proof addrA     by apply ZR.addrA
  proof addrC     by apply ZR.addrC
  proof addr0     by apply ZR.addr0
  proof addrN     by apply ZR.addrN
  proof mulr1     by apply ZR.mulr1
  proof mulrA     by apply ZR.mulrA
  proof mulrC     by apply ZR.mulrC
  proof mulrDl    by apply ZR.mulrDl
  proof expr0     by apply ZR.expr0
  proof ofint0    by apply ZR.ofint0
  proof ofint1    by apply ZR.ofint1
  proof exprS     by apply ZR.exprS
  proof ofintS    by apply ZR.ofintS
  proof ofintN    by apply ZR.ofintN.

op [lossless uniform full] duni_R : R distr.

op [lossless] dshort_R  : R distr.

op duni = dvector duni_R.

op dshort = dvector dshort_R.

op duni_matrix = dmatrix duni_R.

module type Adv_T = {
   proc guess(A : matrix, t : vector, uv : vector * R) : bool
}.

abbrev [-printing] m_transpose = trmx.

abbrev (`<*>`) = dotp.

abbrev (&+) = ZR.(+).

abbrev (&-) = ZR.(-).

module MLWE(Adv : Adv_T) = {

  proc main(b : bool) : bool = {
    var s, e, _A, u0, u1, t, e', v0, v1, b';

    _A <$ duni_matrix;
    s <$ dshort;
    e <$ dshort;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    t <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv.guess(_A, t, if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

type seed.

op H : seed -> matrix.

op [lossless] dseed : seed distr.

module type HAdv_T = {
   proc guess(sd : seed, t : vector, uv : vector * R) : bool
}.

module MLWE_H(Adv : HAdv_T) = {

  proc main(tr b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    sd <$ dseed;
    s <$ dshort;
    e <$ dshort;
    _A <- if tr then m_transpose (H sd) else H sd;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    t <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv.guess(sd, t, if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

theory MLWE_ROM.

clone import FullRO as RO_H with
  type in_t    = seed,
  type out_t   = matrix,
  op   dout    = fun (sd : seed) => duni_matrix,
  type d_in_t  = bool,
  type d_out_t = bool.

module type Ideal_RO = { include RO [get] }.

module type ROAdv_T(O : Ideal_RO) = {
   proc guess(sd : seed, t : vector, uv : vector * R) : bool
}.

module MLWE_RO(Adv : ROAdv_T,O : RO) = {

  proc main(tr : bool, b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    O.init();
    sd <$ dseed;
    s <$ dshort;
    e <$ dshort;
    _A <@ O.get(sd);
    _A <- if tr then m_transpose _A else _A;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    t <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv(O).guess(sd, t, if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

theory MLWE_vs_MLWE_ROM.

module B(A : ROAdv_T, O : RO) : Adv_T = {
  var _sd : seed
  var __A : matrix

  module FakeRO  = {
      proc get(sd : seed) : matrix = {
           var _Ares;
           _Ares <- __A;
           if (sd <> _sd) {
              O.sample(sd);
              _Ares <@ O.get(sd);
           }
           return _Ares;
      }
  }

  proc guess(_A : matrix, t : vector, uv : vector * R) : bool = {
    var sd, b;
    sd <$ dseed;
    _sd <- sd;
    __A <- _A;
    O.init();
    b <@ A(FakeRO).guess(sd,t,uv);
    return b;
  }
}.

module Bt(A : ROAdv_T, O : RO) : Adv_T = {
  var _sd : seed
  var __A : matrix

  module FakeRO  = {
      proc get(sd : seed) : matrix = {
           var _Ares;
           _Ares <- __A;
           if (sd <> _sd) {
              O.sample(sd);
              _Ares <@ O.get(sd);
           }
           return _Ares;
      }
  }

  proc guess(_A : matrix, t : vector, uv : vector * R) : bool = {
    var sd, b;
    sd <$ dseed;
    _sd <- sd;
    __A <- m_transpose _A;
    O.init();
    b <@ A(FakeRO).guess(sd,t,uv);
    return b;
  }

}.

end MLWE_vs_MLWE_ROM.

end MLWE_ROM.

theory MLWE_SMP.

clone import FullRO as RO_SMP.

module type SMP_RO = { include RO [get] }.

module type Sampler(O : SMP_RO) = {
    proc sampleA(sd : seed) : matrix
    proc sampleAT(sd : seed) : matrix
}.

module type PSampler = {
    proc sampleA(sd : seed) : matrix
    proc sampleAT(sd : seed) : matrix
}.

module type SAdv_T(O : SMP_RO) = {
   proc interact(sd : seed, t : vector) : unit
   proc guess(uv : vector * R) : bool
}.

module MLWE_SMP(Adv : SAdv_T, S: Sampler, O : RO) = {
  proc main(tr : bool, b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    O.init();

    sd <$ dseed;
    t <$ duni;
    Adv(O).interact(sd,t);

    if (tr) { _A <@ S(O).sampleAT(sd); }
    else    { _A <@ S(O).sampleA(sd);  }

    s <$ dshort;
    e <$ dshort;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv(O).guess(if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

end MLWE_SMP.

theory SMP_vs_ROM.

import MLWE_ROM.

clone import MLWE_SMP with
  type RO_SMP.in_t    = seed,
  type RO_SMP.out_t   = matrix,
  op   RO_SMP.dout    = fun (sd : seed) => duni_matrix,
  type RO_SMP.d_in_t  = bool,
  type RO_SMP.d_out_t = bool.

import RO_H.

module (S : Sampler) (H : SMP_RO) = {
  proc sampleA(sd : seed) : matrix = {
      var _A;
      _A <@ H.get(sd);
      return _A;
  }
  proc sampleAT(sd : seed) : matrix = {
      var _A;
      _A <@ H.get(sd);
      return trmx _A;
  }
}.

module (BS(Adv : SAdv_T, S : Sampler) : ROAdv_T) (O : SMP_RO) = {
   proc guess(sd : seed, t : vector,uv : vector * R) = {
       var b;
       Adv(O).interact(sd,t);
       b <@ Adv(O).guess(uv);
       return b;
   }
}.

import MLWE_vs_MLWE_ROM.

module MLWE_SMPs(Adv : SAdv_T, S: Sampler, O : RO_H.RO) = {
  proc main(tr : bool, b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    O.init();

    sd <$ dseed;
    t <$ duni;
    O.sample(sd);
    Adv(O).interact(sd,t);

    if (tr) { _A <@ S(O).sampleAT(sd); }
    else    { _A <@ S(O).sampleA(sd);  }

    s <$ dshort;
    e <$ dshort;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv(O).guess(if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

module MLWE_ROs(Adv : ROAdv_T,O : RO_H.RO) = {
  proc main(tr : bool, b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    O.init();
    sd <$ dseed;
    s <$ dshort;
    e <$ dshort;
    O.sample(sd);
    _A <@ O.get(sd);
    _A <- if tr then m_transpose _A else _A;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    t <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;

    b' <@ Adv(O).guess(sd, t, if b then (u1,v1) else (u0,v0));
    return b';
   }

}.

module DLeftAux(A : SAdv_T)  (O : RO) = {
     proc run(tr : bool,b : bool) : bool = {
        var sd,t,_A,s,e,u0,u1,e',v0,v1,b';
        sd <$ dseed;
        s <$ dshort;
        e <$ dshort;
        O.sample(sd);
        _A <@ O.get(sd);
        _A <- if tr then trmx _A else _A;
        u0 <- _A *^ s + e;
        u1 <$ duni;
        t <$ duni;
        e' <$ dshort_R;
        v0 <- (t `<*>` s) &+ e';
        v1 <$ duni_R;
        b' <@ BS(A, S, O).guess(sd, t,if b then (u1, v1) else (u0, v0));
        return b';
     }
}.

module (DLeft(A : SAdv_T) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DLeftAux(A,O).run(false,b);
         return b';
     }
}.

module (DLeftT(A : SAdv_T) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DLeftAux(A,O).run(true,b);
         return b';
     }
}.

module DRightAux(A : SAdv_T)   (O : RO) = {
     proc run(tr : bool, b : bool) : bool = {
        var sd,t,_A,s,e,u0,u1,e',v0,v1,b';
        sd <$ dseed;
        t <$ duni;
        O.sample(sd);
        A(O).interact(sd, t);
        if (tr) { _A <@ S(O).sampleAT(sd); }
        else    { _A <@ S(O).sampleA(sd);  }
        s <$ dshort;
        e <$ dshort;
        u0 <- _A *^ s + e;
        u1 <$ duni;
        e' <$ dshort_R;
        v0 <- (t `<*>` s) &+ e';
        v1 <$ duni_R;
        b' <@ A(O).guess(if b then (u1, v1) else (u0, v0));
        return b';
     }
}.

module (DRight(A : SAdv_T) : RO_Distinguisher)  (O : RO) = {

     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DRightAux(A,O).run(false,b);
         return b';
     }
}.

module (DRightT(A : SAdv_T) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DRightAux(A,O).run(true,b);
         return b';
     }
}.

import FullEager.

end SMP_vs_ROM.

theory SMP_vs_ROM_IND.

import MLWE_ROM.

import MLWE_SMP.

import RO_SMP.

module type Simulator_t(O : Ideal_RO) = {
   proc init() : unit {}
   include SMP_RO
}.

module type Distinguisher_t(S : PSampler, H : SMP_RO) = {
   proc distinguish(tr b : bool, sd : seed) : bool
}.

module WIndfReal(D : Distinguisher_t, S : Sampler, O : RO) = {
   proc main(tr b : bool) : bool = {
        var sd,b';
        O.init();
        sd <$ dseed;
        b' <@ D(S(O),O).distinguish(tr, b ,sd);
        return b';
   }
}.

module WIndfIdeal(D : Distinguisher_t, Sim : Simulator_t, O : RO_H.RO) = {
   proc main(tr b : bool) : bool = {
        var sd,b';
        O.init();
        Sim(O).init();
        sd <$ dseed;
        b' <@ D(SMP_vs_ROM.S(O),Sim(O)).distinguish(tr, b,sd);
        return b';
   }
}.

module (BS(Adv : SAdv_T, Sim : Simulator_t) : ROAdv_T) (H : Ideal_RO) = {
   proc guess(sd : seed, t : vector,uv : vector * R) = {
       var b;
       Sim(H).init();
       Adv(Sim(H)).interact(sd,t);
       b <@ Adv(Sim(H)).guess(uv);
       return b;
   }
}.

import MLWE_vs_MLWE_ROM.

module (D(A : SAdv_T) : Distinguisher_t) (S : PSampler, H : SMP_RO) = {
  proc distinguish(tr b : bool, sd : seed) : bool = {
    var _A,t,s,e,u0,u1,e',v0,v1,b';
    t <$ duni;
    A(H).interact(sd,t);
    if (tr) { _A <@ S.sampleAT(sd); }
    else    { _A <@ S.sampleA(sd);  }
    s <$ dshort;
    e <$ dshort;
    u0 <- _A *^ s + e;
    u1 <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;
    b' <@ A(H).guess(if b then (u1, v1) else (u0, v0));
    return b';
  }
}.

import RO_H.

import FullEager.

module DLeftAux(A : SAdv_T, Sim : Simulator_t)  (O : RO) = {
     proc run(tr : bool,b : bool) : bool = {
        var sd,t,_A,s,e,u0,u1,e',v0,v1,b';
        sd <$ dseed;
        s <$ dshort;
        e <$ dshort;
        O.sample(sd);
        _A <@ O.get(sd);
        _A <- if tr then trmx _A else _A;
        u0 <- _A *^ s + e;
        u1 <$ duni;
        t <$ duni;
        e' <$ dshort_R;
        v0 <- (t `<*>` s) &+ e';
        v1 <$ duni_R;
        b' <@ BS(A, Sim, O).guess(sd, t,if b then (u1, v1) else (u0, v0));
        return b';
     }
}.

module (DLeft(A : SAdv_T, Sim : Simulator_t) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DLeftAux(A,Sim,O).run(false,b);
         return b';
     }
}.

module (DLeftT(A : SAdv_T, Sim : Simulator_t) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DLeftAux(A,Sim,O).run(true,b);
         return b';
     }
}.

module DRightAux(A : SAdv_T, Sim : Simulator_t)   (O : RO) = {
     proc run(tr : bool, b : bool) : bool = {
        var sd,t,_A,s,e,u0,u1,e',v0,v1,b';
        sd <$ dseed;
        t <$ duni;
        O.sample(sd);
        Sim(O).init();
        A(Sim(O)).interact(sd, t);
        if (tr) { _A <@ O.get(sd);  _A <- trmx _A; }
        else {  _A <@ O.get(sd); }
        s <$ dshort;
        e <$ dshort;
        u0 <- _A *^ s + e;
        u1 <$ duni;
        e' <$ dshort_R;
        v0 <- (t `<*>` s) &+ e';
        v1 <$ duni_R;
        b' <@ A(Sim(O)).guess(if b then (u1, v1) else (u0, v0));
        return b';
     }
}.

module (DRight(A : SAdv_T, Sim : Simulator_t) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DRightAux(A,Sim,O).run(false,b);
         return b';
     }
}.

module (DRightT(A : SAdv_T, Sim : Simulator_t) : RO_Distinguisher)  (O : RO) = {
     proc distinguish(b : bool) : bool = {
         var b';
         b' <@ DRightAux(A,Sim,O).run(true,b);
         return b';
     }
}.

module MLWE_ROs(Adv : ROAdv_T,O : RO) = {
  proc main(tr : bool, b : bool) : bool = {
    var sd, s, e, _A, u0, u1, t, e', v0, v1, b';

    O.init();
    sd <$ dseed;
    s <$ dshort;
    e <$ dshort;
    O.sample(sd);
    _A <@ O.get(sd);
    _A <- if tr then m_transpose _A else _A;
    u0 <- _A *^ s + e;
    u1 <$ duni;

    t <$ duni;
    e' <$ dshort_R;
    v0 <- (t `<*>` s) &+ e';
    v1 <$ duni_R;
    b' <@ Adv(O).guess(sd, t,if b then (u1, v1) else (u0, v0));
    return b';
   }

}.

module WIndfIdeals(D : Distinguisher_t, Sim : Simulator_t, O : RO_H.RO) = {
   proc main(tr b : bool) : bool = {
        var sd,b';
        O.init();
        Sim(O).init();
        sd <$ dseed;
        O.sample(sd);
        b' <@ D(SMP_vs_ROM.S(O),Sim(O)).distinguish(tr, b,sd);
        return b';
   }
}.

end SMP_vs_ROM_IND.
