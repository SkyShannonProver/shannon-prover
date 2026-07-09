require import AllCore List Int IntDiv Real FMap Distr DBool DList DProd FSet PROM SplitRO FelTactic.
require import FinType.

require (****) Subtype Ske RndProd Indistinguishability Monoid EventPartitioning.
import StdOrder IntOrder RealOrder.

(* TODO: this come from eclib/JUtil.ec *)
op map2 ['a, 'b, 'c] (f:'a -> 'b -> 'c) (s:'a list) (t:'b list) = 
  with s = "[]"   , t = "[]" => []
  with s = _ :: _ , t = "[]" => []
  with s = "[]"   , t = _ :: _ => []
  with s = x :: s', t = y :: t' => f x y :: map2 f s' t'.

lemma map2_zip (f:'a -> 'b -> 'c) s t : 
  map2 f s t = map (fun (p:'a * 'b) => f p.`1 p.`2) (zip s t).
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma size_map2 (f:'a -> 'b -> 'c) (l1:'a list) l2 : size (map2 f l1 l2) = min (size l1) (size l2).
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma nth_map2 dfla dflb dflc (f:'a -> 'b -> 'c) (l1:'a list) l2 i: 
  0 <= i < min (size l1) (size l2) => 
  nth dflc (map2 f l1 l2) i = f (nth dfla l1 i) (nth dflb l2 i).
proof.
(* COMPLETE THIS *)
  admit.
qed.

(* -------------------------------------------------------------------------- *)

theory Byte.
  type byte.

  clone include MFinite with 
    type t <- byte
    rename "dunifin" as "dbyte".
   
  op zero : byte.
  op (+^) : byte -> byte -> byte.

  clone import Monoid as MB with 
    type t <- byte,
    op idm <- zero,
    op (+) <- (+^).

  axiom addK b : b +^ b = zero.

  lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

end Byte.
import Byte.

type bytes = byte list.

(* -------------------------------------------------------------------------- *)
theory Key.
  type key.     (* chacha key *)
  clone include MFinite with 
    type t <- key
    rename "dunifin" as "dkey".
end Key.
import Key.

theory Nonce.
  type nonce.     (* chacha nonce *)
  clone MFinite with 
    type t = nonce
    rename "dunifin" as "dnonce".
end Nonce.
import Nonce.

(* -------------------------------------------------------------------------- *)
theory C.

  op max_counter : int.

  axiom gt0_max_counter : 0 < max_counter.

  subtype counter =
    { i : int | 0 <= i < max_counter + 1 }
    rename "ofint", "toint".

  realize inhabited.
  proof. by exists 0; smt(gt0_max_counter). qed.

  clone FinType with 
    type t  = counter,
    op enum = List.map ofintd (iota_ 0 (max_counter + 1))
    proof *.
  realize enum_spec.  
  proof.
    move=> c; rewrite count_uniq_mem.
    + apply map_inj_in_uniq; last by apply iota_uniq.
      move=> x y /mema_iota hx /mema_iota hy heq.
      by rewrite -(ofintdK x) 1:// -(ofintdK y) 1:// heq.
    have -> // : c \in enum.  
    rewrite /enum mapP; exists (toint c).
    by rewrite mema_iota /= tointP tointKd.
  qed.

end C.

clone FinProdType as NonceCount with
  type t1 <- nonce, type t2 <- C.counter,
  theory FT1 <- Nonce.MFinite.Support, theory FT2 <- C.FinType.

(* -------------------------------------------------------------------------- *)

abstract theory GenBlock.
  op block_size : int.
  axiom ge0_block_size : 0 <= block_size.

  subtype block = { l : bytes | size l = block_size }
    rename "block_of_bytes", "bytes_of_block".

  realize inhabited.
  proof.
    exists (nseq block_size witness).
    smt(size_nseq ge0_block_size).
  qed.

  op dblock =  dmap (dlist dbyte block_size) block_of_bytesd.

  lemma dblock_ll : is_lossless dblock.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.
  
  lemma dblock_uni: is_uniform dblock.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  lemma dblock_fu: is_full dblock.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.
 
  lemma dblock_funi: is_funiform dblock.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  op zero = block_of_bytesd (mkseq (fun _ => Byte.zero) block_size).

  op (+^) (b1 b2:block) =
     block_of_bytesd (map2 (+^) (bytes_of_block b1) (bytes_of_block b2)).
 
  lemma nth_xor x y i :
     0 <= i < block_size =>
     nth Byte.zero (bytes_of_block (x +^ y)) i =
     nth Byte.zero (bytes_of_block x) i +^ nth Byte.zero (bytes_of_block y) i.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  lemma nth_zero i : nth Byte.zero (bytes_of_block zero) i = Byte.zero. 
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  clone import Monoid as MB with 
    type t <- block,
    op idm <- zero,
    op (+) <- (+^)
    proof *.
  realize Axioms.addmA.
  proof.
    move=> x y z; apply bytes_of_block_inj.
    apply (eq_from_nth Byte.zero); rewrite !bytes_of_blockP //.
    by move=> i hi; rewrite !nth_xor // Byte.MB.addmA. 
  qed.
  realize Axioms.addmC.
  proof.
    move=> x y; apply bytes_of_block_inj.
    apply (eq_from_nth Byte.zero); rewrite !bytes_of_blockP //.
    by move=> i hi; rewrite !nth_xor // Byte.MB.addmC.
  qed.
  realize Axioms.add0m.
  proof.
    move=> x; apply bytes_of_block_inj.
    apply (eq_from_nth Byte.zero); rewrite !bytes_of_blockP //.
    by move=> i hi; rewrite !nth_xor // nth_zero Byte.MB.add0m.
  qed.

  lemma addK b : b +^ b = zero.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  lemma xorK1_genblock b1 b2 : b1 = b1 +^ b2 +^ b2.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

end GenBlock.

(* block : [poly_tin; poly_tout; extra_block] *)
clone import GenBlock as Poly_in 
  rename "block" as "poly_in".
hint solve 0 random : dpoly_in_ll dpoly_in_funi dpoly_in_fu. 

clone import GenBlock as Poly_out 
  rename "block" as "poly_out".
hint solve 0 random : dpoly_out_ll dpoly_out_funi dpoly_out_fu. 

clone import GenBlock as TPoly with 
  op block_size = poly_in_size + poly_out_size 
  proof ge0_block_size by smt (ge0_poly_in_size ge0_poly_out_size) 
  rename "block" as "poly".
hint solve 0 random : dpoly_ll dpoly_funi dpoly_fu. 

clone import GenBlock as Extra_block
  rename "block" as "extra_block".
hint solve 0 random : dextra_block_ll dextra_block_funi dextra_block_fu. 
 
clone import GenBlock as Block
  with op block_size = poly_in_size + poly_out_size + extra_block_size
  proof ge0_block_size by smt (ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
hint solve 0 random : dblock_ll dblock_funi dblock_fu. 

axiom gt0_block_size : 0 < block_size.

op extend (bs:bytes) : block = 
  Block.block_of_bytesd
    (take block_size bs ++ mkseq (fun _ => Byte.zero)
    (block_size - size bs)).

lemma nth_extend m i : 0 <= i < block_size => 
  nth Byte.zero (bytes_of_block (extend m)) i = 
    if i < size m then  nth Byte.zero m i else Byte.zero.
proof.
(* COMPLETE THIS *)
  move=> [hi0 hib]; rewrite /extend.
  smt(Block.block_of_bytesdK size_cat size_take size_mkseq nth_cat nth_take nth_mkseq ge0_block_size).
qed.

(* -------------------------------------------------------------------------- *)
op chacha20_block : key -> nonce -> C.counter -> block.

(* -------------------------------------------------------------------------- *)
(* Functional definition of chacha20                                          *)

op gen_ctr_round (merge: bytes -> block -> bytes) genblock (k:key) (n:nonce) (round_st : bytes * bytes * int) =
  let (cph,m,c) = round_st in
  let stream = genblock k n (C.ofintd c) in
  (cph ++ merge m stream, drop block_size m, c + 1).

op gen_CTR_encrypt_bytes merge genblock key nonce counter m =
  let len = size m in
  let rounds = (len %/ block_size) + b2i (len %% block_size <> 0) in 
  (iter rounds (gen_ctr_round merge genblock key nonce) ([], m, counter)).`1.

op take_xor (m:bytes) (stream : block) = 
  take (size m) (bytes_of_block (extend m +^ stream)).

op map2_xor (m:bytes) (stream : block) = 
  map2 Byte.(+^) m (bytes_of_block stream).

(* This correspond exactly to the definition used in the functional correctness proof *)

op chacha20_CTR_encrypt_bytes key nonce counter m =
  gen_CTR_encrypt_bytes map2_xor chacha20_block key nonce counter m.

lemma take_xor_map2_xor m str: map2_xor m str = take_xor m str.
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma iter_gen_ctr_round_nil_cat merge genblock k n c m i j : 
  let round = gen_ctr_round merge genblock k n in
  iter i round (c, m, j) = 
     let (c', m', j') = iter i round ([], m, j) in
     (c ++ c', m', j').
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma iter_gen_ctr_round_S merge genblock k n c m i j: 
  let round = gen_ctr_round merge genblock k n in
  0 <= i =>
  iter (i + 1) round (c, m, j) = 
    let (c', m', j') = iter i round ([], drop block_size m, j + 1) in 
    (c ++ merge m (genblock k n (C.ofintd j)) ++ c', m', j').
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma iter_gen_ctr_round_nil merge genblock k n i j:
  (forall str, merge [] str = []) =>
  let round = gen_ctr_round merge genblock k n in
  iter i round ([], [],j) = ([], [], max j (j + i)).
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma gen_CTR_encrypt_bytes0 merge genblock k n c :
  (forall str, merge [] str = []) =>
  gen_CTR_encrypt_bytes merge genblock k n c [] = [].
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma gen_CTR_encrypt_bytes_cons merge genblock k n c m:
  (forall str, merge [] str = []) =>
  gen_CTR_encrypt_bytes merge genblock k n c m = 
  merge m (genblock k n (C.ofintd c)) ++ 
    gen_CTR_encrypt_bytes merge genblock k n (c+1) (drop block_size m).
proof.
(* COMPLETE THIS *)
  admit.
qed.

(* -------------------------------------------------------------------------- *)
(* Functional definition of poly1305                                          *) 

type polynomial.

op topol : bytes -> bytes -> polynomial.
op max_ad_size : int.
op max_cipher_size : int.
axiom max_cipher_size_ok : max_cipher_size <= C.max_counter * block_size.

op valid_topol (a:bytes) (c:bytes) = 
  size a <= max_ad_size /\ size c <= max_cipher_size.

axiom topol_inj a1 c1 a2 c2:
  valid_topol a1 c1 => valid_topol a2 c2 =>
  topol a1 c1 = topol a2 c2 => a1 = a2 /\ c1 = c2.

op poly1305_eval : poly_in -> polynomial -> poly_out.

op (+) : poly_out -> poly_out -> poly_out.
op (-) : poly_out -> poly_out -> poly_out.

op poly1305 (r:poly_in) (s:poly_out) (p:polynomial) = s + poly1305_eval r p.

op mk_rs (b:block) = 
  let b = take (poly_in_size + poly_out_size) (bytes_of_block b) in
  (
    Poly_in.poly_in_of_bytesd (take poly_in_size b),
    Poly_out.poly_out_of_bytesd (drop poly_in_size b)
  ).

op genpoly1305 genblock (k:key) (n:nonce) (p:polynomial) = 
  let (r,s) = mk_rs (genblock k n (C.ofintd 0)) in
  poly1305 r s p.
  
axiom poly_out_sub_add (p1 p2: poly_out) : p1 = p1 - p2 + p2.
axiom poly_out_add_sub (p1 p2: poly_out) : p1 = p1 + p2 - p2.
axiom poly_out_add_sub' (p1 p2: poly_out) : p1 = p1 + (p2 - p2).
axiom poly_out_swap (t p1 p2:poly_out) : t - p1 + p2 = t + (p2 - p1).

(* -------------------------------------------------------------------------- *)
type message = bytes.
type associated_data = bytes.
type tag = poly_out.

type plaintext = nonce * associated_data * message.
type ciphertext = nonce * associated_data * message * tag.

clone import Ske.SKE_RND with
  type key <- key,
  type plaintext <- plaintext,
  type ciphertext <- ciphertext.

module ChaChaPoly = {
  proc init() = {}
  
  proc kg () = { var k; k <$ dkey; return k; }
  
  proc enc (k : key, nap : nonce * associated_data * message) : 
     nonce * associated_data * message * tag = {
    var n, a, p, c, t;
    (n,a,p) <- nap;
    c <- gen_CTR_encrypt_bytes take_xor chacha20_block k n 1 p;
    t <- genpoly1305  chacha20_block k n (topol a c);
    return (n,a,c,t);
  }
  
  proc dec(k : key, nact : nonce * associated_data * message * tag) :
    (nonce * associated_data * message) option = {
    var n, a, c, p, t, t', result;
    result <- None;
    (n,a,c,t) <- nact;
    t' <- genpoly1305 chacha20_block k n (topol a c);
    if (t = t') {
      p <- gen_CTR_encrypt_bytes take_xor chacha20_block k n 1 c;
      result <- Some (n,a,p);
    }
    return result;
  }

}.

(* --------------------------------------------------------------------------- *)

module type CC = {
  proc cc (k:key, n:nonce, c: C.counter) : block
}.

module type FCC = {
  proc init () : unit
  include CC
}.

module ChaCha(CC:CC) = {
  proc enc(k:key, n:nonce, p:message) : bytes = {
    var i, z, c;
    c     <- [];
    i     <- 1;
    while (p <> []) {
      z <@ CC.cc(k, n, C.ofintd i);
      c <- c ++ take (size p) (bytes_of_block (extend p +^ z));
      p <- drop block_size p;
      i <- i + 1;
    }
    return c;
  }
}.

module Poly(CC:CC) = {
  proc mac(k:key, n: nonce, a: associated_data, c: message) : tag = {
    var b, r, s;
    b     <@ CC.cc(k, n, C.ofintd 0);
    (r,s) <- mk_rs b; 
    return poly1305 r s (topol a c);
  }
}.

module GenChaChaPoly(CC:FCC) : SKE = {
  include CC[init]
  include ChaChaPoly[kg]
  
  proc enc (k : key, nap : nonce * associated_data * message) : 
    nonce * associated_data * message * tag = {
    var n, a, p, c, t;
    (n,a,p) <- nap;
    c <@ ChaCha(CC).enc(k,n,p);
    t <@ Poly(CC).mac(k,n,a,c);
    return (n,a,c,t);
  }

  proc dec(k : key, nact : nonce * associated_data * message * tag) :
    (nonce * associated_data * message) option = {
    var n, a, c, p, t, t', result;
    result <- None;
    (n,a,c,t) <- nact;
    t' <@ Poly(CC).mac(k,n,a,c);
    if (t = t') {
      p <@ ChaCha(CC).enc(k,n,c);
      result <- Some (n,a,p);
    }
    return result;
  }
}.

(* --------------------------------------------------------------------- *)
(* We want to bound :
   `| Pr[CCA_game(A, Real_Oracles(ChaChaPoly(CCperm))).main() : res] 
      - Pr[CCA_game(A, Ideal_Oracles).main() : res] |

   We process as follow: 
    `| Pr[CCA_game(A, Real_Oracles(ChaChaPoly(CCperm))).main() : res] 
        - Pr[CCA_game(A, Ideal_Oracles).main() : res] | <= 
Step 1 indistinguishability from a random oracle:
    `| Pr[CCA_game(A, Real_Oracles(ChaChaPoly(CCperm))).main() : res] 
        - Pr[CCA_game(A, Real_Oracles(ChaChaPoly(RO))).main() : res] + 
    `| Pr[CCA_game(A, Real_Oracles(ChaChaPoly(RO))).main() : res] 
        - Pr[CCA_game(A, Ideal_Oracles).main() : res] | 

Step 2 : CCA <= CPA + UFCMA + extra stuff on RO
    
Step 3 : enc return random 
         => CPA ~ Ideal

Step 4 : UFCMA with random enc
   
*)

abstract theory OpCC.
  type globS.
  op cc : globS -> key -> nonce -> C.counter -> block.

  module type Init = {
    proc init () : globS
  }.

  module OCC (I:Init) : FCC = {
    var gs : globS

    proc init () : unit = {
      gs <@ I.init();
    }
    
    proc kg () : key = {
      var k;
      k <$ dkey;
      return k;
    }

    proc cc (k:key, n:nonce, c:C.counter) = {
      return cc gs k n c;
    }
  }.

  module OChaChaPoly (I:Init) = {
    include OCC(I) [init, kg]

    proc enc (k : key, nap : nonce * associated_data * message) : 
       nonce * associated_data * message * tag = {
      var n, a, p, c, t;
      (n,a,p) <- nap;
      c <- gen_CTR_encrypt_bytes take_xor (cc OCC.gs) k n 1 p;
      t <- genpoly1305  (cc OCC.gs) k n (topol a c);
      return (n,a,c,t);
    }

    proc dec(k : key, nact : nonce * associated_data * message * tag) :
      (nonce * associated_data * message) option = {
      var n, a, c, p, t, t', result;
      result <- None;
      (n,a,c,t) <- nact;
      t' <- genpoly1305 (cc OCC.gs) k n (topol a c);
      if (t = t') {
        p <- gen_CTR_encrypt_bytes take_xor (cc OCC.gs) k n 1 c;
        result <- Some (n,a,p);
      }
      return result;
    }
  }.
    
  module type Adv (S:SKE) = { 
    proc main () : bool 
  }.

  section PROOFS.
  
    declare module I <: Init { -OCC }.
    declare module A <: Adv { -OCC, -I}.
   
    phoare chacha_spec k0 n0 p0 gs0 : 
      [ChaCha(OCC(I)).enc : 
        k = k0 /\ n = n0 /\ p = p0 /\ OCC.gs = gs0 ==>
        res = gen_CTR_encrypt_bytes take_xor (cc gs0) k0 n0 1 p0] = 1%r.
    proof.
    (* COMPLETE THIS *)
      admit.
    qed.

    phoare poly_spec k0 n0 a0 c0 gs0 :
      [Poly(OCC(I)).mac : 
        k = k0 /\ n = n0 /\ a = a0 /\ c = c0 /\ OCC.gs = gs0 ==>
        res = genpoly1305 (cc gs0) k0 n0 (topol a0 c0)] = 1%r.
    proof.
    (* COMPLETE THIS *)
      admit.
    qed.

    equiv CCP_OCCP : A(GenChaChaPoly(OCC(I))).main ~ A(OChaChaPoly(I)).main : 
       ={glob A, glob I, glob OCC, arg} ==> ={res, glob A, glob I, glob OCC}.
    proof.
    (* COMPLETE THIS *)
      admit.
    qed.
  
    lemma pr_CCP_OCCP &m : 
      Pr[A(GenChaChaPoly(OCC(I))).main() @ &m : res] = 
      Pr[A(OChaChaPoly(I)).main() @ &m : res].
    proof.
    (* COMPLETE THIS *)
      admit.
    qed.

  end section PROOFS.

end OpCC.

clone import FullRO with
  type in_t    <- (nonce*C.counter),
  type out_t   <- block, 
  type d_in_t  <- unit,
  type d_out_t <- bool,
  op   dout    <- fun _ => dblock
proof *.

clone import FinEager as FiniteRO with
  theory FinFrom <- NonceCount
proof *.

module IndBlock = {
  var k : key

  proc init () = { k <$ dkey; }
  proc f (n:nonce, c:C.counter) = {
    return chacha20_block k n c;
  }
}.

module IndRO = {
  proc init = RO.init
  proc f = RO.get
}.

clone Indistinguishability as Indist with 
  type t_in <- nonce * C.counter,
  type t_out <- block.
  
module D(A:CCA_Adv, RO: Indist.Oracle) = {
  module O = {
    proc init () = {}
    
    module ChaCha = {
      proc enc(n:nonce, p:message) : bytes = {
        var i, z, c;
        c     <- [];
        i     <- 1;
        while (p <> []) {
          z <@ RO.f(n, C.ofintd i);
          c <- c ++ take (size p) (bytes_of_block (extend p +^ z));
          p <- drop block_size p;
          i <- i + 1;
        }
        return c;
      }
    }

    module Poly = {
      proc mac(n: nonce, a: associated_data, c: message) : tag = {
        var b, r, s;
        b     <@ RO.f(n, C.ofintd 0);
        (r,s) <- mk_rs b; 
        return poly1305 r s (topol a c);
      }
    }

    proc enc (nap : nonce * associated_data * message) : 
      nonce * associated_data * message * tag = {
      var n, a, p, c, t;
      (n,a,p) <- nap;
      c <@ ChaCha.enc(n,p);
      t <@ Poly.mac(n,a,c);
      return (n,a,c,t);
    }
  
    proc dec(nact : nonce * associated_data * message * tag) :
      (nonce * associated_data * message) option = {
      var n, a, c, p, t, t', result;
      result <- None;
      (n,a,c,t) <- nact;
      t' <@ Poly.mac(n,a,c);
      if (t = t') {
        p <@ ChaCha.enc(n,c);
        result <- Some (n,a,p);
      }
      return result;
    }
  }
  
  proc guess = CCA_game(A,O).main

}.

module CCRO(RO:RO) = {
  proc init = RO.init 
  proc cc(k : key, n : nonce, c : C.counter) : block = {
    var result;
    result <@ RO.get (n,c);
    return result;
  }
}.

op test_poly (n:nonce) (lc:ciphertext list) r s = 
  let pts = map (fun (c:ciphertext) => (topol c.`2 c.`3, c.`4))
                (List.filter (fun (c:ciphertext) => c.`1 = n) lc) in
  List.has (fun (pt:polynomial*tag) => pt.`2 = poly1305 r s pt.`1) pts.

module UFCMA_poly(A:CCA_Adv, RO:RO) = {
  proc main () = {
    var ns, forged, i, n, bl, r, s;
    CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(RO)))).main();
    ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
    forged <- false;
    i <- 0;
    while (i < size ns) {
      n  <- List.nth witness ns i;
      bl <@ RO.get(n,C.ofintd 0);
      (r,s) <- mk_rs bl; 
      forged <- forged || test_poly n Mem.lc r s;
      i <- i + 1;
    }
    return forged;
  }
}.
       
abstract theory Step1_2.

clone import OpCC as OpCCinit with 
  type globS <- unit,
  op cc <- fun _ => chacha20_block.
 
module I_stateless = {
  proc init () = {}
}.

clone import OpCC as OpCCRO with 
  type globS = (nonce * C.counter, block) fmap,
  op cc m k n c <- oget m.[(n,c)].
 
module IFinRO = {
  proc init () = { 
    FinRO.init();
    return RO.m;
  }
}.

op get (gs:OpCCRO.globS) (k:key) n c = oget gs.[(n,c)].

clone import CCA_CPA_UFCMA as CCA_UFCMA with 
  type globS <- OpCCRO.globS,
  op enc gs k (nap:plaintext) =  
    let (n,a,p) = nap in
    let c = gen_CTR_encrypt_bytes take_xor (get gs) k n 1 p in
    let t = genpoly1305 (get gs) k n (topol a c) in
    (n,a,c,t), 
  op dec gs k (nact:ciphertext) = 
    let (n,a,c,t) = nact in
    let t' = genpoly1305 (get gs) k n (topol a c) in
    if (t = t') then
      Some (n,a, gen_CTR_encrypt_bytes take_xor (get gs) k n 1 c)
    else None, 
  op valid_key <- fun _ => true
  proof *.
realize dec_enc.
proof.
  move=> k _ gs [n a p]; rewrite /dec /enc /=.
  have htake_xor : forall str, take_xor [] str = [].
  + by move=> ?; rewrite /take_xor take0.
  have : forall j, 0 <= j => forall p c, j = size p =>
    gen_CTR_encrypt_bytes take_xor (get gs) k n c (gen_CTR_encrypt_bytes take_xor (get gs) k n c p) = p;
   2: by move=> /(_ (size p)) -> //;apply size_ge0.
  elim /sintind.
  move=> {p} i hi hrec p c ->>.
  case: (size p = 0).
  + by rewrite size_eq0 => ->>; rewrite !gen_CTR_encrypt_bytes0.
  move=> hs; rewrite (gen_CTR_encrypt_bytes_cons _ _ _ _ _ p) 1:// gen_CTR_encrypt_bytes_cons 1://.
  case: (size p < block_size) => hsz.
  + rewrite drop_oversize 1:/# gen_CTR_encrypt_bytes0 1:// cats0 drop_oversize.
    + by rewrite size_take // Block.bytes_of_blockP /#.
    rewrite gen_CTR_encrypt_bytes0 1:// cats0. 
    rewrite -!take_xor_map2_xor; apply (eq_from_nth Byte.zero).
    + by rewrite !size_map2 Block.bytes_of_blockP /#.
    move=> j; rewrite !size_map2 Block.bytes_of_blockP => hj.
    by rewrite
         !(nth_map2 Byte.zero Byte.zero) ?size_map2
         ?Block.bytes_of_blockP 1,2:/# -Byte.xorK1.
  rewrite drop_size_cat;1: by rewrite size_take 1:// Block.bytes_of_blockP /#.
  rewrite (hrec (size (drop block_size p))) 2://; 1: smt(size_drop gt0_block_size).
  rewrite -{4}(cat_take_drop block_size p); congr.
  rewrite -!take_xor_map2_xor; apply (eq_from_nth Byte.zero).
  + rewrite size_take 1:#smt:(gt0_block_size).
    rewrite size_map2 size_cat size_map2 bytes_of_blockP.
    by rewrite /min; smt(size_ge0).
  move=> j hj.
  have [hj1 hj2] : j < block_size /\ j < size p.
  + move: hj; rewrite size_map2 size_cat size_map2 bytes_of_blockP /min.
    smt(size_ge0).
  rewrite
    (nth_map2 Byte.zero Byte.zero)
    ?(size_cat, size_map2, Block.bytes_of_blockP) 1:#smt:(size_ge0).
  rewrite nth_cat ?(size_cat, size_map2, Block.bytes_of_blockP) /min hsz /= hj1.
  by rewrite
       (nth_map2 Byte.zero Byte.zero)
       ?Block.bytes_of_blockP 1:/# /= -Byte.xorK1 nth_take 1:ge0_block_size.
qed.

module St = {
  proc init () = { 
    FinRO.init();
    return RO.m;
  }
  proc kg = ChaChaPoly.kg
}.

clone Split as Split0 with 
  type from   <- nonce * C.counter,
  type to     <- block,
  type input  <- unit,
  type output <- bool,
  op sampleto <- fun _ => dblock
  proof *.

clone import Split0.SplitDom as SplitD with
  op test = fun p:nonce * C.counter => C.toint p.`2 = 0.

clone import Split0.SplitCodom as SplitC1 with
  type to1 <- poly,
  type to2 <- extra_block,
  op topair = fun (b:block) => 
     let bs = bytes_of_block b in
     (
       TPoly.poly_of_bytesd (take poly_size bs),
       Extra_block.extra_block_of_bytesd (drop poly_size bs)
     ),
  op ofpair = fun (p:poly * extra_block) =>
     Block.block_of_bytesd (bytes_of_poly p.`1 ++ bytes_of_extra_block p.`2),
  op sampleto1 <- fun _ => dpoly,
  op sampleto2 <- fun _ => dextra_block
  proof *.
realize topairK.
proof.
  move=> x; rewrite /topair /ofpair /=.
  rewrite -{3}(Block.bytes_of_blockKd x); congr.
  rewrite TPoly.poly_of_bytesdK. 
  + rewrite size_take 1:ge0_poly_size Block.bytes_of_blockP.
    smt (ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
  rewrite Extra_block.extra_block_of_bytesdK 2:cat_take_drop 2://.
  rewrite size_drop 1:ge0_poly_size Block.bytes_of_blockP.
  smt (ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
qed.

realize sample_spec.
proof.
  have ofpairK : cancel ofpair topair.
  + move=> [x1 x2]; rewrite /topair /ofpair /=.
    rewrite Block.block_of_bytesdK.
    + by rewrite size_cat TPoly.bytes_of_polyP Extra_block.bytes_of_extra_blockP.
    by rewrite
         take_size_cat 1:TPoly.bytes_of_polyP 1:// drop_size_cat
         1:TPoly.bytes_of_polyP 1:// TPoly.bytes_of_polyKd
         Extra_block.bytes_of_extra_blockKd.
  move=> _; rewrite /dblock; apply eq_distr => b.
  rewrite !dmap1E.
  apply (eq_trans _ (mu1 (dpoly `*` dextra_block) ((topair b).`1, (topair b).`2))); last first.
  + congr; apply: fun_ext=> x @/(\o) @/pred1.
    rewrite -{3}topairK; case: (topair b)=> />.
    by move: (can_inj _ _ ofpairK)=> /#.
  rewrite dprod1E (_:block_size = poly_size + extra_block_size) //.
  rewrite dlist_add 1:ge0_poly_size 1:ge0_extra_block_size dmapE.
  rewrite !dmap1E /(\o) -dprodE &(mu_eq_support) => -[l1 l2] /supp_dprod /= [h1 h2].
  have s1 := supp_dlist_size dbyte _ _ ge0_poly_size h1.
  have s2 := supp_dlist_size dbyte _ _ ge0_extra_block_size h2.
  rewrite eq_iff /pred1 /topair //=; split=> />.
  + rewrite block_of_bytesdK 1:size_cat 1:s1 1:s2 //.
    by rewrite take_size_cat // drop_size_cat.
  move=> /(congr1 bytes_of_poly); rewrite poly_of_bytesdK=> // ->.
  move=> /(congr1 bytes_of_extra_block); rewrite extra_block_of_bytesdK=> // ->.
  rewrite extra_block_of_bytesdK.
  + rewrite size_drop 1:ge0_poly_size bytes_of_blockP /block_size /poly_size.
    smt(ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
  rewrite poly_of_bytesdK.
  + rewrite size_take 1:ge0_poly_size bytes_of_blockP /poly_size /block_size.
    smt(ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
  by rewrite cat_take_drop bytes_of_blockKd.
qed.

clone Split as Split1 with 
  type from   <- nonce * C.counter,
  type to     <- poly,
  type input  <- unit,
  type output <- bool,
  op sampleto <- fun _ => dpoly
  proof *.

(* TODO: share more stuff with the previous clone *)
clone import Split1.SplitCodom as SplitC2 with
  type to1 <- poly_in,
  type to2 <- poly_out,
  op topair = fun (b:poly) => 
     let bs = bytes_of_poly b in
     (
       Poly_in.poly_in_of_bytesd (take poly_in_size bs),
       Poly_out.poly_out_of_bytesd (drop poly_in_size bs)
     ),
  op ofpair = fun (p:poly_in * poly_out) =>
     TPoly.poly_of_bytesd (bytes_of_poly_in p.`1 ++ bytes_of_poly_out p.`2),
  op sampleto1 <- fun _ => dpoly_in,
  op sampleto2 <- fun _ => dpoly_out
  proof *.
realize topairK.
proof.
  move=> x; rewrite /topair /ofpair /=.
  rewrite -{3}(TPoly.bytes_of_polyKd x); congr.
  rewrite Poly_in.poly_in_of_bytesdK. 
  + rewrite size_take 1:ge0_poly_in_size TPoly.bytes_of_polyP.
    smt (ge0_poly_in_size ge0_poly_out_size).
  rewrite Poly_out.poly_out_of_bytesdK 2:cat_take_drop 2://.
  rewrite size_drop 1:ge0_poly_in_size TPoly.bytes_of_polyP.
  smt (ge0_poly_in_size ge0_poly_out_size).
qed.

realize sample_spec.
proof.
  have ofpairK : cancel ofpair topair.
  + move=> [x1 x2]; rewrite /topair /ofpair /=.
    rewrite TPoly.poly_of_bytesdK.
    + by rewrite size_cat Poly_in.bytes_of_poly_inP Poly_out.bytes_of_poly_outP.
    by rewrite
         take_size_cat 1:Poly_in.bytes_of_poly_inP 1:// drop_size_cat
         1:Poly_in.bytes_of_poly_inP 1:// Poly_in.bytes_of_poly_inKd
         Poly_out.bytes_of_poly_outKd.
  move=> _; rewrite /dpoly; apply eq_distr => b.
  rewrite !dmap1E.
  apply (eq_trans _ (mu1 (dpoly_in `*` dpoly_out) ((topair b).`1, (topair b).`2))); last first.
  + congr; apply: fun_ext=> x @/(\o) @/pred1.
    rewrite -{3}(topairK b); case: (topair b)=> />.
    by move: (can_inj _ _ ofpairK)=> /#.
  rewrite dprod1E (_:poly_size = poly_in_size + poly_out_size) //.
  rewrite dlist_add 1:ge0_poly_in_size 1:ge0_poly_out_size dmapE.
  rewrite !dmap1E /(\o) -dprodE &(mu_eq_support) => -[l1 l2] /supp_dprod /= [h1 h2].
  have s1 := supp_dlist_size dbyte _ _ ge0_poly_in_size h1.
  have s2 := supp_dlist_size dbyte _ _ ge0_poly_out_size h2.
  rewrite eq_iff /pred1 /topair //=; split=> />.
  + rewrite poly_of_bytesdK 1:size_cat 1:s1 1:s2 //.
    by rewrite take_size_cat // drop_size_cat.
  move=> /(congr1 bytes_of_poly_in); rewrite poly_in_of_bytesdK=> // ->.
  move=> /(congr1 bytes_of_poly_out); rewrite poly_out_of_bytesdK=> // ->.
  rewrite poly_out_of_bytesdK.
  + rewrite size_drop 1:ge0_poly_in_size bytes_of_polyP /poly_size.
    smt(ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
  rewrite poly_in_of_bytesdK.
  + rewrite size_take 1:ge0_poly_in_size bytes_of_polyP /poly_size.
    smt(ge0_poly_in_size ge0_poly_out_size ge0_extra_block_size).
  by rewrite cat_take_drop bytes_of_polyKd.
qed.

module G4 (A:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b;
    Mem.k <@ GenChaChaPoly(CCRO(RO)).kg();
    b <@ CCA_CPA_Adv(A, RealOrcls(GenChaChaPoly(CCRO(RO)))).main();
    return b;
  }
}.

module G5_end(RO:RO) = {
  proc main() = {
    var ns, forged, i, n, bl, r,s ;
    ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
    forged <- false;
    i <- 0;
    while (i < size ns) {
      n  <- List.nth witness ns i;
      bl <@ RO.get(n,C.ofintd 0);
      (r,s) <- mk_rs bl; 
      forged <- forged || test_poly n Mem.lc r s;
      i <- i + 1;
    }
    return forged;
  }
}.

module G5 (A:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b, forged;
    b <@ G4(A, RO).distinguish();
    forged <@ G5_end(RO).main();
    return forged;
  }
}.

module G6 (A:CCA_Adv, ROT:Split0.IdealAll.RO) = {
  proc distinguish () = {
    var b;
    ROF.RO.init();
    b <@ G4(A, RO_DOM(ROT, ROF.RO)).distinguish();
    return b;
  }
}.

module G7 (A:CCA_Adv, ROT:Split0.IdealAll.RO) = {
  proc distinguish () = {
    var b;
    ROF.RO.init();
    b <@ G5(A, RO_DOM(ROT, ROF.RO)).distinguish();
    return b;
  }
}.

module G8 (A:CCA_Adv, RO1:SplitC1.I1.RO) = {
  proc distinguish() = {
    var b;
    SplitC1.I2.RO.init();
    b <@ G6(A, SplitC1.RO_Pair(RO1,SplitC1.I2.RO)).distinguish();
    return b;
  }
}.

module G9 (A:CCA_Adv, RO1:SplitC1.I1.RO) = {
  proc distinguish() = {
    var b;
    SplitC1.I2.RO.init();
    b <@ G7(A, SplitC1.RO_Pair(RO1,SplitC1.I2.RO)).distinguish();
    return b;
  }
}.

section PROOFS.

  declare module A <: CCA_Adv { -RO, -FRO, -OpCCinit.OCC, -OpCCRO.OCC, -IndBlock, -Mem, -StLSke,
                               -Split0.IdealAll.RO, -ROT.RO, -ROF.RO, -SplitC1.I1.RO, -SplitC1.I2.RO,
                               -Split1.IdealAll.RO, -SplitC2.I1.RO, -SplitC2.I2.RO }.

  declare axiom A_ll : forall (O <: CCA_Oracles{-A}), islossless O.enc => islossless O.dec => islossless A(O).main.

  local module G1 (S:SKE) = CCA_game(A, RealOrcls(S)).

  local equiv poly_mac1 : 
    Poly(OpCCinit.OCC(I_stateless)).mac ~ D(A, IndBlock).O.Poly.mac : k{1} = IndBlock.k{2} /\ ={n,a,c} ==> ={res}.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local equiv chacha_enc1: 
    ChaCha(OpCCinit.OCC(I_stateless)).enc ~ D(A, IndBlock).O.ChaCha.enc : 
      k{1} = IndBlock.k{2} /\ ={n,p} ==> ={res}.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local module G2(RO:RO) = {
    module CCRO = {
      proc f = RO.get
    }
    proc distinguish = D(A,CCRO).guess
  }.

  local equiv poly_mac2 : 
    Poly(OCC(IFinRO)).mac ~ D(A, G2(FinRO).CCRO).O.Poly.mac : OCC.gs{1} = RO.m{2} /\ ={n,a,c} ==> ={res}.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local equiv chacha_enc2: 
    ChaCha(OCC(IFinRO)).enc ~ D(A, G2(FinRO).CCRO).O.ChaCha.enc : OCC.gs{1} = RO.m{2} /\ ={n,p} ==> ={res}.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local lemma step1 &m: 
     Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] -
      Pr[CCA_game(A,RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] =
     Pr[Indist.Distinguish(D(A), IndBlock).game() @ &m : res] -
       Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res].
proof.
(* COMPLETE THIS *)
  congr.
  have -> : Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] = Pr[CCA_game(A, RealOrcls(OpCCinit.OChaChaPoly(I_stateless))).main() @ &m : res] by byequiv=>//; proc; inline *; wp; call (_: ={Mem.k}); sim />.
  rewrite -(OpCCinit.pr_CCP_OCCP I_stateless G1 &m).
  byequiv=> //; proc.
  inline{2} D(A, IndBlock).guess.
  inline{2} D(A, IndBlock).O.init.
  wp.
  call (_: Mem.k{1} = IndBlock.k{2}).
  proc. inline{1} 1.
  wp. call poly_mac1. call chacha_enc1. auto => />.
  proc. inline{1} 1.
  sp. wp. seq 1 1 : (Mem.k{1} = IndBlock.k{2} /\ k{1} = IndBlock.k{2} /\ ={n, a, t, result} /\ c0{1} = c{2} /\ t'{1} = t'{2}). call poly_mac1. skip => />. if. smt(). wp. call chacha_enc1. skip => />. skip => />.
  inline *. auto.
  congr.
  rewrite -(OpCCRO.pr_CCP_OCCP IFinRO G1 &m).
  have h_dout : forall (_ : nonce * C.counter), is_lossless dblock by move=> _; apply dblock_ll.
  have h1 : Pr[G1(GenChaChaPoly(OCC(IFinRO))).main() @ &m : res] = Pr[MainD(G2, FinRO).distinguish() @ &m : res].
  byequiv=> //; proc.
  inline{1} 1. inline{2} 2.
  inline{1} 1. inline{1} 1. inline{1} 1. inline{2} 3.
  inline{2} 1. seq 3 3 : (={RO.m, glob A}). sim. wp.
  seq 2 1 : (OCC.gs{1} = RO.m{2} /\ ={RO.m, glob A}).
  inline{1} 2.
  wp.
  rnd{1}.
  auto => />.
  call (_: OCC.gs{1} = RO.m{2}).
  proc.
  inline{1} 1.
  wp.
  call poly_mac2.
  call chacha_enc2.
  auto => />.
  proc.
  inline{1} 1.
  sp.
  wp.
  seq 1 1 : (OCC.gs{1} = RO.m{2} /\ k{1} = Mem.k{1} /\ ={n, a, t, result} /\ c0{1} = c{2} /\ t'{1} = t'{2}).
  call poly_mac2.
  skip => />.
  if.
  smt().
  wp.
  call chacha_enc2.
  skip => />.
  skip => />.
  auto.
  rewrite h1.
  have h2 := pr_RO_FinRO_D h_dout G2 &m () (fun (r:bool) => r).
  rewrite /= in h2.
  rewrite -h2.
  byequiv=> //; proc; inline *; sim.
qed.

  local lemma step2_1 &m :
    Pr[CCA_game(A,RealOrcls(OChaChaPoly(IFinRO))).main() @ &m : res] <=
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] + 
     Pr[UFCMA(A, St).main() @ &m : (exists c, c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None)].
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local module G3 (S:SKE) = CPA_game(CCA_CPA_Adv(A), RealOrcls(S)).

  local equiv UFCMA_genCC :
    UFCMA(A, St).main ~ CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main :
    ={glob A} ==> ={res, Mem.lc} /\ StLSke.gs{1} = RO.m{2}.
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local lemma step2_2 &m : 
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(StLSke(St))).main() @ &m : res] + 
    Pr[UFCMA(A, St).main() @ &m : (exists c, c \in Mem.lc /\ dec StLSke.gs Mem.k c <> None)] <=
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] +
    Pr[UFCMA_poly(A, FinRO).main() @ &m : res].
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local lemma step2_3 &m : 
    Pr[CPA_game(CCA_CPA_Adv(A), RealOrcls(GenChaChaPoly(CCRO(FinRO)))).main() @ &m : res] +
    Pr[UFCMA_poly(A, FinRO).main() @ &m : res] = 
    Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] + 
    Pr[Split1.IdealAll.MainD(G9(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res]. 
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  lemma step2 &m : 
    Pr[CCA_game(A, RealOrcls(ChaChaPoly)).main() @ &m : res] <=
     Pr[Split1.IdealAll.MainD(G8(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] + 
     Pr[Split1.IdealAll.MainD(G9(A), SplitC2.RO_Pair(SplitC2.I1.RO, SplitC2.I2.RO)).distinguish() @ &m : res] + 
     (Pr[Indist.Distinguish(D(A), IndBlock).game() @ &m : res] - Pr[Indist.Distinguish(D(A), IndRO).game() @ &m : res]).
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

end section PROOFS.

end Step1_2.

(* -------------------------------------------------------------------------- *)
(* We now restrict the adversary to be :                                      *)
(* - nonce respective                                                         *)
(* - for encryption end decryption :                                          *)
(*   * the size of additionnal is bounded by [max_ad_size]                    *)
(*   * the size of message is bounded by max_cipher_size                      *)
(* - number of call to                                                        *)
(*   * enc is bounded by qenc                                                 *)
(*   * dec is bounded by qdec                                                 *)

op qenc : int.
 axiom ge0_qenc : 0 <= qenc.

op qdec : int.
axiom ge0_qdec : 0 <= qdec.

op dec_bytes : int.
axiom ge0_dec_bytes : 0 <= dec_bytes. 

op pr1_poly_out = mu1 dpoly_out witness.

op pr_zeropol : real.
axiom ge0_pr_zeropol : 0%r <= pr_zeropol.

axiom pr_zeropol_spec ad1 ad2 m1 m2 t1 t2 : 
   valid_topol ad1 m1 =>
   valid_topol ad2 m2 =>
   let p1 = topol ad1 m1 in
   let p2 = topol ad2 m2 in
   p2 <> p1 => 
   mu dpoly_in (fun r => t2 = t1 + (poly1305_eval r p2 - poly1305_eval r p1)) <= pr_zeropol.
  
op test_poly_in (n : nonce) (lc : ciphertext list) (r : poly_in)
       (amt: associated_data * message * tag) = 
    let (a,m,t) = amt in
    let p = topol a m in
    let pts = 
       map (fun (c : ciphertext) => (topol c.`2 c.`3, c.`4))
           (filter (fun (c : ciphertext) => c.`1 = n /\ valid_topol c.`2 c.`3) lc) in
     valid_topol a m /\
     has (fun (pt : polynomial * tag) => 
            pt.`1 <> p /\ pt.`2 = t + (poly1305_eval r pt.`1 - poly1305_eval r p)) pts.

lemma pr_TPI_ok n (lc:ciphertext list) (amt : associated_data * message * tag) (k : int) : 
  size lc <= k => 
  mu dpoly_in (fun r => test_poly_in n lc r amt) <= k%r * pr_zeropol.
proof.
(* COMPLETE THIS *)
  admit.
qed.

lemma filter_test_poly_in n lc r amt : 
  test_poly_in n lc r amt = test_poly_in n (filter (fun c:ciphertext => c.`1 = n) lc) r amt.
proof.
(* COMPLETE THIS *)
  admit.
qed.


lemma pr_TPI_ok_filter n (lc:ciphertext list) (amt : associated_data * message * tag) (k : int) : 
  size (filter (fun (c:ciphertext) => c.`1 = n) lc) <= k => 
  mu dpoly_in (fun r => test_poly_in n lc r amt) <= k%r * pr_zeropol.
proof.
(* COMPLETE THIS *)
  admit.
qed.

op check_plaintext (lenc:nonce list) (p:plaintext) = 
  let (n, a, m) = p in
  ! n \in lenc /\ 
  valid_topol a m /\
  size lenc < qenc.

op check_cipher (ndec:int) (c:ciphertext) =
  (let (n, a, m, t) = c in
  valid_topol a m) /\
  ndec < qdec.

(* Bounded and Nonce Respecting *)
module BNR (O:CCA_Oracles) = {
  var lenc : nonce list
  var ndec : int 

  proc init () = { lenc <- []; ndec <- 0; }

  proc enc (p:plaintext) = {
    var c;
    c <- witness;
    if (check_plaintext lenc p) {
      c <@ O.enc(p);
      lenc <- p.`1 :: lenc;
    }
    return c;
  }

  proc dec (c:ciphertext) = {
    var p;
    p <- None;
    if (check_cipher ndec c) {
      p <@ O.dec(c);
      ndec <- ndec + 1;
    }
    return p;
  }
}.

module BNR_Adv(A:CCA_Adv, O:CCA_Oracles) = {
  proc main() = {
    var b;
    BNR(O).init();
    b <@ A(BNR(O)).main();
    return b;
  }
}.

module EncRnd = {

  proc init () = {}

  proc cc(n:nonce, p:message) : bytes = {
    var i, z, c;
    p     <- List.map (fun _ => witness<:byte>) p; 
    c     <- [];
    i     <- 1;
    while (p <> []) {
      z <$ dblock; 
      c <- c ++ take (size p) (bytes_of_block  z);
      p <- drop block_size p;
      i <- i + 1;
    }
    return c;
  }

  proc enc (nap : nonce * associated_data * message) : 
       nonce * associated_data * message * tag = {
    var n, a, p, c, t;
    (n,a,p) <- nap;
    c <@ cc(n,p);
    t <$ dpoly_out; 
    return (n,a,c,t);
  }
  
  proc dec (nact: nonce * associated_data * message * tag) : 
    (nonce * associated_data * message) option = {
    return None;
  }
   
}.

section PROOFS.
  declare module A <: CCA_Adv { -BNR, -Mem, -IndBlock, -RO, -FRO}.

  declare axiom A_ll : forall (O <: CCA_Oracles{-A}), islossless O.enc => islossless O.dec => islossless A(O).main.

  local clone import Step1_2 as Step1_2'.

  local module ROin  = SplitC2.I1.RO.
  local module ROout = SplitC2.I2.RO.
  local module ROF   = SplitD.ROF.RO.

  local lemma mk_rs_ofpair r s e : 
    mk_rs (SplitC1.ofpair (SplitC2.ofpair (r, s), e)) = (r, s).
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  op inv_cpa (mr1 : (nonce*C.counter, poly_in) fmap) 
         (ms1 : (nonce*C.counter, poly_out) fmap)
         (log1 log2: (ciphertext, plaintext) fmap)
         (lc1 lc2 : ciphertext list) 
         (lenc1 lenc2: nonce list)
         (ndec1 ndec2 :int) =
     log1 = log2 /\ lenc1 = lenc2 /\ lc1 = lc2 /\ ndec1 = ndec2 /\
     (forall n c, (n,c) \in mr1 => n \in lenc1) /\
     (forall n c, (n,c) \in ms1 => n \in lenc1).

  local equiv equ_cc n0 mr0 ms0:
     ChaCha(CCRO(SplitD.RO_DOM(SplitC1.RO_Pair(SplitC2.RO_Pair(ROin, ROout), SplitC1.I2.RO), ROF))).enc
     ~
     EncRnd.cc : 
       arg{2} = (arg.`2, arg.`3){1} /\ arg{2}.`1 = n0 /\
       size arg{1}.`3 <= max_cipher_size /\
       !n0 \in BNR.lenc{1} /\
       (forall n c, (n,c) \in ROF.m => n \in BNR.lenc){1} /\
       mr0 = ROin.m{1} /\ ms0 = ROout.m{1} 
       ==>
       ={res} /\ size res{1} <= max_cipher_size /\ mr0 = ROin.m{1} /\ ms0 = ROout.m{1} /\ 
       (forall n c, (n,c) \in ROF.m => n \in n0 :: BNR.lenc){1}.
  proof.
    (* COMPLETE THIS *) 
    admit.
  qed.

  local lemma step3 &m:  
    Pr[Split1.IdealAll.MainD(G8(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish() @ &m : res] =
    Pr[CPA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res].
proof.
(* COMPLETE THIS *)
  byequiv (_ : ={glob A} ==> ={res}) => //.
  proc.
  inline *.
  wp.
  call (_: inv_cpa ROin.m{1} ROout.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n c, (n,c) \in ROF.m{1} => n \in BNR.lenc{1})).
  proc.
  sp; if.
  by move => &1 &2; rewrite /inv_cpa => />.
  inline{1} 1; inline{2} 1.
  inline{1} 2; inline{2} 2.
  inline{1} 3.
  seq 6 4 : (={n, a, p, p0} /\ c2{1} = c1{2} /\ n{1} = p{1}.`1 /\ inv_cpa ROin.m{1} ROout.m{1} Mem.log{1} Mem.log{2} Mem.lc{1} Mem.lc{2} BNR.lenc{1} BNR.lenc{2} BNR.ndec{1} BNR.ndec{2} /\ (forall n0 c3, (n0, c3) \in ROF.m{1} => n0 \in n{1} :: BNR.lenc{1}) /\ ! n{1} \in BNR.lenc{1}).
  exists* p{2}, ROin.m{1}, ROout.m{1}; elim* => pp mr0 ms0; call (equ_cc pp.`1 mr0 ms0); auto.
  by smt().
  inline *.
  rcondt{1} 9.
  by auto => />; rewrite /SplitD.test /=; smt(C.ofintdK C.gt0_max_counter).
  wp; rnd{1}; wp; rnd (fun (s0 : poly_out) => s0 + poly1305_eval r5{1} (topol a0{1} c3{1})) (fun (t0 : poly_out) => t0 - poly1305_eval r5{1} (topol a0{1} c3{1})); wp; rnd{1}; auto.
  move => &1 &2 />.
  smt(poly_out_sub_add poly_out_add_sub mk_rs_ofpair get_set_sameE mem_set).
  auto.
  proc; inline *; auto => />; smt().
  wp; rnd{1}; auto => />; smt(dkey_ll mem_empty emptyE).
qed.
          
  local module UFCMA (ROin:SplitC2.I1.RO) = {
  
    var log : (nonce, associated_data * message * tag)fmap
    var bad1 : bool
    var cbad1 : int   
    var bad2 : bool
    var cbad2 : int   
 
    proc set_bad1 (lt:tag list) : poly_out = {
      var t;
      t <$ dpoly_out;
      if (cbad1 < qenc /\ size lt <= qdec) { 
         bad1 <- bad1 || t \in lt;
         cbad1 <- cbad1 + 1;
      }
      return t;
    } 

    proc set_bad2 (lt:tag list) : poly_out = {
      var t;
      t <$ dpoly_out;
      (* if (cbad2 < qdec /\ size lt <= qdec) {  *)
         bad2 <- bad2 || t \in lt;
         cbad2 <- cbad2 + 1;
      (* } *)
      return t;
    } 

    module O = {
      proc init () = {
        log <- empty;
        ROin.init(); ROout.init(); ROF.init();
      }
    
      proc enc (nap : nonce * associated_data * message) : 
          nonce * associated_data * message * tag = {
        var n, a, p, c, t;
        (n,a,p) <- nap;
        c <@ EncRnd.cc(n,p);   
        (* t <$ dp *)
        t <@ set_bad1(map (fun c:ciphertext => c.`4) (filter (fun (c:ciphertext) => c.`1 = n) Mem.lc));
        ROin.sample(n,C.ofintd 0);
        ROout.set((n,C.ofintd 0), witness); 
        log.[n] <- (a,c,t);
        return (n,a,c,t);
      }
  
      proc dec (nact: nonce * associated_data * message * tag) : 
        (nonce * associated_data * message) option = {
        return None;
      }
   
    }
    
    proc distinguish () = {
      var b, ns, forged, i, n, r, t;

      bad1 <- false; cbad1 <- 0;
      bad2 <- false; cbad2 <- 0;

      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 

      forged <- false;
      if (size Mem.lc <= qdec) {
        ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
        i <- 0;
        while (i < size ns) {
          n  <- List.nth witness ns i;
          if ((n,C.ofintd 0) \in ROout.m) {
            r <@ ROin.get(n,C.ofintd 0);
            forged <- forged || test_poly_in n Mem.lc r (oget log.[n]);
          } else { 
            r <@ ROin.get(n,C.ofintd 0);
            t <@ set_bad2((map 
                (fun c:ciphertext => c.`4 - poly1305_eval r (topol c.`2 c.`3)) 
                (filter (fun c:ciphertext => c.`1 = n) Mem.lc)));
            ROout.set((n,C.ofintd 0), witness); 
          }
          i <- i + 1;
        }
      }
      return forged;
    }

  }.

  local clone import PROM.FullRO as ROIN with
    type in_t    <- (nonce*C.counter),
    type out_t   <- poly_in, 
    type d_in_t  <- unit,
    type d_out_t <- bool,
    op   dout    <- fun _ => dpoly_in
  proof *.

  op inv (mr1 mr2 : (nonce*C.counter, poly_in) fmap) 
         (ms1 ms2 : (nonce*C.counter, poly_out) fmap)
         (log1 log2: (ciphertext, plaintext) fmap)
         (lc1 lc2 : ciphertext list) 
         (lenc1 lenc2: nonce list)
         (ndec1 ndec2 :int)
         (nlog : (nonce, associated_data * message * tag) fmap) = 
     inv_cpa mr1 ms1 log1 log2 lc1 lc2 lenc1 lenc2 ndec1 ndec2 /\
     mr1 = mr2 /\ 
     (forall s, s \in ms1 = s \in ms2) /\
     (forall s, s \in ms1 = s \in mr1) /\
     size lenc1 <= qenc /\ ndec1 <= qdec /\
     (forall n, n \in nlog = n \in lenc1) /\ size lc1 <= ndec1 /\
     (forall n, n \in lenc1 => let (a,c,t) = oget nlog.[n] in (n,a,c,t) \in log1) /\
     (forall n a c t, (n,a,c,t) \in lc1 => valid_topol a c) /\
     (forall n, n \in nlog => let (a,c,t) = oget nlog.[n] in valid_topol a c) /\
     (forall n a c t, (n,a,c,t) \in lc1 => n \in nlog => nlog.[n] <> Some (a, c, t)) /\
     (forall n, n \in lenc1 => 
        let (a,c,t) = oget nlog.[n] in
        let r = oget mr1.[(n,C.ofintd 0)] in
        let s = oget ms1.[(n,C.ofintd 0)] in
        s = t - poly1305_eval r (topol a c)).

  local lemma step4_1 &m:
    Pr[Split1.IdealAll.MainD(G9(BNR_Adv(A)), SplitC2.RO_Pair(ROin, ROout)).distinguish() @ &m : res] <=
     Pr[UFCMA(ROIN.RO).distinguish() @ &m : res \/ UFCMA.bad2] + Pr[UFCMA(ROIN.RO).distinguish() @ &m : UFCMA.bad1].
  proof. 
    (* COMPLETE THIS *) 
  admit.
  qed.

  require IterProc.

  clone import IterProc as IPNonce with
    type t <- nonce
    proof *.

  op sub_map (m1 : (nonce * C.counter, 'a) fmap) (m2 : (nonce * C.counter, 'a) fmap) i l =
    (forall n, (n, C.ofintd 0) \in m2 => (n,C.ofintd 0) \in m1) /\
    (forall n, (n, C.ofintd 0) \in m2 => m1.[(n,C.ofintd 0)] = m2.[(n,C.ofintd 0)]) /\
    (forall j, 0 <= j < i => (nth witness l j, C.ofintd 0) \in m1) /\
    (forall n, (n, C.ofintd 0) \in m1 => (n, C.ofintd 0) \in m2 \/ exists j, 0 <= j < i /\ n = nth witness l j).


  local module UF = {
    var forged : bool
  }.

  local module Orcl : Orcl = {
    proc f (n : nonce) : unit = {
      var r, t;
      if ((n,C.ofintd 0) \in ROout.m) {
        r <@ ROIN.RO.get(n,C.ofintd 0);
        UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n]);
      } else { 
        r <@ ROIN.RO.get(n,C.ofintd 0);
        t <@ UFCMA(ROIN.RO).set_bad2((map 
                (fun c:ciphertext => c.`4 - poly1305_eval r (topol c.`2 c.`3)) 
                (filter (fun c:ciphertext => c.`1 = n) Mem.lc)));
        ROout.set((n,C.ofintd 0), witness); 
      }
    }
  }.

  local module UFCMA2 (ROin:SplitC2.I1.RO) = {

    proc set_bad1 = UFCMA(ROin).set_bad1

    proc set_bad2  = UFCMA(ROin).set_bad2

    module O = UFCMA(ROin).O

    proc distinguish () = {
      var b, ns, ns1, ns2;

      UFCMA.bad1 <- false; UFCMA.cbad1 <- 0;
      UFCMA.bad2 <- false; UFCMA.cbad2 <- 0;

      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 

      UF.forged <- false;
      if (size Mem.lc <= qdec) {
        ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
        ns1 <- filter (fun n => (n,C.ofintd 0) \in ROout.m) ns;
        ns2 <- filter (fun n => (n,C.ofintd 0) \notin ROout.m) ns;
        Iter(Orcl).iter(ns1++ns2);
      }
      return UF.forged;
    }

  }.

  local module UFCMA3 (ROin:SplitC2.I1.RO) = {

    proc set_bad1 = UFCMA(ROin).set_bad1

    proc set_bad2  = UFCMA(ROin).set_bad2

    module O = UFCMA(ROin).O

    proc distinguish () = {
      var b, ns, ns1, ns2, i, n, r, t;

      UFCMA.bad1 <- false; UFCMA.cbad1 <- 0;
      UFCMA.bad2 <- false; UFCMA.cbad2 <- 0;

      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 

      UF.forged <- false;
      if (size Mem.lc <= qdec) {
        ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
        ns1 <- filter (fun n => (n,C.ofintd 0) \in ROout.m) ns;
        ns2 <- filter (fun n => (n,C.ofintd 0) \notin ROout.m) ns;
        i <- 0;
        while (i < size ns1) {
          n <- nth witness ns1 i;
          r <@ ROin.get(n,C.ofintd 0);
          UF.forged <- UF.forged || test_poly_in n Mem.lc r (oget UFCMA.log.[n]);
          i <- i + 1;
        }
        i <- 0;
        while (i < size ns2) {
          n <- nth witness ns2 i;
          r <@ ROin.get(n,C.ofintd 0);
          t <@ UFCMA(ROin).set_bad2((map 
                (fun c:ciphertext => c.`4 - poly1305_eval r (topol c.`2 c.`3)) 
                (filter (fun c:ciphertext => c.`1 = n) Mem.lc)));
          i <- i + 1;
        }
      }
      return UF.forged \/ UFCMA.bad2;
    }

  }.


  local equiv equiv_step4 :
    UFCMA(ROIN.RO).distinguish ~ UFCMA3(ROIN.RO).distinguish :
    ={glob A} ==> ={UFCMA.bad2} /\ res{1} = UF.forged{2} /\ res{2} = (UF.forged{2} \/ UFCMA.bad2{2}).
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local module UFCMA4 (ROin:SplitC2.I1.RO) = {

    var cforged : int

    proc set_bad1 = UFCMA(ROin).set_bad1

    module O = UFCMA(ROin).O

    proc set_forged () = {
      var n, r, ns, ns1;

      ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
      ns1 <- filter (fun n => (n,C.ofintd 0) \in ROout.m) ns;
      if (cforged < size ns1) {
        n <- nth witness ns1 cforged;
        r <$ dpoly_in;
        ROin.set((n,C.ofintd 0), r);
        UF.forged <- UF.forged ||
            test_poly_in n Mem.lc r (oget UFCMA.log.[n]);
        cforged <- cforged + 1;
      }
    }

    proc set_bad2 () = {
      var n, r, ns, ns2, t;

      ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
      ns2 <- filter (fun n => (n,C.ofintd 0) \notin ROout.m) ns;
      if (UFCMA.cbad2 < size ns2) {
        n <- nth witness ns2 UFCMA.cbad2;
        r <@ ROin.get(n,C.ofintd 0);
        t <$ dpoly_out;
        UFCMA.bad2 <- UFCMA.bad2 || 
              t \in (map (fun c:ciphertext => c.`4 - poly1305_eval r (topol c.`2 c.`3)) 
                (filter (fun c:ciphertext => c.`1 = n) Mem.lc));
        UFCMA.cbad2 <- UFCMA.cbad2 + 1;
      }
    }

    proc test_forged () : unit = {
      var ns, ns1;

      UF.forged <- false;
      cforged <- 0;
      ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
      ns1 <- filter (fun n => (n,C.ofintd 0) \in ROout.m) ns;

      while (cforged < size ns1) {
        set_forged();
      }
    }

    proc test_bad2 () : unit = {
      var ns, ns2;

      UFCMA.bad2 <- false;
      UFCMA.cbad2 <- 0;
      ns <- undup (List.map (fun (p:ciphertext) => p.`1) Mem.lc);
      ns2 <- filter (fun n => (n,C.ofintd 0) \notin ROout.m) ns;

      while (UFCMA.cbad2 < size ns2) {
        set_bad2();
      }
    }


    proc distinguish () = {
      var b;

      UFCMA.bad1 <- false; UFCMA.cbad1 <- 0;
      UFCMA.bad2 <- false; UFCMA.cbad2 <- 0;

      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 

      UF.forged <- false;
      if (size Mem.lc <= qdec) {
        test_forged();
        test_bad2();
      }
      return UF.forged \/ UFCMA.bad2;
    }

  }.

  import StdBigop.Bigreal.
  import StdBigop.Bigint.

  local lemma step4_bad2 &m :
    Pr[UFCMA(ROIN.RO).distinguish() @ &m : res \/ UFCMA.bad2] <= qdec%r * (maxr pr_zeropol pr1_poly_out).
  proof.
  (* COMPLETE THIS *)
    admit.
  qed.

  local module UFCMA_l = {
  
    var lbad1 : (tag * tag) list
 
    proc set_bad1 (lt:tag list) : poly_out = {
      var t;
      t <$ dpoly_out;
      if (UFCMA.cbad1 < qenc /\ size lt <= qdec) { 
         lbad1 <- lbad1 ++ (List.map (fun t' => (t,t')) lt);
         UFCMA.cbad1 <- UFCMA.cbad1 + 1;
      }
      return t;
    } 

    module O = {
      proc init () = {
        UFCMA.log <- empty;
        ROIN.RO.init(); ROout.init(); ROF.init();
      }
    
      proc enc (nap : nonce * associated_data * message) : 
          nonce * associated_data * message * tag = {
        var n, a, p, c, t;
        (n,a,p) <- nap;
        c <@ EncRnd.cc(n,p);   
        (* t <$ dp *)
        t <@ set_bad1(map (fun c:ciphertext => c.`4) (filter (fun (c:ciphertext) => c.`1 = n) Mem.lc));
        ROIN.RO.sample(n,C.ofintd 0);
        ROout.set((n,C.ofintd 0), witness); 
        UFCMA.log.[n] <- (a,c,t);
        return (n,a,c,t);
      }
  
      proc dec (nact: nonce * associated_data * message * tag) : 
        (nonce * associated_data * message) option = {
        return None;
      }
   
    }
    
    proc f () = {
      var b;

      lbad1 <- []; UFCMA.cbad1 <- 0;
      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 
    }
  }.


  op make_lbad1 
    (log : (nonce, associated_data * message * tag) fmap) 
    (lc : ciphertext list) 
    (lenc : nonce list) =
    flatten
    (map (fun n:nonce => 
            map (fun c:ciphertext => ((oget log.[n]).`3, c.`4))
                (filter (fun c:ciphertext => c.`1 = n) lc))
         lenc).

  

  lemma make_lbad1_size_cons2 log lc lenc c :
      uniq lenc =>
      size (make_lbad1 log (c::lc) lenc) = 
      if c.`1 \in lenc
      then size (make_lbad1 log lc lenc) + 1
      else size (make_lbad1 log lc lenc).
  proof.
  (* COMPLETE THIS *)
  admit.
  qed.    


  lemma leq_make_lbad1 log lc lenc :
      uniq lenc =>
      size (make_lbad1 log lc lenc) <= size lc.
  proof.
  (* COMPLETE THIS *)
  move=> huniq.
  elim: lc => [|c lc ih].
  rewrite /make_lbad1 size_flatten /=.
  elim: lenc huniq => //=.
  smt().
  rewrite make_lbad1_size_cons2 //.
  smt().
  qed.

  lemma make_lbad1_size_cons3 (log : (_, _) fmap) lc lenc n a c t:
      uniq lenc =>
      ! n \in lenc =>
      size (make_lbad1 log.[n <- (a,c,t)] lc (n::lenc)) =
      size (filter (fun (c0 : ciphertext) => c0.`1 = n) lc) +
      size (make_lbad1 log lc lenc).
  proof.
  (* COMPLETE THIS *)
  move=> huniq hnin.
  rewrite /make_lbad1 /=.
  rewrite flatten_cons size_cat size_map.
  congr.
  congr.
  congr.
  rewrite -eq_in_map => n0 hn0 /=.
  have hneq: n0 <> n by smt().
  rewrite get_set_neqE 1:hneq.
  done.
  done.
  qed.

  op inv_lbad1
    (lbad1 : (tag * tag) list) 
    (lenc : nonce list)
    (ufcmalog : (nonce, associated_data * message * tag) fmap) 
    (log : (ciphertext, plaintext) fmap)
    (lc : ciphertext list) 
    (cbad1 : int)
    (ndec : int) =
    uniq lenc /\
    cbad1 <= qenc /\
    size lenc <= qenc /\
    size lbad1 <= size (make_lbad1 ufcmalog lc lenc) <= qdec /\
    size lc <= ndec <= qdec /\
    uniq lenc /\
    (forall n, n \in lenc => let (a,c,t) = oget ufcmalog.[n] in (n,a,c,t) \in log) /\
    (forall n, n \in lenc = n \in ufcmalog) /\
    (* (forall n a c t, (n,a,c,t) \in lc1 => n \in nlog => nlog.[n] <> Some (a, c, t)) /\ *)
    (forall t t', (t,t') \in lbad1 => 
      (exists n, n \in lenc /\
        (oget ufcmalog.[n]).`3 = t /\
        exists a c, (n, a, c, t') \in lc)).


  local lemma step4_bad1_lbad1 &m: 
    Pr[UFCMA(ROIN.RO).distinguish() @ &m : UFCMA.bad1] <=
    Pr[UFCMA_l.f() @ &m : size UFCMA_l.lbad1 <= qdec /\ exists tt, tt \in UFCMA_l.lbad1 /\ tt.`1 = tt.`2].
  proof.
  (* COMPLETE THIS *)
  admit.
  qed.

  local clone EventPartitioning as EP with 
    type input <- unit,
    type output <- unit.

  local clone EP.ListPartitioning as LP with
    type partition <- int.

  op w1 : poly_out.
  op w2 : poly_out.

  declare axiom neq_w1_w2 : w1 <> w2.

  local lemma step4_lbad1_sum &m :
    Pr[UFCMA_l.f() @ &m : size UFCMA_l.lbad1 <= qdec /\ exists tt, tt \in UFCMA_l.lbad1 /\ tt.`1 = tt.`2] <=
     BRA.big predT (fun (i : int) => Pr[UFCMA_l.f() @ &m : let tt = nth (w1,w2) UFCMA_l.lbad1 i in tt.`1 = tt.`2])
       (iota_ 0 qdec).
  proof.
    (* COMPLETE THIS *) 
  admit.
  qed.

  local module UFCMA_li = {

    var i : int
    var badi : bool
    var cbadi : int

    proc set_bad1i (ti:tag) = {
      var t;
      t <$ dpoly_out;
      if (cbadi < 1) {
          badi <- badi || t = ti;
          cbadi <- cbadi + 1;
      }
      return t;
    }
        
    proc set_bad1 (lt:tag list) : poly_out = {
      var t;
      t <$ dpoly_out;
      if (UFCMA.cbad1 < qenc /\ size lt <= qdec) { 
        if (size UFCMA_l.lbad1 <= i < size UFCMA_l.lbad1 + size lt) {
          t <@ set_bad1i (nth witness lt (i - size UFCMA_l.lbad1));
        }
        UFCMA_l.lbad1 <- UFCMA_l.lbad1 ++ (List.map (fun t' => (t,t')) lt);
        UFCMA.cbad1 <- UFCMA.cbad1 + 1;
      }
      return t;
    } 

    module O = {
      proc init () = {
        UFCMA.log <- empty;
        ROIN.RO.init(); ROout.init(); ROF.init();
      }
    
      proc enc (nap : nonce * associated_data * message) : 
          nonce * associated_data * message * tag = {
        var n, a, p, c, t;
        (n,a,p) <- nap;
        c <@ EncRnd.cc(n,p);   
        (* t <$ dp *)
        t <@ set_bad1(map (fun c:ciphertext => c.`4) (filter (fun (c:ciphertext) => c.`1 = n) Mem.lc));
        ROIN.RO.sample(n,C.ofintd 0);
        ROout.set((n,C.ofintd 0), witness); 
        UFCMA.log.[n] <- (a,c,t);
        return (n,a,c,t);
      }
  
      proc dec (nact: nonce * associated_data * message * tag) : 
        (nonce * associated_data * message) option = {
        return None;
      }
   
    }
    
    proc f (i0:int) = {
      var b;

      cbadi <- 0; badi <- false; i <- i0;

      UFCMA_l.lbad1 <- []; UFCMA.cbad1 <- 0;
      b <@ CPA_game(CCA_CPA_Adv(BNR_Adv(A)), O).main(); 
    }
  }.

  op inv_lbad1_i
    (lbad1 : (tag * tag) list) 
    (lenc : nonce list)
    (ufcmalog : (nonce, associated_data * message * tag) fmap) 
    (log : (ciphertext, plaintext) fmap)
    (lc : ciphertext list) 
    (cbad1 : int)
    (ndec : int) =
    uniq lenc /\
    cbad1 <= qenc /\
    size lenc <= qenc /\
    size lbad1 <= size (make_lbad1 ufcmalog lc lenc) <= qdec /\
    size lc <= ndec <= qdec /\
    uniq lenc.


  local lemma step4_badi &m nth0 :
    0 <= nth0 < qdec => 
    Pr[UFCMA_l.f() @ &m : let tt = nth (w1,w2) UFCMA_l.lbad1 nth0 in tt.`1 = tt.`2] <=
    Pr[UFCMA_li.f(nth0) @ &m : UFCMA_li.badi].
  proof.
  (* COMPLETE THIS *) 
  admit.
  qed.

  local lemma pr_step4_badi &m nth0 :
    0 <= nth0 < qdec => 
    Pr[UFCMA_li.f(nth0) @ &m : UFCMA_li.badi] <= pr1_poly_out.
  proof.
  (* COMPLETE THIS *) 
  admit.
  qed.


  local lemma step4_bad1 &m :
    Pr[UFCMA(ROIN.RO).distinguish() @ &m : UFCMA.bad1] <= qdec%r * pr1_poly_out.
  proof.
  (* COMPLETE THIS *) 
  admit.
  qed.

  lemma conclusion &m : 
    Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
      Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
      (Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] -
       Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res]) + 
       qdec%r * (maxr pr_zeropol pr1_poly_out) +
       qdec%r * pr1_poly_out.
   proof. 
     (* COMPLETE THIS *) 
    admit.
   qed.

end section PROOFS.