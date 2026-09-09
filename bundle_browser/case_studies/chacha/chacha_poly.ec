require import AllCore List Int IntDiv Real FMap Distr DBool DList DProd FSet PROM SplitRO FelTactic.

require import FinType.

require   Subtype Ske RndProd Indistinguishability Monoid EventPartitioning.

import StdOrder IntOrder RealOrder.

op map2 ['a, 'b, 'c] (f:'a -> 'b -> 'c) (s:'a list) (t:'b list) =
  with s = "[]"   , t = "[]" => []
  with s = _ :: _ , t = "[]" => []
  with s = "[]"   , t = _ :: _ => []
  with s = x :: s', t = y :: t' => f x y :: map2 f s' t'.

lemma map2_zip (f:'a -> 'b -> 'c) s t :
  map2 f s t = map (fun (p:'a * 'b) => f p.`1 p.`2) (zip s t).

proof.

by elim: s t => [|x s ih] [|y t] //=; rewrite ih.

qed.

lemma size_map2 (f:'a -> 'b -> 'c) (l1:'a list) l2 : size (map2 f l1 l2) = min (size l1) (size l2).

proof.

by elim: l1 l2 => [|x s ih] [|y t] //=; smt(size_ge0).

qed.

lemma nth_map2 dfla dflb dflc (f:'a -> 'b -> 'c) (l1:'a list) l2 i:
  0 <= i < min (size l1) (size l2) =>
  nth dflc (map2 f l1 l2) i = f (nth dfla l1 i) (nth dflb l2 i).

proof.

by elim: l1 l2 i => [|x s ih] [|y t] i //= hi; smt(size_ge0).

qed.

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

by rewrite -MB.addmA addK MB.addm0.

qed.

end Byte.

import Byte.

type bytes = byte list.

theory Key.

type key.

clone include MFinite with
    type t <- key
    rename "dunifin" as "dkey".

end Key.

import Key.

theory Nonce.

type nonce.

clone MFinite with
    type t = nonce
    rename "dunifin" as "dnonce".

end Nonce.

import Nonce.

theory C.

op max_counter : int.

axiom gt0_max_counter : 0 < max_counter.

subtype counter =
    { i : int | 0 <= i < max_counter + 1 }
    rename "ofint", "toint".

realize inhabited.

proof.

by exists 0; smt(gt0_max_counter).

qed.

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

by apply/dmap_ll/dlist_ll/dbyte_ll.

qed.

lemma dblock_uni: is_uniform dblock.

proof.

apply dmap_uni_in_inj; last by apply/dlist_uni/dbyte_uni.

move=> x y hx hy heq.

rewrite -(block_of_bytesdK x) 1:(supp_dlist_size _ _ _ ge0_block_size hx) //.

by rewrite -(block_of_bytesdK y) 1:(supp_dlist_size _ _ _ ge0_block_size hy) // heq.

qed.

lemma dblock_fu: is_full dblock.

proof.

move=> b; rewrite supp_dmap; exists (bytes_of_block b).

rewrite bytes_of_blockKd /= supp_dlist 1:ge0_block_size bytes_of_blockP /=.

by rewrite allP => x _; rewrite dbyte_fu.

qed.

lemma dblock_funi: is_funiform dblock.

proof.

by apply is_full_funiform; [apply dblock_fu | apply dblock_uni].

qed.

op zero = block_of_bytesd (mkseq (fun _ => Byte.zero) block_size).

op (+^) (b1 b2:block) =
     block_of_bytesd (map2 (+^) (bytes_of_block b1) (bytes_of_block b2)).

lemma nth_xor x y i :
     0 <= i < block_size =>
     nth Byte.zero (bytes_of_block (x +^ y)) i =
     nth Byte.zero (bytes_of_block x) i +^ nth Byte.zero (bytes_of_block y) i.

proof.

move=> hi.

rewrite /(+^) block_of_bytesdK 1:size_map2 1:!bytes_of_blockP 1:/#.

by rewrite (nth_map2 Byte.zero Byte.zero) // !bytes_of_blockP /#.

qed.

lemma nth_zero i : nth Byte.zero (bytes_of_block zero) i = Byte.zero.

proof.

rewrite /zero block_of_bytesdK; first (rewrite size_mkseq; smt(ge0_block_size)).

case: (0 <= i < block_size)=> hi.

+ by rewrite nth_mkseq.

+ rewrite nth_out; smt(size_mkseq ge0_block_size).

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

apply bytes_of_block_inj; apply (eq_from_nth Byte.zero); rewrite !bytes_of_blockP // => i hi.

by rewrite nth_xor // Byte.addK nth_zero.

qed.

lemma xorK1 b1 b2 : b1 = b1 +^ b2 +^ b2.

proof.

by rewrite -MB.addmA addK MB.addm0.

qed.

end GenBlock.

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

move=> [hi0 hib]; rewrite /extend.

smt(Block.block_of_bytesdK size_cat size_take size_mkseq nth_cat nth_take nth_mkseq ge0_block_size).

qed.

op chacha20_block : key -> nonce -> C.counter -> block.

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

op chacha20_CTR_encrypt_bytes key nonce counter m =
  gen_CTR_encrypt_bytes map2_xor chacha20_block key nonce counter m.

lemma take_xor_map2_xor m str: map2_xor m str = take_xor m str.

proof.

apply (eq_from_nth Byte.zero).

+ rewrite /map2_xor /take_xor size_map2 size_take 1:size_ge0.

smt(bytes_of_blockP size_ge0 ge0_block_size).

move=> i; rewrite /map2_xor size_map2 => hi.

have hib : 0 <= i < block_size by smt(bytes_of_blockP).

rewrite /take_xor nth_take 1:size_ge0 1:/#.

rewrite nth_xor // nth_extend //.

rewrite (nth_map2 Byte.zero Byte.zero) 1:/#.

smt().

qed.

lemma iter_gen_ctr_round_nil_cat merge genblock k n c m i j :
  let round = gen_ctr_round merge genblock k n in
  iter i round (c, m, j) =
     let (c', m', j') = iter i round ([], m, j) in
     (c ++ c', m', j').

proof.

elim/natind: i c m j => [i0 hi0|i0 hi0 ih] c m j /=.

+ by rewrite !iter0 //=; smt(cats0).

have /= ih1 := ih c m j.

rewrite !iterS // ih1.

move: (iter i0 (gen_ctr_round merge genblock k n) ([], m, j)) => -[z1 z2 z3].

by rewrite /gen_ctr_round /= catA.

qed.

lemma iter_gen_ctr_round_S merge genblock k n c m i j:
  let round = gen_ctr_round merge genblock k n in
  0 <= i =>
  iter (i + 1) round (c, m, j) =
    let (c', m', j') = iter i round ([], drop block_size m, j + 1) in
    (c ++ merge m (genblock k n (C.ofintd j)) ++ c', m', j').

proof.

move=> /= hi.

rewrite iterSr 1:/#.

have -> : gen_ctr_round merge genblock k n (c, m, j)
        = (c ++ merge m (genblock k n (C.ofintd j)), drop block_size m, j + 1).

+ by rewrite /gen_ctr_round /=.

have /= hnc := iter_gen_ctr_round_nil_cat merge genblock k n
                 (c ++ merge m (genblock k n (C.ofintd j)))
                 (drop block_size m) i (j + 1).

by rewrite hnc.

qed.

lemma iter_gen_ctr_round_nil merge genblock k n i j:
  (forall str, merge [] str = []) =>
  let round = gen_ctr_round merge genblock k n in
  iter i round ([], [],j) = ([], [], max j (j + i)).

proof.

move=> hm /=; elim/natind: i j => [i0 hi0|i0 hi0 ih] j.

+ by rewrite iter0 //; smt().

have /= ihj := ih (j + 1).

rewrite iterSr //.

have -> : gen_ctr_round merge genblock k n ([], [], j) = ([], [], j + 1).

+ by rewrite /gen_ctr_round /= hm.

by rewrite ihj /=; smt().

qed.

lemma gen_CTR_encrypt_bytes0 merge genblock k n c :
  (forall str, merge [] str = []) =>
  gen_CTR_encrypt_bytes merge genblock k n c [] = [].

proof.

move=> hm; rewrite /gen_CTR_encrypt_bytes /=.

by rewrite iter0 //=; smt().

qed.

lemma gen_CTR_encrypt_bytes_cons merge genblock k n c m:
  (forall str, merge [] str = []) =>
  gen_CTR_encrypt_bytes merge genblock k n c m =
  merge m (genblock k n (C.ofintd c)) ++
    gen_CTR_encrypt_bytes merge genblock k n (c+1) (drop block_size m).

proof.

move=> hm; rewrite /gen_CTR_encrypt_bytes /=; have h0s := size_ge0 m.

case : (size m < block_size) => hs.

+ have hb : 0 <= size m < `|block_size| by smt().

  rewrite divz_small 1:// modz_small //= size_eq0.

  case: (m = []) => [->> | hne] @/b2i /=; first by rewrite !iter0 // hm.

  rewrite (iter_gen_ctr_round_S _ _ _ _ _ _ 0) // iter0 //=.

  by rewrite drop_oversize 1:/# /= iter0.

have -> : size m = block_size + size (drop block_size m).

+ by rewrite -{1}(cat_take_drop block_size m) size_cat size_take 1:ge0_block_size /#.

have /= -> := divzMDl 1; first smt(gt0_block_size).

rewrite modzDl -addzA addzC iter_gen_ctr_round_S; first smt(size_ge0 gt0_block_size).

by case: (iter _ _ _) => />.

qed.

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

end Step1_2.

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

op check_plaintext (lenc:nonce list) (p:plaintext) =
  let (n, a, m) = p in
  ! n \in lenc /\
  valid_topol a m /\
  size lenc < qenc.

op check_cipher (ndec:int) (c:ciphertext) =
  (let (n, a, m, t) = c in
  valid_topol a m) /\
  ndec < qdec.

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
op inv_cpa (mr1 : (nonce*C.counter, poly_in) fmap)
         (ms1 : (nonce*C.counter, poly_out) fmap)
         (log1 log2: (ciphertext, plaintext) fmap)
         (lc1 lc2 : ciphertext list)
         (lenc1 lenc2: nonce list)
         (ndec1 ndec2 :int) =
     log1 = log2 /\ lenc1 = lenc2 /\ lc1 = lc2 /\ ndec1 = ndec2 /\
     (forall n c, (n,c) \in mr1 => n \in lenc1) /\
     (forall n c, (n,c) \in ms1 => n \in lenc1).
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
op sub_map (m1 : (nonce * C.counter, 'a) fmap) (m2 : (nonce * C.counter, 'a) fmap) i l =
    (forall n, (n, C.ofintd 0) \in m2 => (n,C.ofintd 0) \in m1) /\
    (forall n, (n, C.ofintd 0) \in m2 => m1.[(n,C.ofintd 0)] = m2.[(n,C.ofintd 0)]) /\
    (forall j, 0 <= j < i => (nth witness l j, C.ofintd 0) \in m1) /\
    (forall n, (n, C.ofintd 0) \in m1 => (n, C.ofintd 0) \in m2 \/ exists j, 0 <= j < i /\ n = nth witness l j).
op make_lbad1
    (log : (nonce, associated_data * message * tag) fmap)
    (lc : ciphertext list)
    (lenc : nonce list) =
    flatten
    (map (fun n:nonce =>
            map (fun c:ciphertext => ((oget log.[n]).`3, c.`4))
                (filter (fun c:ciphertext => c.`1 = n) lc))
         lenc).
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

    (forall t t', (t,t') \in lbad1 =>
      (exists n, n \in lenc /\
        (oget ufcmalog.[n]).`3 = t /\
        exists a c, (n, a, c, t') \in lc)).
op w1 : poly_out.
op w2 : poly_out.
declare axiom neq_w1_w2 : w1 <> w2.
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

  (* SCRATCHPAD BEGIN — your own declarations may go below this line *)
clone import Step1_2 as S12.

lemma take_xor_nil (str:Block.block) : take_xor [] str = [].
proof. by rewrite /take_xor take0. qed.

lemma dmap_dblock_mk_rs : dmap dblock mk_rs = dpoly_in `*` dpoly_out.
proof.
  rewrite (SplitC1.sample_spec witness) dmap_comp.
  have -> : (mk_rs \o SplitC1.ofpair) = (fun (p : poly * extra_block) => SplitC2.topair p.`1).
  apply fun_ext => p; case: p => x y /=.
  rewrite /(\o) /mk_rs /SplitC1.ofpair /SplitC2.topair /=.
  have hx := TPoly.bytes_of_polyP x.
  have hy := Extra_block.bytes_of_extra_blockP y.
  rewrite Block.block_of_bytesdK.
  rewrite size_cat hx hy.
  rewrite /poly_size /block_size.
  trivial.
  rewrite /poly_size in hx.
  rewrite (take_size_cat _ _ _ hx).
  trivial.
  rewrite dprod_marginalL dextra_block_ll /=.
  rewrite dscalar1.
  rewrite (SplitC2.sample_spec witness) dmap_comp.
  have -> : (SplitC2.topair \o SplitC2.ofpair) = idfun.
  apply fun_ext => p.
  case: p => r s; rewrite /(\o) /idfun /SplitC2.topair /SplitC2.ofpair /=.
  have hr := Poly_in.bytes_of_poly_inP r.
  have hs := Poly_out.bytes_of_poly_outP s.
  rewrite TPoly.poly_of_bytesdK.
  rewrite size_cat hr hs /poly_size.
  trivial.
  rewrite (take_size_cat _ _ _ hr) (drop_size_cat _ _ _ hr) Poly_in.bytes_of_poly_inKd Poly_out.bytes_of_poly_outKd.
  trivial.
  rewrite dmap_id.
  trivial.
qed.

lemma dmap_addpoly (x:poly_out) : dmap dpoly_out (fun s => s + x) = dpoly_out.
proof.
apply eq_distr => u; rewrite dmap1E.
have -> : (pred1 u \o (fun (s:poly_out) => s + x)) = pred1 (u - x).
+ apply fun_ext => s; rewrite /(\o) /pred1 eq_iff; split.
  + by move=> <-; apply poly_out_add_sub.
  by move=> ->; rewrite -poly_out_sub_add.
by apply dpoly_out_funi.
qed.

lemma dmap_tag (q:polynomial) :
  dmap dblock (fun b => poly1305 (mk_rs b).`1 (mk_rs b).`2 q) = dpoly_out.
proof.
have -> : (fun (b:block) => poly1305 (mk_rs b).`1 (mk_rs b).`2 q)
        = ((fun (rs:poly_in*poly_out) => poly1305 rs.`1 rs.`2 q) \o mk_rs).
+ by apply fun_ext.
rewrite -dmap_comp dmap_dblock_mk_rs dprod_dlet dmap_dlet.
have -> : (fun (r:poly_in) =>
             dmap (dlet dpoly_out (fun (s:poly_out) => dunit (r,s)))
                  (fun (rs:poly_in*poly_out) => poly1305 rs.`1 rs.`2 q))
        = (fun (_:poly_in) => dpoly_out).
+ apply fun_ext => r /=.
  rewrite dmap_dlet /=.
  have -> : (fun (a:poly_out) => dmap (dunit (r,a)) (fun (rs:poly_in*poly_out) => poly1305 rs.`1 rs.`2 q))
          = (fun (a:poly_out) => dunit (a + poly1305_eval r q)).
  + by apply fun_ext => a; rewrite dmap_dunit /poly1305.
  by move: (dmap_addpoly (poly1305_eval r q)); rewrite /dmap /(\o) /= => ->.
by apply dlet_cst; apply dpoly_in_ll.
qed.

equiv D_enc_real :
  D(BNR_Adv(A), IndBlock).O.enc ~ RealOrcls(ChaChaPoly).enc :
    ={arg} /\ IndBlock.k{1} = Mem.k{2} ==> ={res} /\ IndBlock.k{1} = Mem.k{2}.
proof.
proc; inline *.
wp.
while{1} (0 <= size p0{1} /\ n0{1} = n{1} /\
   c0{1} ++ gen_CTR_encrypt_bytes take_xor chacha20_block IndBlock.k{1} n{1} i{1} p0{1}
     = gen_CTR_encrypt_bytes take_xor chacha20_block IndBlock.k{1} n{1} 1 p{1})
  (size p0{1}).
+ move=> &m z; auto => /> &hr h0 heq hne; split.
  + split; 1: smt(size_ge0).
    rewrite -heq (gen_CTR_encrypt_bytes_cons take_xor chacha20_block IndBlock.k{hr} n{hr} i{hr} p0{hr} take_xor_nil).
    by rewrite catA /take_xor.
  smt(size_drop gt0_block_size size_ge0 size_eq0).
auto => /> &1; split; 1: smt(size_ge0).
move=> c0L iL p0L; split; 1: smt(size_eq0 size_ge0).
rewrite (gen_CTR_encrypt_bytes0 take_xor chacha20_block Mem.k{1} p{1}.`1 iL take_xor_nil) cats0 => ->.
by rewrite /genpoly1305 /=; case: (mk_rs (chacha20_block Mem.k{1} p{1}.`1 (C.ofintd 0))).
qed.

equiv D_dec_real :
  D(BNR_Adv(A), IndBlock).O.dec ~ RealOrcls(ChaChaPoly).dec :
    ={arg} /\ IndBlock.k{1} = Mem.k{2} ==> ={res} /\ IndBlock.k{1} = Mem.k{2}.
proof.
proc; inline *.
sp 10 5.
if; 1: by move=> /> /#.
+ wp.
  while{1} (0 <= size p0{1} /\ n1{1} = n{1} /\
     c1{1} ++ gen_CTR_encrypt_bytes take_xor chacha20_block IndBlock.k{1} n{1} i{1} p0{1}
       = gen_CTR_encrypt_bytes take_xor chacha20_block IndBlock.k{1} n{1} 1 c{1})
    (size p0{1}).
  + move=> &m z; auto => /> &hr h0 heq hne; split.
    + split; 1: smt(size_ge0).
      rewrite -heq (gen_CTR_encrypt_bytes_cons take_xor chacha20_block IndBlock.k{hr} n{hr} i{hr} p0{hr} take_xor_nil).
      by rewrite catA /take_xor.
    smt(size_drop gt0_block_size size_ge0 size_eq0).
  auto => /> &2; split; 1: smt(size_ge0).
  move=> c1L iL p0L; split; 1: smt(size_eq0 size_ge0).
  by rewrite (gen_CTR_encrypt_bytes0 take_xor chacha20_block Mem.k{2} n{2} iL take_xor_nil) cats0.
auto.
qed.

lemma step1 &m :
  Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] =
  Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res].
proof.
byequiv => //; proc; inline *; wp.
call (_: IndBlock.k{1} = Mem.k{2} /\ ={BNR.lenc, BNR.ndec}).
+ proc; sp; if; 1,3: by auto.
  by wp; call D_enc_real; auto.
+ proc; sp; if; 1,3: by auto.
  by wp; call D_dec_real; auto.
by auto.
qed.



op enck (m : OpCCRO.globS) (p:plaintext) : ciphertext = CCA_UFCMA.enc m witness p.
op deck (m : OpCCRO.globS) (c:ciphertext) : plaintext option = CCA_UFCMA.dec m witness c.
op badf (m : OpCCRO.globS) (lc : ciphertext list) = has (fun c => deck m c <> None) lc.

op rs_of (m : OpCCRO.globS) (n:nonce) = mk_rs (oget m.[(n, C.ofintd 0)]).

op romOK (m : OpCCRO.globS) (lenc : nonce list) =
  forall n c, (n,c) \in m => n \in lenc.

op logok (m : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap) =
  forall cph, cph \in lg => deck m cph = lg.[cph].

lemma deck_someP (m : OpCCRO.globS) (cph:ciphertext) :
  (deck m cph <> None) =
  (cph.`4 = poly1305 (rs_of m cph.`1).`1 (rs_of m cph.`1).`2 (topol cph.`2 cph.`3)).
proof.
rewrite /deck /rs_of /CCA_UFCMA.dec /genpoly1305 /get /=.
case: cph => n a c t /=.
by case: (mk_rs (oget m.[(n, C.ofintd 0)])) => r s /=; case: (t = poly1305 r s (topol a c)).
qed.

lemma test_poly_deck (m : OpCCRO.globS) (n:nonce) (lc:ciphertext list) :
  test_poly n lc (mk_rs (oget m.[(n, C.ofintd 0)])).`1 (mk_rs (oget m.[(n, C.ofintd 0)])).`2 =
  has (fun (cph:ciphertext) => cph.`1 = n /\ deck m cph <> None) lc.
proof.
rewrite /test_poly /=; elim: lc => //= cph lc ih.
case: (cph.`1 = n) => hn /=; last by rewrite ih.
by rewrite ih deck_someP hn.
qed.

(* ---------------- games ---------------- *)

module Orc3 (RO:RO) = {
  proc cc (n:nonce, p:message) : bytes = {
    var i, z, c;
    c <- []; i <- 1;
    while (p <> []) {
      z <@ RO.get(n, C.ofintd i);
      c <- c ++ take (size p) (bytes_of_block (extend p +^ z));
      p <- drop block_size p;
      i <- i + 1;
    }
    return c;
  }

  proc mac (n:nonce, a:associated_data, c:message) : tag = {
    var b, r, s;
    b <@ RO.get(n, C.ofintd 0);
    (r,s) <- mk_rs b;
    return poly1305 r s (topol a c);
  }

  proc enc (nap : plaintext) : ciphertext = {
    var n, a, p, c, t;
    (n,a,p) <- nap;
    c <@ cc(n,p);
    t <@ mac(n,a,c);
    Mem.log.[(n,a,c,t)] <- (n,a,p);
    return (n,a,c,t);
  }

  proc dec (cph : ciphertext) : plaintext option = {
    var n, a, c, t, t', p, r;
    r <- None;
    (n,a,c,t) <- cph;
    Mem.lc <- if cph \in Mem.log then Mem.lc else cph :: Mem.lc;
    t' <@ mac(n,a,c);
    if (t = t') { p <@ cc(n,c); r <- Some (n,a,p); }
    return r;
  }
}.

module Orc4 (RO:RO) = {
  include Orc3(RO) [enc]

  proc dec (cph : ciphertext) : plaintext option = {
    Mem.lc <- if cph \in Mem.log then Mem.lc else cph :: Mem.lc;
    return Mem.log.[cph];
  }
}.

module G3 (Ad:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b;
    Mem.log <- empty; Mem.lc <- [];
    b <@ Ad(Orc3(RO)).main();
    return b;
  }
}.

module G4 (Ad:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b;
    Mem.log <- empty; Mem.lc <- [];
    b <@ Ad(Orc4(RO)).main();
    return b;
  }
}.

module G5end (RO:RO) = {
  proc main () = {
    var ns, forged, i, n, bl, r, s;
    ns <- undup (List.map (fun (c:ciphertext) => c.`1) Mem.lc);
    forged <- false;
    i <- 0;
    while (i < size ns) {
      n <- List.nth witness ns i;
      bl <@ RO.get(n, C.ofintd 0);
      (r,s) <- mk_rs bl;
      forged <- forged || test_poly n Mem.lc r s;
      i <- i + 1;
    }
    return forged;
  }
}.

module G5 (Ad:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b, f;
    b <@ G4(Ad,RO).distinguish();
    f <@ G5end(RO).main();
    return f;
  }
}.

lemma gen_CTR_nil (f : key -> nonce -> C.counter -> block) k n c :
  gen_CTR_encrypt_bytes take_xor f k n c [] = [].
proof. by apply gen_CTR_encrypt_bytes0; apply take_xor_nil. qed.

lemma gen_CTR_cons (f : key -> nonce -> C.counter -> block) k n c m :
  gen_CTR_encrypt_bytes take_xor f k n c m =
  take_xor m (f k n (C.ofintd c)) ++ gen_CTR_encrypt_bytes take_xor f k n (c+1) (drop block_size m).
proof. by apply gen_CTR_encrypt_bytes_cons; apply take_xor_nil. qed.

lemma cc_spec (mm : OpCCRO.globS) (nn:nonce) (pp:message) :
  hoare [ Orc3(FinRO).cc : RO.m = mm /\ arg = (nn,pp) ==>
          RO.m = mm /\ res = gen_CTR_encrypt_bytes take_xor (S12.get mm) witness nn 1 pp ].
proof.
proc; inline FinRO.get.
while (RO.m = mm /\ n = nn /\
       c ++ gen_CTR_encrypt_bytes take_xor (S12.get mm) witness nn i p =
       gen_CTR_encrypt_bytes take_xor (S12.get mm) witness nn 1 pp).
+ auto => /> &hr heq hne.
  rewrite (gen_CTR_cons (S12.get mm) witness nn i{hr} p{hr}) in heq.
  by rewrite -heq catA /take_xor /S12.get.
auto => />; smt(gen_CTR_nil cat0s cats0).
qed.

lemma mac_spec (mm : OpCCRO.globS) (nn:nonce) (aa:associated_data) (ccv:message) :
  hoare [ Orc3(FinRO).mac : RO.m = mm /\ arg = (nn,aa,ccv) ==>
          RO.m = mm /\ res = genpoly1305 (S12.get mm) witness nn (topol aa ccv) ].
proof.
by proc; inline FinRO.get; auto => />.
qed.

lemma deck_enck (m : OpCCRO.globS) (q:plaintext) : deck m (enck m q) = Some q.
proof. by rewrite /deck /enck; apply CCA_UFCMA.dec_enc. qed.

lemma logok_set (m : OpCCRO.globS) lg (q:plaintext) :
  logok m lg => logok m lg.[enck m q <- q].
proof.
move=> h cph; rewrite mem_set get_setE.
case: (cph = enck m q) => [->|hne] /=; first by apply deck_enck.
by move=> hin; apply h.
qed.

lemma enck_expandP (m : OpCCRO.globS) (nap:plaintext) :
  enck m nap =
  (nap.`1, nap.`2, gen_CTR_encrypt_bytes take_xor (S12.get m) witness nap.`1 1 nap.`3,
   poly1305 (mk_rs (oget m.[(nap.`1, C.ofintd 0)])).`1 (mk_rs (oget m.[(nap.`1, C.ofintd 0)])).`2
            (topol nap.`2 (gen_CTR_encrypt_bytes take_xor (S12.get m) witness nap.`1 1 nap.`3))).
proof.
rewrite /enck /CCA_UFCMA.enc /genpoly1305 /S12.get; case: nap => n a p /=.
by case: (mk_rs (oget m.[(n, C.ofintd 0)])).
qed.

lemma enc_logok :
  hoare [ Orc3(FinRO).enc : logok RO.m Mem.log ==> logok RO.m Mem.log ].
proof.
proc; inline *.
wp.
while (logok RO.m Mem.log /\ (n,a,p) = nap /\ n0 = n /\
       c0 ++ gen_CTR_encrypt_bytes take_xor (S12.get RO.m) witness n i p0 =
       gen_CTR_encrypt_bytes take_xor (S12.get RO.m) witness n 1 p).
+ auto => /> &hr hlog heq hne.
  rewrite (gen_CTR_cons (S12.get RO.m{hr}) witness n{hr} i{hr} p0{hr}) in heq.
  by rewrite -heq catA /take_xor /S12.get.
auto => /> &hr hlog.
split; first by smt().
move=> c00 i0 _ heq.
have -> : c00 = gen_CTR_encrypt_bytes take_xor (S12.get RO.m{hr}) witness nap{hr}.`1 1 nap{hr}.`3.
+ by move: heq; rewrite (gen_CTR_nil (S12.get RO.m{hr}) witness nap{hr}.`1 i0) cats0.
have -> : (nap{hr}.`1, nap{hr}.`2, nap{hr}.`3) = nap{hr} by smt().
by rewrite -enck_expandP; apply logok_set.
qed.

lemma cc_ll : islossless Orc3(FinRO).cc.
proof.
proc; inline*.
while (true) (size p).
+ by move=> z; auto; smt(size_drop gt0_block_size size_ge0 size_eq0).
by auto; smt(size_eq0 size_ge0).
qed.

lemma mac_ll : islossless Orc3(FinRO).mac.
proof. by proc; inline*; auto. qed.

lemma Orc3_enc_ll : islossless Orc3(FinRO).enc.
proof. by proc; wp; call mac_ll; call cc_ll; auto. qed.

lemma Orc3_dec_ll : islossless Orc3(FinRO).dec.
proof.
proc; inline*; sp; if; last by auto.
wp; while (true) (size p0).
+ by move=> z; auto; smt(size_drop gt0_block_size size_ge0 size_eq0).
by auto; smt(size_eq0 size_ge0).
qed.

lemma deck_val (m : OpCCRO.globS) (cph:ciphertext) :
  deck m cph =
  if cph.`4 = poly1305 (mk_rs (oget m.[(cph.`1, C.ofintd 0)])).`1
                       (mk_rs (oget m.[(cph.`1, C.ofintd 0)])).`2 (topol cph.`2 cph.`3)
  then Some (cph.`1, cph.`2, gen_CTR_encrypt_bytes take_xor (S12.get m) witness cph.`1 1 cph.`3)
  else None.
proof.
rewrite /deck /CCA_UFCMA.dec /genpoly1305 /S12.get; case: cph => n a c t /=.
by case: (mk_rs (oget m.[(n, C.ofintd 0)])).
qed.

lemma dec_hoare (mm : OpCCRO.globS) (cphv : ciphertext)
                (lg : (ciphertext,plaintext) fmap) (lcv : ciphertext list) :
  hoare [ Orc3(FinRO).dec :
    RO.m = mm /\ arg = cphv /\ Mem.log = lg /\ Mem.lc = lcv ==>
    RO.m = mm /\ Mem.log = lg /\
    Mem.lc = (if cphv \in lg then lcv else cphv :: lcv) /\ res = deck mm cphv ].
proof.
proc; inline*; sp.
if.
+ wp.
  while (RO.m = mm /\ Mem.log = lg /\ Mem.lc = (if cphv \in lg then lcv else cphv :: lcv) /\
         n1 = cphv.`1 /\ t = t' /\ (n,a,c,t) = cphv /\
         c1 ++ gen_CTR_encrypt_bytes take_xor (S12.get mm) witness cphv.`1 i p0 =
         gen_CTR_encrypt_bytes take_xor (S12.get mm) witness cphv.`1 1 cphv.`3).
  + auto => /> &hr heq hne.
    rewrite (gen_CTR_cons (S12.get mm) witness n{hr} i{hr} p0{hr}) in heq.
    by rewrite -heq catA /take_xor /S12.get.
  auto => />; smt(deck_val gen_CTR_nil cats0 cat0s).
auto => />; smt(deck_val).
qed.

lemma dec_spec (mm : OpCCRO.globS) (cphv : ciphertext)
               (lg : (ciphertext,plaintext) fmap) (lcv : ciphertext list) :
  phoare [ Orc3(FinRO).dec :
    RO.m = mm /\ arg = cphv /\ Mem.log = lg /\ Mem.lc = lcv ==>
    RO.m = mm /\ Mem.log = lg /\
    Mem.lc = (if cphv \in lg then lcv else cphv :: lcv) /\ res = deck mm cphv ] = 1%r.
proof. by conseq Orc3_dec_ll (dec_hoare mm cphv lg lcv). qed.

(* ---------------- steps ---------------- *)

equiv cc_eq : D(BNR_Adv(A), IndRO).O.ChaCha.enc ~ Orc3(RO).cc :
  ={arg, RO.m} ==> ={res, RO.m}.
proof. proc; sim. qed.

equiv mac_eq : D(BNR_Adv(A), IndRO).O.Poly.mac ~ Orc3(RO).mac :
  ={arg, RO.m} ==> ={res, RO.m}.
proof. proc; sim. qed.

equiv Oenc_eq : D(BNR_Adv(A), IndRO).O.enc ~ Orc3(RO).enc :
  ={arg, RO.m} ==> ={res, RO.m}.
proof. proc; wp; call mac_eq; call cc_eq; auto. qed.

equiv Odec_eq : D(BNR_Adv(A), IndRO).O.dec ~ Orc3(RO).dec :
  ={arg, RO.m} ==> ={res, RO.m}.
proof.
proc.
sp 2 3.
seq 1 1 : (={RO.m, n, a, c, t, t'} /\ result{1} = r{2}); first by call mac_eq.
if; 1: by move=> />.
+ by wp; call cc_eq; auto.
by auto.
qed.

lemma L1 &m :
  Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res] =
  Pr[MainD(G3(BNR_Adv(A)), RO).distinguish() @ &m : res].
proof.
byequiv => //; proc; inline *; wp.
call (_: ={RO.m, BNR.lenc, BNR.ndec}).
+ proc; sp; if; 1,3: by auto.
  by wp; call Oenc_eq; auto.
+ proc; sp; if; 1,3: by auto.
  by wp; call Odec_eq; auto.
by auto.
qed.

lemma L2 &m :
  Pr[MainD(G3(BNR_Adv(A)), RO).distinguish() @ &m : res] =
  Pr[MainD(G3(BNR_Adv(A)), FinRO).distinguish() @ &m : res].
proof.
have hll : forall (_:nonce*C.counter), is_lossless dblock by move=> _; apply dblock_ll.
by apply (FiniteRO.pr_RO_FinRO_D hll (G3(BNR_Adv(A))) &m () (fun b => b)).
qed.

lemma enc_logok4 :
  hoare [ Orc4(FinRO).enc : logok RO.m Mem.log ==> logok RO.m Mem.log ].
proof.
proc; inline *.
wp.
while (logok RO.m Mem.log /\ (n,a,p) = nap /\ n0 = n /\
       c0 ++ gen_CTR_encrypt_bytes take_xor (S12.get RO.m) witness n i p0 =
       gen_CTR_encrypt_bytes take_xor (S12.get RO.m) witness n 1 p).
+ auto => /> &hr hlog heq hne.
  rewrite (gen_CTR_cons (S12.get RO.m{hr}) witness n{hr} i{hr} p0{hr}) in heq.
  by rewrite -heq catA /take_xor /S12.get.
auto => /> &hr hlog.
split; first by smt().
move=> c00 i0 _ heq.
have -> : c00 = gen_CTR_encrypt_bytes take_xor (S12.get RO.m{hr}) witness nap{hr}.`1 1 nap{hr}.`3.
+ by move: heq; rewrite (gen_CTR_nil (S12.get RO.m{hr}) witness nap{hr}.`1 i0) cats0.
have -> : (nap{hr}.`1, nap{hr}.`2, nap{hr}.`3) = nap{hr} by smt().
by rewrite -enck_expandP; apply logok_set.
qed.

lemma Orc4_enc_ll : islossless Orc4(FinRO).enc.
proof. by proc; wp; call mac_ll; call cc_ll; auto. qed.

lemma Orc3_enc_bad : hoare [ Orc3(FinRO).enc : badf RO.m Mem.lc ==> badf RO.m Mem.lc ].
proof. by proc; inline*; wp; while (badf RO.m Mem.lc); auto. qed.

lemma Orc4_enc_bad : hoare [ Orc4(FinRO).enc : badf RO.m Mem.lc ==> badf RO.m Mem.lc ].
proof. by proc; inline*; wp; while (badf RO.m Mem.lc); auto. qed.

lemma Orc4_enc_badll : phoare [ Orc4(FinRO).enc : badf RO.m Mem.lc ==> badf RO.m Mem.lc ] = 1%r.
proof. by conseq Orc4_enc_ll Orc4_enc_bad. qed.

lemma Orc4_dec_ll : islossless Orc4(FinRO).dec.
proof. by proc; auto. qed.

lemma badf_cons (m : OpCCRO.globS) cph (lc : ciphertext list) :
  badf m lc => badf m (cph :: lc).
proof. by rewrite /badf /= => ->; rewrite orbT. qed.

lemma Orc4_dec_bad : hoare [ Orc4(FinRO).dec : badf RO.m Mem.lc ==> badf RO.m Mem.lc ].
proof.
proc; auto => /> &hr hb.
by case: (cph{hr} \in Mem.log{hr}) => // _; apply badf_cons.
qed.

lemma Orc4_dec_badll : phoare [ Orc4(FinRO).dec : badf RO.m Mem.lc ==> badf RO.m Mem.lc ] = 1%r.
proof. by conseq Orc4_dec_ll Orc4_dec_bad. qed.

equiv Orc34_enc :
  Orc3(FinRO).enc ~ Orc4(FinRO).enc :
    ={arg, RO.m, Mem.log, Mem.lc} /\ logok RO.m{1} Mem.log{1}
    ==> ={res, RO.m, Mem.log, Mem.lc} /\ logok RO.m{1} Mem.log{1}.
proof.
conseq (_: ={arg, RO.m, Mem.log, Mem.lc} ==> ={res, RO.m, Mem.log, Mem.lc}) enc_logok _ => //.
by sim.
qed.

equiv Orc34_dec :
  Orc3(FinRO).dec ~ Orc4(FinRO).dec :
    ={arg, RO.m, Mem.log, Mem.lc} /\ logok RO.m{1} Mem.log{1}
    ==> ={RO.m, Mem.log, Mem.lc} /\ logok RO.m{1} Mem.log{1} /\
        (! badf RO.m{2} Mem.lc{2} => ={res}).
proof.
proc*.
inline{2} Orc4(FinRO).dec.
wp.
exists* RO.m{1}; elim* => mm.
exists* cph{1}; elim* => cphv.
exists* Mem.log{1}; elim* => lg.
exists* Mem.lc{1}; elim* => lcv.
call{1} (dec_spec mm cphv lg lcv).
auto => /> hlog.
case: (cphv \in lg) => hin /=; first by move=> _; apply hlog.
by rewrite /badf /= => h; smt(domE).
qed.

lemma L3eq &m :
  Pr[MainD(G3(BNR_Adv(A)), FinRO).distinguish() @ &m : res] <=
  Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : res \/ badf RO.m Mem.lc].
proof.
byequiv (_: ={glob A} ==> res{1} => (res{2} \/ badf RO.m{2} Mem.lc{2})) => //.
proc.
seq 1 1 : (={glob A, RO.m}); first by sim.
inline{1} G3(BNR_Adv(A), FinRO).distinguish.
inline{2} G4(BNR_Adv(A), FinRO).distinguish.
inline{1} BNR_Adv(A, Orc3(FinRO)).main.
inline{2} BNR_Adv(A, Orc4(FinRO)).main.
inline{1} BNR(Orc3(FinRO)).init.
inline{2} BNR(Orc4(FinRO)).init.
wp.
call (_: badf RO.m Mem.lc,
         ={RO.m, Mem.log, Mem.lc, BNR.lenc, BNR.ndec} /\ logok RO.m{1} Mem.log{1},
         true).
+ exact A_ll.
+ conseq (_: _ ==> ={res, RO.m, Mem.log, Mem.lc, BNR.lenc, BNR.ndec} /\ logok RO.m{1} Mem.log{1}) => //.
  proc; sp; if; 1,3: by auto.
  by wp; call Orc34_enc; auto.
+ move=> &2 _; proc; sp; if; last by auto.
  by wp; call Orc3_enc_ll; auto.
+ move=> _; proc; sp; if; last by auto.
  by wp; call Orc4_enc_badll; auto.
+ conseq (_: _ ==> ={RO.m, Mem.log, Mem.lc, BNR.lenc, BNR.ndec} /\ logok RO.m{1} Mem.log{1} /\
                   (! badf RO.m{2} Mem.lc{2} => ={res})) => //; first smt().
  proc; sp; if; 1: by auto.
  + by wp; call Orc34_dec; auto.
  by auto.
+ move=> &2 _; proc; sp; if; last by auto.
  by wp; call Orc3_dec_ll; auto.
+ move=> _; proc; sp; if; last by auto.
  by wp; call Orc4_dec_badll; auto.
auto => /> &2; smt(mem_empty).
qed.

lemma L3 &m :
  Pr[MainD(G3(BNR_Adv(A)), FinRO).distinguish() @ &m : res] <=
  Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : res] +
  Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : badf RO.m Mem.lc].
proof.
have h := L3eq &m.
have h2 : Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : res \/ badf RO.m Mem.lc] <=
          Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : res] +
          Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : badf RO.m Mem.lc].
+ rewrite Pr[mu_or]; smt(mu_bounded).
smt().
qed.

lemma L4 &m :
  Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : res] =
  Pr[MainD(G4(BNR_Adv(A)), RO).distinguish() @ &m : res].
proof.
have hll : forall (_:nonce*C.counter), is_lossless dblock by move=> _; apply dblock_ll.
by have /= <- := FiniteRO.pr_RO_FinRO_D hll (G4(BNR_Adv(A))) &m () (fun b => b).
qed.

lemma flat_badf (m : OpCCRO.globS) (lc : ciphertext list) :
  has (fun (nn:nonce) => has (fun (cph:ciphertext) => cph.`1 = nn /\ deck m cph <> None) lc)
      (undup (map (fun (c:ciphertext) => c.`1) lc)) = badf m lc.
proof.
rewrite /badf eq_iff !hasP /=; split.
+ move=> [nn] [_ hh]; move: hh; rewrite hasP /= => -[cph] [h1] [_ h2].
  by exists cph.
move=> [cph] [h1 h2]; exists cph.`1; rewrite mem_undup; split.
+ by rewrite mapP /=; exists cph.
by rewrite hasP /=; exists cph.
qed.

lemma L5 &m :
  Pr[MainD(G4(BNR_Adv(A)), FinRO).distinguish() @ &m : badf RO.m Mem.lc] =
  Pr[MainD(G5(BNR_Adv(A)), FinRO).distinguish() @ &m : res].
proof.
byequiv (_: ={glob A} ==> badf RO.m{1} Mem.lc{1} = res{2}) => //.
proc.
inline{2} G5(BNR_Adv(A), FinRO).distinguish.
swap{2} 2 -1.
sp 0 1.
seq 2 2 : (={RO.m, Mem.lc}); first by inline *; sim.
inline *.
wp.
while{2} (0 <= i{2} <= size ns{2} /\
          ns{2} = undup (map (fun (c:ciphertext) => c.`1) Mem.lc{2}) /\
          Mem.lc{1} = Mem.lc{2} /\ RO.m{1} = RO.m{2} /\
          forged{2} = has (fun (nn:nonce) =>
             has (fun (cph:ciphertext) => cph.`1 = nn /\ deck RO.m{2} cph <> None) Mem.lc{2})
             (take i{2} ns{2}))
  (size ns{2} - i{2}).
+ move=> &1 z; auto => /> &hr h0 h1 h2.
  split; 2: smt().
  split; 1: smt().
  rewrite (take_nth witness) 1:/# -cats1 has_cat /=.
  rewrite (test_poly_deck RO.m{1} _ Mem.lc{1}); smt().
auto => /> &2; split; first by rewrite take0 /=; smt(size_ge0).
move=> i_R; split; first smt().
move=> h1 h2 h3.
have -> : i_R = size (undup (map (fun (c:ciphertext) => c.`1) Mem.lc{2})) by smt().
by rewrite take_size flat_badf.
qed.

lemma L6 &m :
  Pr[MainD(G5(BNR_Adv(A)), FinRO).distinguish() @ &m : res] =
  Pr[MainD(G5(BNR_Adv(A)), RO).distinguish() @ &m : res].
proof.
have hll : forall (_:nonce*C.counter), is_lossless dblock by move=> _; apply dblock_ll.
by have /= <- := FiniteRO.pr_RO_FinRO_D hll (G5(BNR_Adv(A))) &m () (fun b => b).
qed.

lemma dmap_tag_set (m : OpCCRO.globS) (x0 : nonce*C.counter) (q:polynomial) :
  dmap dblock (fun r1 => poly1305 (mk_rs (oget m.[x0 <- r1].[x0])).`1
                                  (mk_rs (oget m.[x0 <- r1].[x0])).`2 q) = dpoly_out.
proof.
have -> : (fun (r1:block) => poly1305 (mk_rs (oget m.[x0 <- r1].[x0])).`1
                                      (mk_rs (oget m.[x0 <- r1].[x0])).`2 q)
        = (fun (b:block) => poly1305 (mk_rs b).`1 (mk_rs b).`2 q).
+ by apply fun_ext => z; rewrite get_set_sameE.
by apply dmap_tag.
qed.

lemma ctr_bound (i sz : int) :
  1 <= i => 0 < sz => sz + (i-1)*block_size <= max_cipher_size => i <= C.max_counter.
proof.
move=> hi hsz hle.
case: (i <= C.max_counter) => // hn.
have hord : C.max_counter <= i - 1 by smt().
have hbs0 : 0 <= block_size by smt(gt0_block_size).
have hmul := IntOrder.ler_wpmul2r block_size hbs0 C.max_counter (i-1) hord.
have hmax := max_cipher_size_ok.
have gen : forall (a b c d : int), a + c <= b => b <= d => d <= c => 0 < a => false by smt().
by apply (gen sz max_cipher_size ((i-1)*block_size) (C.max_counter*block_size)).
qed.

lemma xorKb (b z : Block.block) : b +^ (b +^ z) = z.
proof. by rewrite Block.MB.addmA Block.addK Block.MB.add0m. qed.

lemma encEq (pv : plaintext) :
  equiv [ Orc4(RO).enc ~ CPA_CCA_Orcls(EncRnd).enc :
    ={arg, Mem.log} /\ arg{1} = pv /\ ={BNR.lenc} /\
    ! (pv.`1 \in BNR.lenc{1}) /\ valid_topol pv.`2 pv.`3 /\
    romOK RO.m{1} BNR.lenc{1}
    ==> ={res, Mem.log} /\ res{1}.`1 = pv.`1 /\ romOK RO.m{1} (pv.`1 :: BNR.lenc{1}) ].
proof.
proc.
inline{2} EncRnd.enc.
inline{1} Orc3(RO).mac.
inline{1} Orc3(RO).cc.
inline{2} EncRnd.cc.
inline{1} RO.get.
seq 5 7 : (={Mem.log, BNR.lenc} /\ c1{1} = c1{2} /\ i{1} = i{2} /\ 1 <= i{1} /\ n1{1} = pv.`1 /\ n{1} = pv.`1 /\ a{1} = pv.`2 /\ n{2} = pv.`1 /\ a{2} = pv.`2 /\ size p0{1} = size p1{2} /\ (p0{1} <> [] => size p0{1} + (i{1} - 1) * block_size <= max_cipher_size) /\ ! (pv.`1 \in BNR.lenc{1}) /\ (forall n' c', (n', c') \in RO.m{1} => n' \in BNR.lenc{1} \/ n' = pv.`1) /\ (forall c', (pv.`1, c') \in RO.m{1} => 1 <= C.toint c' < i{1}) /\ p{1} = pv.`3 /\ p{2} = pv).
+ by auto => />; smt(size_map).
seq 1 1 : (={Mem.log, BNR.lenc} /\ c1{1} = c1{2} /\ i{1} = i{2} /\ 1 <= i{1} /\ n1{1} = pv.`1 /\ n{1} = pv.`1 /\ a{1} = pv.`2 /\ n{2} = pv.`1 /\ a{2} = pv.`2 /\ size p0{1} = size p1{2} /\ (p0{1} <> [] => size p0{1} + (i{1} - 1) * block_size <= max_cipher_size) /\ ! (pv.`1 \in BNR.lenc{1}) /\ (forall n' c', (n', c') \in RO.m{1} => n' \in BNR.lenc{1} \/ n' = pv.`1) /\ (forall c', (pv.`1, c') \in RO.m{1} => 1 <= C.toint c' < i{1}) /\ p{1} = pv.`3 /\ p{2} = pv /\ p0{1} = [] /\ p1{2} = []).
while (={Mem.log, BNR.lenc} /\ c1{1} = c1{2} /\ i{1} = i{2} /\ 1 <= i{1} /\ n1{1} = pv.`1 /\ n{1} = pv.`1 /\ a{1} = pv.`2 /\ n{2} = pv.`1 /\ a{2} = pv.`2 /\ size p0{1} = size p1{2} /\ (p0{1} <> [] => size p0{1} + (i{1} - 1) * block_size <= max_cipher_size) /\ ! (pv.`1 \in BNR.lenc{1}) /\ (forall n' c', (n', c') \in RO.m{1} => n' \in BNR.lenc{1} \/ n' = pv.`1) /\ (forall c', (pv.`1, c') \in RO.m{1} => 1 <= C.toint c' < i{1}) /\ p{1} = pv.`3 /\ p{2} = pv).
sp 1 0.
seq 1 1 : (#pre /\ r0{1} = extend p0{1} +^ z{2}).
rnd (fun (zz : block) => extend p0{1} +^ zz) (fun (zz : block) => extend p0{1} +^ zz).
skip => /> *.
by split => [zR _|h r0L hr]; rewrite xorKb.
rcondt{1} 1.
auto => />.
move=> &hr.
move=> Hi Hsz Hb Hnot Hdom Hctr Hp0 Hp1.
have Hb' := Hb Hp0.
have Hsize_ne : size p0{hr} <> 0 by smt(size_eq0).
have Hsize_pos : 0 < size p0{hr} by smt(size_ge0).
have Hi_max : i{m} <= C.max_counter.
case: (i{m} <= C.max_counter) => // Hn.
have Hord : C.max_counter <= i{m} - 1 by smt().
have Hbs0 : 0 <= block_size by smt(gt0_block_size).
have Hmul := IntOrder.ler_wpmul2r block_size Hbs0 C.max_counter (i{m} - 1) Hord.
have Hmax := max_cipher_size_ok.
have Hmid := IntOrder.ler_trans max_cipher_size (size p0{hr} + (i{m} - 1) * block_size) (C.max_counter * block_size) Hb' Hmax.
have Hcycle := IntOrder.ler_trans (C.max_counter * block_size) (size p0{hr} + (i{m} - 1) * block_size) ((i{m} - 1) * block_size) Hmid Hmul.
have Hnonpos : size p0{hr} <= 0 by rewrite -(IntOrder.ler_add2r ((i{m} - 1) * block_size)); exact Hcycle.
smt().
smt(C.ofintdK).
auto => /> &1 &2 Hi Hsz Hb Hnot Hdom Hctr Hp0 Hp1.
have Hsz_pos : 0 < size p0{1} by smt(size_ge0 size_eq0).
have Hb' := Hb Hp0.
have Hi_max : i{2} <= C.max_counter by apply (ctr_bound i{2} (size p0{1})).
have Hoi : C.toint (C.ofintd i{2}) = i{2} by rewrite C.ofintdK; smt().
have Hbs0 : 0 <= block_size by smt(gt0_block_size).
have Hd1 := size_drop block_size p0{1} Hbs0.
have Hd2 := size_drop block_size p1{2} Hbs0.
rewrite get_set_sameE /= xorKb Hsz /=.
split; 2: smt(size_eq0 size_ge0).
split; 1: smt().
split; 1: smt().
split.
+ move=> Hne.
  have Hde : size (drop block_size p1{2}) = size p1{2} - block_size by smt(size_eq0 size_ge0).
  have -> : i{2} * block_size = (i{2}-1)*block_size + block_size by ring.
  smt().
split.
+ by move=> n' c'; rewrite mem_set; smt().
by move=> c'; rewrite mem_set; smt().
by auto => />; smt(size_eq0).
sp 5 1.
rcondt{1} 2.
+ auto => /> &hr *.
  have h0 : C.toint (C.ofintd 0) = 0 by rewrite C.ofintdK; smt(C.gt0_max_counter).
  smt().
conseq (_: _ ==> (n{1}, a{1}, c{1}, t{1}) = c{2} /\ Mem.log{1} = Mem.log{2})
       (_: (forall n' c', (n', c') \in RO.m => n' \in BNR.lenc \/ n' = pv.`1)
           /\ x0 = (pv.`1, C.ofintd 0)
           ==> romOK RO.m (pv.`1 :: BNR.lenc))
       (_: true ==> true).
+ smt().
+ smt().
+ by auto => /> *; smt(mem_set).
+ by auto.
seq 5 1 : (={Mem.log} /\ n{1} = n{2} /\ a{1} = a{2} /\ c{1} = c0{2} /\ t{1} = t{2} /\ (n{1}, a{1}, p{1}) = p{2}).
+ rndsem*{1} 0.
  rnd; skip => /> *.
  by rewrite !dmap_tag_set /=; smt().
by auto.
qed.

lemma romOK_empty (l : nonce list) : romOK empty l.
proof. by move=> n c; rewrite mem_empty. qed.

equiv decEq :
  Orc4(RO).dec ~ CPA_CCA_Orcls(EncRnd).dec :
    ={arg, Mem.log, Mem.lc} ==> ={res, Mem.log, Mem.lc}.
proof. by proc; auto. qed.

lemma L7 &m :
  Pr[MainD(G4(BNR_Adv(A)), RO).distinguish() @ &m : res] =
  Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res].
proof.
byequiv => //.
proc.
inline{1} G4(BNR_Adv(A), RO).distinguish.
inline{2} CCA_CPA_Adv(BNR_Adv(A), EncRnd).main.
inline{2} CPA_CCA_Orcls(EncRnd).init.
inline{1} BNR_Adv(A, Orc4(RO)).main.
inline{2} BNR_Adv(A, CPA_CCA_Orcls(EncRnd)).main.
inline{1} BNR(Orc4(RO)).init.
inline{2} BNR(CPA_CCA_Orcls(EncRnd)).init.
inline{1} RO.init.
inline{2} EncRnd.init.
wp.
call (_: ={Mem.log, Mem.lc, BNR.lenc, BNR.ndec} /\ romOK RO.m{1} BNR.lenc{1}).
+ proc; sp; if; 1,3: by auto.
  exists* p{1}; elim* => pv.
  wp; call (encEq pv); auto; rewrite /check_plaintext /=; smt().
+ proc; sp; if; 1,3: by auto.
  by wp; call decEq; auto.
by auto => />; smt(romOK_empty).
qed.

lemma SC1_ofpairK (p : poly * extra_block) : SplitC1.topair (SplitC1.ofpair p) = p.
proof.
case: p => x y; rewrite /SplitC1.topair /SplitC1.ofpair /=.
have hx := TPoly.bytes_of_polyP x.
have hy := Extra_block.bytes_of_extra_blockP y.
rewrite Block.block_of_bytesdK.
+ by rewrite size_cat hx hy /poly_size /block_size.
rewrite /poly_size in hx.
by rewrite (take_size_cat _ _ _ hx) (drop_size_cat _ _ _ hx)
           TPoly.bytes_of_polyKd Extra_block.bytes_of_extra_blockKd.
qed.

lemma SC2_ofpairK (p : poly_in * poly_out) : SplitC2.topair (SplitC2.ofpair p) = p.
proof.
case: p => x y; rewrite /SplitC2.topair /SplitC2.ofpair /=.
have hx := Poly_in.bytes_of_poly_inP x.
have hy := Poly_out.bytes_of_poly_outP y.
rewrite TPoly.poly_of_bytesdK.
+ by rewrite size_cat hx hy /poly_size.
by rewrite (take_size_cat _ _ _ hx) (drop_size_cat _ _ _ hx)
           Poly_in.bytes_of_poly_inKd Poly_out.bytes_of_poly_outKd.
qed.

lemma mk_rs_ofpair (p : poly * extra_block) : mk_rs (SplitC1.ofpair p) = SplitC2.topair p.`1.
proof.
case: p => x y /=; rewrite /mk_rs /SplitC1.ofpair /SplitC2.topair /=.
have hx := TPoly.bytes_of_polyP x.
have hy := Extra_block.bytes_of_extra_blockP y.
rewrite Block.block_of_bytesdK.
+ by rewrite size_cat hx hy /poly_size /block_size.
rewrite /poly_size in hx.
by rewrite (take_size_cat _ _ _ hx).
qed.

lemma mk_rs_topair (b : block) : mk_rs b = SplitC2.topair (SplitC1.topair b).`1.
proof. by rewrite -{1}(SplitC1.topairK b) mk_rs_ofpair. qed.

op setS (b : block) (s : poly_out) : block =
  SplitC1.ofpair (SplitC2.ofpair ((mk_rs b).`1, s), (SplitC1.topair b).`2).

lemma mk_rs_setS (b:block) (s:poly_out) : mk_rs (setS b s) = ((mk_rs b).`1, s).
proof. by rewrite /setS mk_rs_ofpair /= SC2_ofpairK. qed.

lemma setS_setS (b:block) (j u : poly_out) : setS (setS b j) u = setS b u.
proof. by rewrite {1}/setS mk_rs_setS /= SC1_ofpairK /setS. qed.

lemma setS_same (b:block) : setS b (mk_rs b).`2 = b.
proof.
rewrite /setS.
have -> : ((mk_rs b).`1, (mk_rs b).`2) = mk_rs b by smt().
rewrite mk_rs_topair SplitC2.topairK.
have -> : ((SplitC1.topair b).`1, (SplitC1.topair b).`2) = SplitC1.topair b by smt().
by apply SplitC1.topairK.
qed.

op Phi (q : polynomial) (bj : block * poly_out) : block * poly_out =
  (setS bj.`1 bj.`2, poly1305 (mk_rs bj.`1).`1 (mk_rs bj.`1).`2 q).

op Psi (q : polynomial) (bt : block * poly_out) : block * poly_out =
  (setS bt.`1 (bt.`2 - poly1305_eval (mk_rs bt.`1).`1 q), (mk_rs bt.`1).`2).

lemma PhiK (q:polynomial) : cancel (Phi q) (Psi q).
proof.
move=> [b j]; rewrite /Phi /Psi /= mk_rs_setS /= setS_setS /poly1305.
have -> : (mk_rs b).`2 + poly1305_eval (mk_rs b).`1 q - poly1305_eval (mk_rs b).`1 q
        = (mk_rs b).`2 by rewrite -poly_out_add_sub.
by rewrite setS_same.
qed.

lemma PsiK (q:polynomial) : cancel (Psi q) (Phi q).
proof.
move=> [b t]; rewrite /Phi /Psi /= mk_rs_setS /= setS_setS setS_same /poly1305.
by rewrite -poly_out_sub_add.
qed.

lemma dmap_Phi (q:polynomial) : dmap (dblock `*` dpoly_out) (Phi q) = dblock `*` dpoly_out.
proof.
apply eq_distr => -[x1 x2]; rewrite dmap1E.
have -> : (pred1 (x1,x2) \o Phi q) = pred1 (Psi q (x1,x2)).
+ apply fun_ext => y; rewrite /(\o) /pred1 eq_iff; split.
  + by move=> <-; rewrite PhiK.
  by move=> ->; rewrite PsiK.
rewrite /Psi /= !dprod1E.
by rewrite (Block.dblock_funi (setS x1 (x2 - poly1305_eval (mk_rs x1).`1 q)) x1)
           (Poly_out.dpoly_out_funi (mk_rs x1).`2 x2).
qed.

lemma dmap_dblock_r : dmap dblock (fun b => (mk_rs b).`1) = dpoly_in.
proof.
have -> : (fun (b:block) => (mk_rs b).`1) = (fun (p:poly_in*poly_out) => idfun p.`1) \o mk_rs.
+ by apply fun_ext.
rewrite -(dmap_comp mk_rs (fun (p:poly_in*poly_out) => idfun p.`1) dblock) dmap_dblock_mk_rs.
by rewrite dprod_marginalL dpoly_out_ll dmap_id dscalar1.
qed.

lemma mu_has_le ['a, 'b] (d : 'a distr) (P : 'a -> 'b -> bool) (l : 'b list) (bnd : real) :
  0%r <= bnd =>
  (forall x, x \in l => mu d (fun r => P r x) <= bnd) =>
  mu d (fun r => has (fun x => P r x) l) <= (size l)%r * bnd.
proof.
move=> hb; elim: l.
+ move=> _.
  rewrite (mu_eq d (fun (r:'a) => has (fun (x:'b) => P r x) []) pred0) 1:// mu0 /=.
  smt().
move=> x l ih hall.
have h1 : mu d (fun (r:'a) => P r x) <= bnd by apply hall; rewrite in_cons.
have h2 : mu d (fun (r:'a) => has (P r) l) <= (size l)%r * bnd.
+ by apply ih => y hy; apply hall; rewrite in_cons hy.
have -> : (fun (r:'a) => has (fun (y:'b) => P r y) (x::l))
        = predU (fun (r:'a) => P r x) (fun (r:'a) => has (fun (y:'b) => P r y) l).
+ by apply fun_ext => r; rewrite /predU /=.
rewrite mu_or /=.
have := ge0_mu d (predI (fun (r:'a) => P r x) (fun (r:'a) => has (P r) l)).
smt(size_ge0).
qed.

lemma test_polyE (n:nonce) (lc:ciphertext list) (r:poly_in) (s:poly_out) :
  test_poly n lc r s =
  has (fun (cph:ciphertext) => cph.`1 = n /\ cph.`4 = poly1305 r s (topol cph.`2 cph.`3)) lc.
proof.
rewrite /test_poly /=; elim: lc => //= cph lc ih.
by case: (cph.`1 = n) => hn /=; rewrite ih.
qed.

lemma pr1_poly_outE (x : poly_out) : mu1 dpoly_out x = pr1_poly_out.
proof. by rewrite /pr1_poly_out; apply dpoly_out_funi. qed.

lemma ge0_pr1_poly_out : 0%r <= pr1_poly_out.
proof. by rewrite /pr1_poly_out; apply ge0_mu. qed.

lemma bound_fresh (n:nonce) (lc : ciphertext list) :
  mu dblock (fun bl => test_poly n lc (mk_rs bl).`1 (mk_rs bl).`2)
  <= (size lc)%r * pr1_poly_out.
proof.
have -> : (fun (bl:block) => test_poly n lc (mk_rs bl).`1 (mk_rs bl).`2)
        = (fun (bl:block) => has (fun (cph:ciphertext) =>
             cph.`1 = n /\ cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3)) lc).
+ by apply fun_ext => bl; apply test_polyE.
apply (mu_has_le dblock (fun (bl:block) (cph:ciphertext) =>
         cph.`1 = n /\ cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3))
       lc pr1_poly_out ge0_pr1_poly_out).
move=> cph _ /=.
case: (cph.`1 = n) => hn /=; last first.
+ by rewrite (mu_eq dblock _ pred0) 1:// mu0 ge0_pr1_poly_out.
have -> : (fun (bl:block) => cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3))
        = pred1 cph.`4 \o (fun (bl:block) => poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3)).
+ by apply fun_ext => bl; rewrite /(\o) /pred1 eq_iff; smt().
by rewrite -dmap1E dmap_tag pr1_poly_outE.
qed.

op nlkpTestR (ce : ciphertext) (lc : ciphertext list) (n:nonce) (r:poly_in) =
  has (fun (dq:ciphertext) => dq.`1 = n /\
        dq.`4 = ce.`4 + (poly1305_eval r (topol dq.`2 dq.`3) - poly1305_eval r (topol ce.`2 ce.`3))) lc.

lemma bound_used (n:nonce) (lc : ciphertext list) (ce : ciphertext) :
  valid_topol ce.`2 ce.`3 =>
  (forall dq, dq \in lc => dq.`1 = n =>
      valid_topol dq.`2 dq.`3 /\
      (topol dq.`2 dq.`3 = topol ce.`2 ce.`3 => dq.`4 <> ce.`4)) =>
  mu dblock (fun bl => nlkpTestR ce lc n (mk_rs bl).`1) <= (size lc)%r * pr_zeropol.
proof.
move=> hce hlc.
apply (mu_has_le dblock (fun (bl:block) (dq:ciphertext) =>
         dq.`1 = n /\
         dq.`4 = ce.`4 + (poly1305_eval (mk_rs bl).`1 (topol dq.`2 dq.`3)
                          - poly1305_eval (mk_rs bl).`1 (topol ce.`2 ce.`3)))
       lc pr_zeropol ge0_pr_zeropol).
move=> dq hdq /=.
case: (dq.`1 = n) => hn /=; last first.
+ by rewrite (mu_eq dblock _ pred0) 1:// mu0 ge0_pr_zeropol.
have [hvdq hne] := hlc dq hdq hn.
case: (topol dq.`2 dq.`3 = topol ce.`2 ce.`3) => hq.
+ rewrite (mu_eq dblock _ pred0) 2:mu0 2:ge0_pr_zeropol.
  move=> bl @/pred0 /=; rewrite hq.
  by have := hne hq; smt(poly_out_add_sub').
have -> : (fun (bl:block) => dq.`4 = ce.`4 + (poly1305_eval (mk_rs bl).`1 (topol dq.`2 dq.`3)
                          - poly1305_eval (mk_rs bl).`1 (topol ce.`2 ce.`3)))
        = (fun (r:poly_in) => dq.`4 = ce.`4 + (poly1305_eval r (topol dq.`2 dq.`3)
                          - poly1305_eval r (topol ce.`2 ce.`3))) \o (fun (bl:block) => (mk_rs bl).`1).
+ by apply fun_ext.
rewrite -dmapE dmap_dblock_r.
by apply (pr_zeropol_spec ce.`2 dq.`2 ce.`3 dq.`3 ce.`4 dq.`4).
qed.

module Toy3 = {
  proc loop (k:int, b:bool) : bool = {
    var x;
    while (0 < k) { x <$ dpoly_out; b <- b || (x = witness); k <- k-1; }
    return b;
  }
  proc step (k:int, b:bool) : bool = {
    var x, r;
    r <- b;
    if (0 < k) { x <$ dpoly_out; r <@ loop(k-1, b || (x = witness)); }
    return r;
  }
}.

equiv loop_step : Toy3.loop ~ Toy3.step : ={arg} ==> ={res}.
proof.
proc; inline Toy3.loop.
sp 0 1.
case (0 < k{1}).
+ rcondt{1} 1; first by auto.
  rcondt{2} 1; first by auto.
  wp.
  while (k{1} = k0{2} /\ b{1} = b0{2}); first by auto.
  by auto.
rcondf{1} 1; first by auto.
rcondf{2} 1; first by auto.
by auto.
qed.

lemma toy2 (n:int) : 0 <= n => phoare [ Toy3.loop : k = n /\ !b ==> res ] <= (n%r * pr1_poly_out).
proof.
elim/natind: n.
+ move=> n hn hn0; proc; rcondf 1; first by auto; smt().
  hoare; first by move=> &hr _; smt(ge0_pr1_poly_out).
  by auto; smt().
move=> n hn ih _.
bypr => &hr [hk hb].
have -> : Pr[Toy3.loop(k{hr}, b{hr}) @ &hr : res] = Pr[Toy3.step(k{hr}, b{hr}) @ &hr : res].
+ by byequiv loop_step.
byphoare (_: k = n+1 /\ !b ==> res) => //.
proc.
rcondt 2; first by auto; smt().
seq 2 : (b || (x = witness)) pr1_poly_out 1%r 1%r (n%r*pr1_poly_out) (k = n+1 /\ !b).
+ by auto.
+ rnd; wp; skip => /> &hr0 hb0.
  done.
+ by conseq (_: _ ==> true).
+ by conseq (_: _ ==> true).
+ by call (ih hn); auto; smt().
by smt().
qed.

op nlkp (lg : (ciphertext,plaintext) fmap) (n : nonce) : ciphertext =
  choiceb (fun (c:ciphertext) => c \in lg /\ c.`1 = n) witness.

op nlkpTest (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
            (n : nonce) (r : poly_in) =
  nlkpTestR (nlkp lg n) lc n r.

op ftest (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
         (lenc : nonce list) (n : nonce) (bl : block) =
  if n \in lenc then nlkpTest lg lc n (mk_rs bl).`1
  else test_poly n lc (mk_rs bl).`1 (mk_rs bl).`2.

module Orc5v (RO:RO) = {
  proc enc (nap : plaintext) : ciphertext = {
    var n, a, p, c, t, bl;
    (n,a,p) <- nap;
    c  <@ Orc3(RO).cc(n,p);
    bl <@ RO.get(n, C.ofintd 0);
    t  <$ dpoly_out;
    Mem.log.[(n,a,c,t)] <- (n,a,p);
    return (n,a,c,t);
  }
  proc dec = Orc4(RO).dec
}.

module Orc5u (RO:RO) = {
  proc enc (nap : plaintext) : ciphertext = {
    var n, a, p, c, t;
    (n,a,p) <- nap;
    c  <@ Orc3(RO).cc(n,p);
    t  <$ dpoly_out;
    Mem.log.[(n,a,c,t)] <- (n,a,p);
    return (n,a,c,t);
  }
  proc dec = Orc4(RO).dec
}.

module G5endB (RO:RO) = {
  proc main () = {
    var ns, forged, i, n, bl;
    ns <- undup (List.map (fun (c:ciphertext) => c.`1) Mem.lc);
    forged <- false;
    i <- 0;
    while (i < size ns) {
      n  <- List.nth witness ns i;
      bl <@ RO.get(n, C.ofintd 0);
      forged <- forged || ftest Mem.log Mem.lc BNR.lenc n bl;
      i <- i + 1;
    }
    return forged;
  }
}.

module G5v (Ad:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b, f;
    Mem.log <- empty; Mem.lc <- [];
    b <@ Ad(Orc5v(RO)).main();
    f <@ G5endB(RO).main();
    return f;
  }
}.

module G5u (Ad:CCA_Adv, RO:RO) = {
  proc distinguish () = {
    var b, f;
    Mem.log <- empty; Mem.lc <- [];
    b <@ Ad(Orc5u(RO)).main();
    f <@ G5endB(RO).main();
    return f;
  }
}.

op Psi2 (bs : block * poly_out) : block * poly_out =
  (setS bs.`1 bs.`2, (mk_rs bs.`1).`2).

lemma Psi2K : cancel Psi2 Psi2.
proof. by move=> [b s]; rewrite /Psi2 /= mk_rs_setS /= setS_setS setS_same. qed.

lemma dmap_Psi2 : dmap (dblock `*` dpoly_out) Psi2 = dblock `*` dpoly_out.
proof.
apply eq_distr => -[x1 x2]; rewrite dmap1E.
have -> : (pred1 (x1,x2) \o Psi2) = pred1 (Psi2 (x1,x2)).
+ apply fun_ext => y; rewrite /(\o) /pred1 eq_iff; split.
  + by move=> <-; rewrite Psi2K.
  by move=> ->; rewrite Psi2K.
rewrite /Psi2 /= !dprod1E.
by rewrite (Block.dblock_funi (setS x1 x2) x1) (Poly_out.dpoly_out_funi (mk_rs x1).`2 x2).
qed.

lemma dmap_setS :
  dmap (dblock `*` dpoly_out) (fun (p:block*poly_out) => setS p.`1 p.`2) = dblock.
proof.
have -> : (fun (p:block*poly_out) => setS p.`1 p.`2)
        = (fun (p:block*poly_out) => idfun p.`1) \o Psi2.
+ by apply fun_ext => -[b s]; rewrite /(\o) /Psi2 /idfun.
rewrite -(dmap_comp Psi2 (fun (p:block*poly_out) => idfun p.`1)) dmap_Psi2.
by rewrite dprod_marginalL dpoly_out_ll dmap_id dscalar1.
qed.

lemma dlet_setS :
  dlet dblock (fun (r0 : block) => dmap dpoly_out (fun (t0 : poly_out) => setS r0 t0))
  = dblock.
proof.
have h : dmap (dblock `*` dpoly_out) (fun (q:block*poly_out) => setS q.`1 q.`2)
       = dlet dblock (fun (r0:block) => dmap dpoly_out (fun (t0:poly_out) => setS r0 t0))
  by apply (dmap_dprodE dblock dpoly_out (fun (q:block*poly_out) => setS q.`1 q.`2)).
by rewrite -h dmap_setS.
qed.

op ginv (m1 m2 : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap) (lenc : nonce list) =
  (forall x, x \in m1 <=> x \in m2) /\
  romOK m1 lenc /\
  (forall n, (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
           = (mk_rs (oget m2.[(n, C.ofintd 0)])).`1) /\
  uniq lenc /\
  (forall cph, cph \in lg => cph.`1 \in lenc) /\
  (forall n, n \in lenc =>
     (nlkp lg n) \in lg /\ (nlkp lg n).`1 = n /\
     (n, C.ofintd 0) \in m1 /\
     (mk_rs (oget m1.[(n, C.ofintd 0)])).`2
       = (nlkp lg n).`4
         - poly1305_eval (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
                         (topol (nlkp lg n).`2 (nlkp lg n).`3)).

op ginv0 (m1 m2 : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap)
         (lenc : nonce list) (nn : nonce) =
  (forall x, x \in m1 <=> x \in m2) /\
  (forall n c, (n,c) \in m1 => n \in lenc \/ n = nn) /\
  (forall n, (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
           = (mk_rs (oget m2.[(n, C.ofintd 0)])).`1) /\
  uniq lenc /\ ! (nn \in lenc) /\
  (forall cph, cph \in lg => cph.`1 \in lenc) /\
  (forall n, n \in lenc =>
     (nlkp lg n) \in lg /\ (nlkp lg n).`1 = n /\
     (n, C.ofintd 0) \in m1 /\
     (mk_rs (oget m1.[(n, C.ofintd 0)])).`2
       = (nlkp lg n).`4
         - poly1305_eval (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
                         (topol (nlkp lg n).`2 (nlkp lg n).`3)).

lemma nlkp_set_new (lg : (ciphertext,plaintext) fmap) (cph : ciphertext) (pl : plaintext) :
  (forall x, x \in lg => x.`1 <> cph.`1) =>
  nlkp lg.[cph <- pl] cph.`1 = cph.
proof.
move=> h; rewrite /nlkp.
have hex : exists (x:ciphertext), (x \in lg.[cph <- pl] /\ x.`1 = cph.`1).
+ by exists cph; rewrite mem_set.
have := choicebP (fun (c:ciphertext) => c \in lg.[cph <- pl] /\ c.`1 = cph.`1) witness _.
+ by move: hex => [x hx]; exists x.
move=> /= [h1 h2]; move: h1; rewrite mem_set; case => h1 //.
by have := h _ h1.
qed.

lemma nlkp_set_old (lg : (ciphertext,plaintext) fmap) (cph : ciphertext)
                   (pl : plaintext) (n : nonce) :
  n <> cph.`1 => nlkp lg.[cph <- pl] n = nlkp lg n.
proof.
move=> hn; rewrite /nlkp; congr; apply fun_ext => x.
by rewrite mem_set eq_iff; smt().
qed.

lemma encRepro (pv : plaintext) :
  equiv [ Orc3(RO).enc ~ Orc5v(RO).enc :
    ={arg, Mem.log, BNR.lenc} /\ arg{1} = pv /\
    ! (pv.`1 \in BNR.lenc{1}) /\ valid_topol pv.`2 pv.`3 /\
    ginv RO.m{1} RO.m{2} Mem.log{1} BNR.lenc{1}
    ==> ={res, Mem.log} /\ res{1}.`1 = pv.`1 /\
        ginv RO.m{1} RO.m{2} Mem.log{1} (pv.`1 :: BNR.lenc{1}) ].
proof.
proc; inline{1} Orc3(RO).mac; inline{1} Orc3(RO).cc; inline{2} Orc3(RO).cc; inline RO.get.
sp 5 5.
seq 1 1 : (
  ={Mem.log, BNR.lenc, p0, i} /\
  c1{1} = c0{2} /\
  n{1} = pv.`1 /\ n{2} = pv.`1 /\
  n1{1} = pv.`1 /\ n0{2} = pv.`1 /\
  a{1} = pv.`2 /\ a{2} = pv.`2 /\
  p{1} = pv.`3 /\ p{2} = pv.`3 /\
  valid_topol pv.`2 pv.`3 /\
  ! (pv.`1 \in BNR.lenc{1}) /\
  (p0{1} <> [] => size p0{1} + (i{1} - 1) * block_size <= max_cipher_size) /\
  1 <= i{1} /\
  (forall x, x \in RO.m{1} <=> x \in RO.m{2}) /\
  (forall n' c', (n', c') \in RO.m{1} =>
     n' \in BNR.lenc{1} \/
     (n' = pv.`1 /\ 1 <= C.toint c' < i{1})) /\
  (forall c', (pv.`1, c') \in RO.m{1} =>
     RO.m{1}.[(pv.`1, c')] = RO.m{2}.[(pv.`1, c')]) /\
  (forall n', (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`1 =
              (mk_rs (oget RO.m{2}.[(n', C.ofintd 0)])).`1) /\
  uniq BNR.lenc{1} /\
  (forall cph, cph \in Mem.log{1} => cph.`1 \in BNR.lenc{1}) /\
  (forall n', n' \in BNR.lenc{1} =>
     (nlkp Mem.log{1} n') \in Mem.log{1} /\
     (nlkp Mem.log{1} n').`1 = n' /\
     (n', C.ofintd 0) \in RO.m{1} /\
     (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`2 =
       (nlkp Mem.log{1} n').`4 -
       poly1305_eval
         (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`1
         (topol (nlkp Mem.log{1} n').`2 (nlkp Mem.log{1} n').`3))
).
while (
  ={Mem.log, BNR.lenc, p0, i} /\
  c1{1} = c0{2} /\
  n{1} = pv.`1 /\ n{2} = pv.`1 /\
  n1{1} = pv.`1 /\ n0{2} = pv.`1 /\
  a{1} = pv.`2 /\ a{2} = pv.`2 /\
  p{1} = pv.`3 /\ p{2} = pv.`3 /\
  valid_topol pv.`2 pv.`3 /\
  ! (pv.`1 \in BNR.lenc{1}) /\
  (p0{1} <> [] => size p0{1} + (i{1} - 1) * block_size <= max_cipher_size) /\
  1 <= i{1} /\
  (forall x, x \in RO.m{1} <=> x \in RO.m{2}) /\
  (forall n' c', (n', c') \in RO.m{1} =>
     n' \in BNR.lenc{1} \/
     (n' = pv.`1 /\ 1 <= C.toint c' < i{1})) /\
  (forall c', (pv.`1, c') \in RO.m{1} =>
     RO.m{1}.[(pv.`1, c')] = RO.m{2}.[(pv.`1, c')]) /\
  (forall n', (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`1 =
              (mk_rs (oget RO.m{2}.[(n', C.ofintd 0)])).`1) /\
  uniq BNR.lenc{1} /\
  (forall cph, cph \in Mem.log{1} => cph.`1 \in BNR.lenc{1}) /\
  (forall n', n' \in BNR.lenc{1} =>
     (nlkp Mem.log{1} n') \in Mem.log{1} /\
     (nlkp Mem.log{1} n').`1 = n' /\
     (n', C.ofintd 0) \in RO.m{1} /\
     (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`2 =
       (nlkp Mem.log{1} n').`4 -
       poly1305_eval
         (mk_rs (oget RO.m{1}.[(n', C.ofintd 0)])).`1
         (topol (nlkp Mem.log{1} n').`2 (nlkp Mem.log{1} n').`3))
).
rcondt{1} 3.
auto => />.
move=> &hr _ _ hnl hsz hi _ hkeys _ _ _ _ _ hp0 r00 _.
have hsz' := hsz hp0.
have hp0sz : 0 < size p0{m} by smt(size_eq0 size_ge0).
have hib : i{m} <= C.max_counter by
  apply (ctr_bound i{m} (size p0{m})); smt.
have htoi : C.toint (C.ofintd i{m}) = i{m} by
  rewrite C.ofintdK; smt.
apply/negP => hin.
have hk := hkeys pv.`1 (C.ofintd i{m}) hin.
rewrite htoi in hk.
smt.
rcondt{2} 3.
auto => />.
move=> &hr _ _ hn hbound hi heq hmembers _ _ _ _ _ hp0 _ _.
apply/negP => hin.
have hinm : (pv.`1, C.ofintd i{m}) \in RO.m{m} by rewrite (heq (pv.`1, C.ofintd i{m})).
case: (hmembers pv.`1 (C.ofintd i{m}) hinm) => [hbad | [_ hctr]].
+ by smt().
have hpos : 0 < size p0{m} by smt(size_eq0 size_ge0).
have himax : i{m} <= C.max_counter by
  apply (ctr_bound i{m} (size p0{m})); smt.
have hK : C.toint (C.ofintd i{m}) = i{m} by
  rewrite C.ofintdK; smt.
smt.
wp; rnd; auto => />.
move=> &1 &2 _ _ hn hbound hi heq hmembers hvals hrs _ _ hnl hp0 r0L _.
rewrite !get_set_sameE /=.
split.
+ move=> hdrop.
  have hb := hbound hp0.
  have hd : size (drop block_size p0{2}) = max 0 (size p0{2} - block_size)
    by rewrite size_drop; smt(ge0_block_size).
  have hdpos : 0 < size (drop block_size p0{2}) by smt(size_eq0 size_ge0).
  smt().
split; [smt |].
split.
move=> x1; rewrite !mem_set; split.
+ move=> [hx | hx].
- left; rewrite -(heq x1); exact hx.
- right; exact hx.
+ move=> [hx | hx].
- left; rewrite (heq x1); exact hx.
- right; exact hx.
split.
have himax : i{2} <= C.max_counter by
  apply (ctr_bound i{2} (size p0{2})); [exact hi | smt(size_eq0 size_ge0) | exact (hbound hp0)].
have hK : C.toint (C.ofintd i{2}) = i{2} by
  rewrite C.ofintdK; smt.
move=> n' c'; rewrite mem_set; move=> [hold | hnew].
+ case: (hmembers n' c' hold) => [hL | [hne hc]].
- left; exact hL.
- right; split; [exact hne | smt].
+ have hne : n' = pv.`1 by have := congr1 fst _ _ hnew.
  have hce : c' = C.ofintd i{2} by have := congr1 snd _ _ hnew.
  right; split; [exact hne |].
  rewrite hce hK; smt().
have hK0 : C.toint (C.ofintd 0) = 0 by rewrite C.ofintdK; smt(C.gt0_max_counter).
have himax2 : i{2} <= C.max_counter by
  apply (ctr_bound i{2} (size p0{2})); [exact hi | smt(size_eq0 size_ge0) | exact (hbound hp0)].
have hK2 : C.toint (C.ofintd i{2}) = i{2} by rewrite C.ofintdK; smt().
have hzz : forall (n'' : nonce),
  ((n'', C.ofintd 0) = (pv.`1, C.ofintd i{2})) = false by smt().
split.
+ by move=> c'; rewrite mem_set !get_setE /=; smt().
split.
+ by move=> n'; rewrite !get_setE hzz /=; apply hrs.
move=> n' hnn; have [h1 [h2 [h3 h4]]] := hnl n' hnn.
by rewrite mem_set !get_setE hzz /=; smt().
auto => />.
move=> &1 &2 hn _ _ hdom hrom hrs huniq hlog hnl.
split.
+ by move=> n' c' hin; left; apply (hrom n' c' hin).
by move=> c' hin; have := hrom n{2} c' hin.
sp 5 2.
rcondt{1} 2.
+ auto => /> &hr *.
  have h0 : C.toint (C.ofintd 0) = 0 by rewrite C.ofintdK; smt(C.gt0_max_counter).
  smt().
rcondt{2} 2.
+ auto => /> *.
  have h0 : C.toint (C.ofintd 0) = 0 by rewrite C.ofintdK; smt(C.gt0_max_counter).
  smt().
transitivity{1}
  { r0 <$ dblock;
    t <$ dpoly_out;
    r1 <- setS r0 t;
    RO.m <- RO.m.[x0 <- r1];
    b <- oget RO.m.[x0];
    (r, s) <- mk_rs b;
    t <- poly1305 r s (topol a0 c0);
    Mem.log.[(n, a, c, t)] <- (n, a, p); }
  (={RO.m, Mem.log, BNR.lenc, x0, n, a, c, p, a0, c0}
     ==> ={RO.m, Mem.log, BNR.lenc, t, n, a, c})
  (x0{1} = (pv.`1, C.ofintd 0) /\ x0{2} = (pv.`1, C.ofintd 0) /\
   n{1} = pv.`1 /\ n{2} = pv.`1 /\ a{1} = pv.`2 /\ a{2} = pv.`2 /\
   a0{1} = pv.`2 /\ c0{1} = c{1} /\ c{1} = c{2} /\ p{1} = pv.`3 /\ p{2} = pv.`3 /\
   Mem.log{1} = Mem.log{2} /\ BNR.lenc{1} = BNR.lenc{2} /\
   ginv0 RO.m{1} RO.m{2} Mem.log{1} BNR.lenc{1} pv.`1
     ==> ((n{1}, a{1}, c{1}, t{1}) = (n{2}, a{2}, c{2}, t{2}) /\ Mem.log{1} = Mem.log{2}) /\
         (n{1}, a{1}, c{1}, t{1}).`1 = pv.`1 /\
         ginv RO.m{1} RO.m{2} Mem.log{1} (pv.`1 :: BNR.lenc{1})).
+ move=> &1 &2 hp.
  exists BNR.lenc{1} RO.m{1} Mem.log{1} a{1} a0{1} c{1} c0{1} n{1} p{1} x0{1} => /=.
  rewrite /ginv0; smt().
+ move=> &1 &m &2 [h1 [h2 [h3 [h4 [h5 [h6 h7]]]]]] hq.
  by rewrite h1 h2 h3 h4 h5 h6 h7.
+ seq 1 3 : (={RO.m, Mem.log, BNR.lenc, x0, n, a, c, p, a0, c0, r1}).
  + rndsem*{2} 0.
    auto => *; rewrite dlet_setS //.
  by auto.
swap{2} 4 -2.
wp.
rnd (fun (u:poly_out) => u + poly1305_eval (mk_rs r0{1}).`1 (topol a0{1} c0{1}))
    (fun (v:poly_out) => v - poly1305_eval (mk_rs r0{1}).`1 (topol a0{1} c0{1})).
rnd.
skip => />.
move=> &1 &2 hdom hrom hrs huniq hnn hlog hnl r0L hr0.
split; first by move=> tR _; apply poly_out_sub_add.
move=> _ tL htL.
split; first by apply poly_out_add_sub.
move=> _.
have hget : oget RO.m{1}.[(pv.`1, C.ofintd 0) <- setS r0L tL].[(pv.`1, C.ofintd 0)]
          = setS r0L tL by rewrite get_set_sameE.
rewrite hget mk_rs_setS /= /poly1305 /=.
split.
+ move=> x1; rewrite !mem_set; split.
  + by move=> [h|h]; [left; rewrite -(hdom x1) | right].
  by move=> [h|h]; [left; rewrite (hdom x1) | right].
split; first by rewrite /romOK => n2 c2; rewrite mem_set /=; smt().
split.
+ move=> n2; case: (n2 = pv.`1) => hn2.
  + by rewrite hn2 !get_set_sameE /= mk_rs_setS.
  by rewrite !get_set_neqE 1,2:/#; apply hrs.
split; first by move=> cph; rewrite mem_set; smt().
have hnew : forall x, x \in Mem.log{2} =>
     x.`1 <> (pv.`1, pv.`2, c{2},
              tL + poly1305_eval (mk_rs r0L).`1 (topol pv.`2 c{2})).`1.
+ by move=> x hx /=; have := hlog x hx; smt().
have hnk := nlkp_set_new Mem.log{2}
     (pv.`1, pv.`2, c{2}, tL + poly1305_eval (mk_rs r0L).`1 (topol pv.`2 c{2}))
     (pv.`1, pv.`2, pv.`3) hnew.
move: hnk => /= hnk.
move=> n2 hn2.
case: (n2 = pv.`1) => he.
+ rewrite he hnk /= !mem_set /= get_set_sameE /= mk_rs_setS /=.
  by apply poly_out_add_sub.
have hin : n2 \in BNR.lenc{2} by smt().
have hold : nlkp Mem.log{2}.[(pv.`1, pv.`2, c{2},
              tL + poly1305_eval (mk_rs r0L).`1 (topol pv.`2 c{2}))
              <- (pv.`1, pv.`2, pv.`3)] n2
          = nlkp Mem.log{2} n2.
+ by apply (nlkp_set_old Mem.log{2} _ _ n2) => /=; exact he.
have hne2 : RO.m{1}.[(pv.`1, C.ofintd 0) <- setS r0L tL].[(n2, C.ofintd 0)]
          = RO.m{1}.[(n2, C.ofintd 0)] by rewrite get_set_neqE; smt().
have [g1 [g2 [g3 g4]]] := hnl n2 hin.
rewrite hold hne2 g2 g4 /= !mem_set.
smt().
qed.

lemma has_filter_eq ['a] (p : 'a -> bool) (q : 'a -> bool) (l : 'a list) :
  has (fun x => q x /\ p x) l = has p (filter q l).
proof. by elim: l => //= x l ih; case: (q x) => hq /=; rewrite ih. qed.

lemma test_polyF (n:nonce) (lc:ciphertext list) (r:poly_in) (s:poly_out) :
  test_poly n lc r s =
  has (fun (cph:ciphertext) => cph.`4 = poly1305 r s (topol cph.`2 cph.`3))
      (filter (fun (c:ciphertext) => c.`1 = n) lc).
proof. by rewrite test_polyE -has_filter_eq. qed.

lemma bound_freshF (n:nonce) (lc : ciphertext list) :
  mu dblock (fun bl => test_poly n lc (mk_rs bl).`1 (mk_rs bl).`2)
  <= (size (filter (fun (c:ciphertext) => c.`1 = n) lc))%r * pr1_poly_out.
proof.
have -> : (fun (bl:block) => test_poly n lc (mk_rs bl).`1 (mk_rs bl).`2)
        = (fun (bl:block) => has (fun (cph:ciphertext) =>
             cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3))
             (filter (fun (c:ciphertext) => c.`1 = n) lc)).
+ by apply fun_ext => bl; apply test_polyF.
apply (mu_has_le dblock (fun (bl:block) (cph:ciphertext) =>
         cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3))
       (filter (fun (c:ciphertext) => c.`1 = n) lc) pr1_poly_out ge0_pr1_poly_out).
move=> cph _ /=.
have -> : (fun (bl:block) => cph.`4 = poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3))
        = pred1 cph.`4 \o (fun (bl:block) => poly1305 (mk_rs bl).`1 (mk_rs bl).`2 (topol cph.`2 cph.`3)).
+ by apply fun_ext => bl; rewrite /(\o) /pred1 eq_iff; smt().
by rewrite -dmap1E dmap_tag pr1_poly_outE.
qed.

lemma nlkpTestRF (ce : ciphertext) (lc : ciphertext list) (n:nonce) (r:poly_in) :
  nlkpTestR ce lc n r =
  has (fun (dq:ciphertext) =>
         dq.`4 = ce.`4 + (poly1305_eval r (topol dq.`2 dq.`3)
                          - poly1305_eval r (topol ce.`2 ce.`3)))
      (filter (fun (c:ciphertext) => c.`1 = n) lc).
proof. by rewrite /nlkpTestR -has_filter_eq. qed.

lemma bound_usedF (n:nonce) (lc : ciphertext list) (ce : ciphertext) :
  valid_topol ce.`2 ce.`3 =>
  (forall dq, dq \in lc => dq.`1 = n =>
      valid_topol dq.`2 dq.`3 /\
      (topol dq.`2 dq.`3 = topol ce.`2 ce.`3 => dq.`4 <> ce.`4)) =>
  mu dblock (fun bl => nlkpTestR ce lc n (mk_rs bl).`1)
  <= (size (filter (fun (c:ciphertext) => c.`1 = n) lc))%r * pr_zeropol.
proof.
move=> hce hlc.
have -> : (fun (bl:block) => nlkpTestR ce lc n (mk_rs bl).`1)
        = (fun (bl:block) => has (fun (dq:ciphertext) =>
             dq.`4 = ce.`4 + (poly1305_eval (mk_rs bl).`1 (topol dq.`2 dq.`3)
                              - poly1305_eval (mk_rs bl).`1 (topol ce.`2 ce.`3)))
             (filter (fun (c:ciphertext) => c.`1 = n) lc)).
+ by apply fun_ext => bl; apply nlkpTestRF.
apply (mu_has_le dblock (fun (bl:block) (dq:ciphertext) =>
         dq.`4 = ce.`4 + (poly1305_eval (mk_rs bl).`1 (topol dq.`2 dq.`3)
                          - poly1305_eval (mk_rs bl).`1 (topol ce.`2 ce.`3)))
       (filter (fun (c:ciphertext) => c.`1 = n) lc) pr_zeropol ge0_pr_zeropol).
move=> dq hdq /=.
have hdq' : dq \in lc by move: hdq; rewrite mem_filter.
have hn : dq.`1 = n by move: hdq; rewrite mem_filter /=.
have [hvdq hne] := hlc dq hdq' hn.
case: (topol dq.`2 dq.`3 = topol ce.`2 ce.`3) => hq.
+ rewrite (mu_eq dblock _ pred0) 2:mu0 2:ge0_pr_zeropol.
  move=> bl @/pred0 /=; rewrite hq.
  by have := hne hq; smt(poly_out_add_sub').
have -> : (fun (bl:block) => dq.`4 = ce.`4 + (poly1305_eval (mk_rs bl).`1 (topol dq.`2 dq.`3)
                          - poly1305_eval (mk_rs bl).`1 (topol ce.`2 ce.`3)))
        = (fun (r:poly_in) => dq.`4 = ce.`4 + (poly1305_eval r (topol dq.`2 dq.`3)
                          - poly1305_eval r (topol ce.`2 ce.`3))) \o (fun (bl:block) => (mk_rs bl).`1).
+ by apply fun_ext.
rewrite -dmapE dmap_dblock_r.
by apply (pr_zeropol_spec ce.`2 dq.`2 ce.`3 dq.`3 ce.`4 dq.`4).
qed.

op condN (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
         (lenc : nonce list) (n:nonce) =
  n \in lenc =>
    valid_topol (nlkp lg n).`2 (nlkp lg n).`3 /\
    (forall dq, dq \in lc => dq.`1 = n =>
       valid_topol dq.`2 dq.`3 /\
       (topol dq.`2 dq.`3 = topol (nlkp lg n).`2 (nlkp lg n).`3 =>
        dq.`4 <> (nlkp lg n).`4)).

lemma ftest_bound (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
                  (lenc : nonce list) (n:nonce) :
  condN lg lc lenc n =>
  mu dblock (fun bl => ftest lg lc lenc n bl)
  <= (size (filter (fun (c:ciphertext) => c.`1 = n) lc))%r
     * (maxr pr_zeropol pr1_poly_out).
proof.
rewrite /ftest /condN; case: (n \in lenc) => hn /=.
+ move=> h; have [h1 h2] := h.
  apply (RealOrder.ler_trans
          ((size (filter (fun (c:ciphertext) => c.`1 = n) lc))%r * pr_zeropol)).
  + by rewrite /nlkpTest; apply bound_usedF.
  smt(size_ge0 ge0_pr_zeropol ge0_pr1_poly_out).
apply (RealOrder.ler_trans
        ((size (filter (fun (c:ciphertext) => c.`1 = n) lc))%r * pr1_poly_out)).
+ by apply bound_freshF.
smt(size_ge0 ge0_pr_zeropol ge0_pr1_poly_out).
qed.

lemma size_filter_cons (n:nonce) (l : nonce list) (lc : ciphertext list) :
  ! (n \in l) =>
  size (filter (fun (c:ciphertext) => c.`1 \in n :: l) lc)
  = size (filter (fun (c:ciphertext) => c.`1 = n) lc)
    + size (filter (fun (c:ciphertext) => c.`1 \in l) lc).
proof.
move=> hn; elim: lc => //= c lc ih.
by case: (c.`1 = n) => h1; case: (c.`1 \in l) => h2; smt().
qed.

module Lp (RO:RO) = {
  proc loop (ns : nonce list, forged : bool) : bool = {
    var n, bl;
    while (ns <> []) {
      n  <- head witness ns;
      ns <- behead ns;
      bl <@ RO.get(n, C.ofintd 0);
      forged <- forged || ftest Mem.log Mem.lc BNR.lenc n bl;
    }
    return forged;
  }
  proc step (ns : nonce list, forged : bool) : bool = {
    var n, bl, r0;
    r0 <- forged;
    if (ns <> []) {
      n  <- head witness ns;
      bl <@ RO.get(n, C.ofintd 0);
      r0 <@ loop(behead ns, forged || ftest Mem.log Mem.lc BNR.lenc n bl);
    }
    return r0;
  }
}.

equiv RO_get_self : RO.get ~ RO.get : ={arg, RO.m} ==> ={res, RO.m}.
proof. by proc; auto. qed.

equiv Lp_loop_step : Lp(RO).loop ~ Lp(RO).step :
  ={arg, RO.m, Mem.log, Mem.lc, BNR.lenc} ==> ={res}.
proof.
proc; inline Lp(RO).loop.
sp 0 1.
case (ns{1} <> []).
+ rcondt{1} 1; first by auto.
  rcondt{2} 1; first by auto.
  wp.
  while (={RO.m, Mem.log, Mem.lc, BNR.lenc} /\ ns{1} = ns0{2} /\ forged{1} = forged0{2}).
  + by wp; call RO_get_self; auto.
  by wp; call RO_get_self; auto.
rcondf{1} 1; first by auto.
rcondf{2} 1; first by auto.
by auto.
qed.

lemma Lp_bound (l : nonce list) :
  forall (lcv : ciphertext list) (lgv : (ciphertext,plaintext) fmap) (lencv : nonce list),
  uniq l =>
  (forall nn, nn \in l => condN lgv lcv lencv nn) =>
  phoare [ Lp(RO).loop :
     ns = l /\ !forged /\ Mem.lc = lcv /\ Mem.log = lgv /\ BNR.lenc = lencv /\
     (forall nn, nn \in l => ! ((nn, C.ofintd 0) \in RO.m))
     ==> res ]
  <= ((size (filter (fun (c:ciphertext) => c.`1 \in l) lcv))%r * (maxr pr_zeropol pr1_poly_out)).
proof.
elim: l.
+ move=> lcv lgv lencv _ _; proc; rcondf 1; first by auto.
  hoare; first by move=> &hr _; smt(size_ge0 ge0_pr_zeropol ge0_pr1_poly_out).
  by auto.
move=> nn l ih lcv lgv lencv huniq hcond.
bypr => &hr hpre.
have -> : Pr[Lp(RO).loop(ns{hr}, forged{hr}) @ &hr : res]
        = Pr[Lp(RO).step(ns{hr}, forged{hr}) @ &hr : res].
+ by byequiv Lp_loop_step.
byphoare (_: ns = nn::l /\ !forged /\ Mem.lc = lcv /\ Mem.log = lgv /\ BNR.lenc = lencv /\
             (forall n', n' \in nn::l => ! ((n', C.ofintd 0) \in RO.m)) ==> res) => //.
proc.
rcondt 2; first by auto.
seq 3 : (forged \/ ftest Mem.log Mem.lc BNR.lenc n bl)
        ((size (filter (fun (c:ciphertext) => c.`1 = nn) lcv))%r * (maxr pr_zeropol pr1_poly_out))
        1%r
        1%r
        ((size (filter (fun (c:ciphertext) => c.`1 \in l) lcv))%r * (maxr pr_zeropol pr1_poly_out))
        (ns = nn::l /\ n = nn /\ !forged /\ r0 = forged /\
         Mem.lc = lcv /\ Mem.log = lgv /\ BNR.lenc = lencv /\
         (forall n', n' \in l => ! ((n', C.ofintd 0) \in RO.m))).
+ inline RO.get; auto => /> *; smt(mem_set).
+ inline RO.get.
  rcondt 5; first by auto; smt().
  wp; rnd; auto => /> *.
  rewrite (mu_eq dblock _ (fun (x0:block) => ftest lgv lcv lencv nn x0)).
  + by move=> z; rewrite get_set_sameE.
  by apply ftest_bound; apply hcond; rewrite in_cons.
+ by conseq (_: _ ==> true).
+ by conseq (_: _ ==> true).
+ call (ih lcv lgv lencv _ _).
  + by smt().
  + by move=> n' hn'; apply hcond; smt().
  by auto; smt().
have hsz : size (filter (fun (c:ciphertext) => c.`1 \in nn :: l) lcv)
         = size (filter (fun (c:ciphertext) => c.`1 = nn) lcv)
         + size (filter (fun (c:ciphertext) => c.`1 \in l) lcv).
+ by apply size_filter_cons; smt().
move=> &hr0 _; rewrite hsz fromintD.
smt().
qed.

equiv G5endB_Lp : G5endB(RO).main ~ Lp(RO).loop :
  ={RO.m, Mem.log, Mem.lc, BNR.lenc} /\
  arg{2} = (undup (map (fun (c:ciphertext) => c.`1) Mem.lc{2}), false)
  ==> ={res}.
proof.
proc; sp 3 0.
while (={RO.m, Mem.log, Mem.lc, BNR.lenc} /\ forged{1} = forged{2} /\
       ns{2} = drop i{1} ns{1} /\ 0 <= i{1} <= size ns{1}).
+ wp; call RO_get_self; auto => /> *.
  smt(drop_nth size_drop size_ge0 size_eq0).
auto => /> *; smt(drop0 size_ge0 size_eq0 drop_oversize).
qed.

lemma size_take_xor (m : bytes) (z : Block.block) :
  size (take_xor m z) = min (size m) block_size.
proof.
rewrite /take_xor size_take 1:size_ge0 Block.bytes_of_blockP.
smt(size_ge0 gt0_block_size).
qed.

lemma size_gen_CTR (f : key -> nonce -> C.counter -> block) k n i (p : bytes) :
  size (gen_CTR_encrypt_bytes take_xor f k n i p) = size p.
proof.
have : forall j, 0 <= j => forall (q:bytes) c, j = size q =>
   size (gen_CTR_encrypt_bytes take_xor f k n c q) = size q;
  2: by move=> /(_ (size p)) -> //; apply size_ge0.
elim/sintind => j hj hrec q c ->>.
case: (q = []) => [->>|hne]; first by rewrite gen_CTR_nil.
rewrite (gen_CTR_cons f k n c q) size_cat size_take_xor.
rewrite (hrec (size (drop block_size q))) 2://; 1: smt(size_drop size_ge0 gt0_block_size size_eq0).
smt(size_drop size_ge0 gt0_block_size size_eq0).
qed.

op inv0 (m : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
        (lenc : nonce list) (nd : int) =
  (forall n, ! ((n, C.ofintd 0) \in m)) /\
  size lc <= nd /\ nd <= qdec /\
  uniq lenc /\
  (forall dq, dq \in lc => valid_topol dq.`2 dq.`3) /\
  (forall cph, cph \in lg => cph.`1 \in lenc /\ valid_topol cph.`2 cph.`3) /\
  (forall n, n \in lenc => (nlkp lg n) \in lg /\ (nlkp lg n).`1 = n).

op noBad1 (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list) =
  forall dq, dq \in lc => ! (dq \in lg).

lemma condN_of (m : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap)
               (lc : ciphertext list) (lenc : nonce list) (nd : int) (n : nonce) :
  inv0 m lg lc lenc nd => noBad1 lg lc => condN lg lc lenc n.
proof.
rewrite /inv0 /noBad1 /condN => -[h1 [h2 [h3 [h4 [h5 [h6 h7]]]]]] hnb hn.
have [hin hn1] := h7 n hn.
have [_ hv] := h6 (nlkp lg n) hin.
split; first by apply hv.
move=> dq hdq hdqn; split; first by apply h5.
move=> hq.
have hv2 := h5 dq hdq.
have [ha hc] := topol_inj dq.`2 dq.`3 (nlkp lg n).`2 (nlkp lg n).`3 hv2 hv hq.
have := hnb dq hdq.
smt().
qed.

lemma cc_inv (nn : nonce) (pp : bytes) :
  hoare [ Orc3(RO).cc :
    arg = (nn,pp) /\ size pp <= max_cipher_size /\ (forall n, ! ((n, C.ofintd 0) \in RO.m))
    ==> size res = size pp /\ (forall n, ! ((n, C.ofintd 0) \in RO.m)) ].
proof.
proc; inline RO.get.
while (size c + size p = size pp /\ 1 <= i /\
       (p <> [] => size p + (i-1)*block_size <= max_cipher_size) /\
       (forall n, ! ((n, C.ofintd 0) \in RO.m)) /\ n = nn).
+ auto => /> &hr h1 h2 h3 h4 hne r _.
  have hpos : 0 < size p{hr} by smt(size_ge0 size_eq0).
  have himax : i{hr} <= C.max_counter by apply (ctr_bound i{hr} (size p{hr})); smt().
  have hoi : C.toint (C.ofintd i{hr}) = i{hr} by rewrite C.ofintdK; smt().
  have h0 : C.toint (C.ofintd 0) = 0 by rewrite C.ofintdK; smt(C.gt0_max_counter).
  have hbs0 : 0 <= block_size by smt(gt0_block_size).
  have hd := size_drop block_size p{hr} hbs0.
  have hring : i{hr} * block_size = (i{hr}-1)*block_size + block_size by ring.
  split.
  + move=> _; rewrite size_cat size_take 1:size_ge0 Block.bytes_of_blockP.
    smt(mem_set gt0_block_size size_eq0 size_ge0).
  move=> _; rewrite size_cat size_take 1:size_ge0 Block.bytes_of_blockP.
  smt(gt0_block_size size_eq0 size_ge0).
auto => /> *; smt(size_ge0 size_eq0).
qed.

lemma Orc5u_enc_inv (pv : plaintext) :
  hoare [ Orc5u(RO).enc :
    arg = pv /\ ! (pv.`1 \in BNR.lenc) /\ valid_topol pv.`2 pv.`3 /\
    inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec
    ==> inv0 RO.m Mem.log Mem.lc (pv.`1 :: BNR.lenc) BNR.ndec /\ res.`1 = pv.`1 ].
proof.
proc.
sp 1.
seq 1 : (n = pv.`1 /\ a = pv.`2 /\ p = pv.`3 /\ size c = size pv.`3 /\
         ! (pv.`1 \in BNR.lenc) /\ valid_topol pv.`2 pv.`3 /\
         (forall n', ! ((n', C.ofintd 0) \in RO.m)) /\
         size Mem.lc <= BNR.ndec /\ BNR.ndec <= qdec /\ uniq BNR.lenc /\
         (forall dq, dq \in Mem.lc => valid_topol dq.`2 dq.`3) /\
         (forall cph, cph \in Mem.log => cph.`1 \in BNR.lenc /\ valid_topol cph.`2 cph.`3) /\
         (forall n0, n0 \in BNR.lenc =>
            (nlkp Mem.log n0) \in Mem.log /\ (nlkp Mem.log n0).`1 = n0)).
+ call (cc_inv pv.`1 pv.`3).
  by auto => />; rewrite /inv0; smt().
auto => /> &hr h1 h2 h3 h4 h5 h6 h7 h8 h9 h10 h11 t _.
pose CE := (pv.`1, pv.`2, c{hr}, t).
pose PL := (pv.`1, pv.`2, pv.`3).
have hlog : forall cph, cph \in Mem.log{hr}.[CE <- PL] =>
              (cph.`1 = pv.`1 \/ cph.`1 \in BNR.lenc{hr}) /\ valid_topol cph.`2 cph.`3.
+ move=> cph; rewrite mem_set; case => hcph.
  + by have [hc1 hc2] := h10 cph hcph; smt().
  by rewrite hcph /CE /=; smt().
have hnl : forall n0, (n0 = pv.`1 \/ n0 \in BNR.lenc{hr}) =>
             (nlkp Mem.log{hr}.[CE <- PL] n0 \in Mem.log{hr}.[CE <- PL]) /\
             (nlkp Mem.log{hr}.[CE <- PL] n0).`1 = n0.
+ move=> n0; case => hn0.
  + have -> : n0 = CE.`1 by rewrite hn0 /CE.
    rewrite (nlkp_set_new Mem.log{hr} CE PL).
    + by move=> x hx; have [hx1 _] := h10 x hx; rewrite /CE /=; smt().
    by rewrite mem_set /CE.
  have hne : n0 <> CE.`1 by rewrite /CE /=; smt().
  rewrite (nlkp_set_old Mem.log{hr} CE PL n0 hne).
  by have [hh1 hh2] := h11 n0 hn0; rewrite mem_set hh1.
rewrite /inv0 /=.
smt().
qed.

lemma Orc5u_dec_inv (cphv : ciphertext) :
  hoare [ Orc5u(RO).dec :
    arg = cphv /\ valid_topol cphv.`2 cphv.`3 /\
    inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec /\ BNR.ndec < qdec
    ==> inv0 RO.m Mem.log Mem.lc BNR.lenc (BNR.ndec + 1) ].
proof. by proc; auto => />; rewrite /inv0; smt(size_ge0). qed.

lemma BNR_enc_inv :
  hoare [ BNR(Orc5u(RO)).enc : inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec
          ==> inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec ].
proof.
proc; sp; if; last by auto.
wp; exists* p; elim* => pv.
call (Orc5u_enc_inv pv).
by auto => />; smt().
qed.

lemma BNR_dec_inv :
  hoare [ BNR(Orc5u(RO)).dec : inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec
          ==> inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec ].
proof.
proc; sp; if; last by auto.
wp; exists* c; elim* => cv.
call (Orc5u_dec_inv cv).
by auto => />; smt().
qed.

lemma size_filter_all (lcv : ciphertext list) :
  size (filter (fun (c:ciphertext) =>
     c.`1 \in undup (map (fun (c0:ciphertext) => c0.`1) lcv)) lcv) = size lcv.
proof.
have : forall (l : ciphertext list),
   (forall c, c \in l => c.`1 \in undup (map (fun (c0:ciphertext) => c0.`1) lcv)) =>
   size (filter (fun (c:ciphertext) =>
      c.`1 \in undup (map (fun (c0:ciphertext) => c0.`1) lcv)) l) = size l.
+ by elim => //= c l ih h; rewrite h //= ih // => c' hc'; apply h; rewrite hc'.
by apply; move=> c hc; rewrite mem_undup; apply/mapP; exists c.
qed.

lemma G5endB_bound (lcv : ciphertext list) (lgv : (ciphertext,plaintext) fmap)
                   (lencv : nonce list) :
  phoare [ G5endB(RO).main :
     Mem.lc = lcv /\ Mem.log = lgv /\ BNR.lenc = lencv /\
     (forall nn, condN lgv lcv lencv nn) /\
     (forall n, ! ((n, C.ofintd 0) \in RO.m))
     ==> res ]
  <= ((size lcv)%r * (maxr pr_zeropol pr1_poly_out)).
proof.
have hu : uniq (undup (map (fun (c0:ciphertext) => c0.`1) lcv)) by apply undup_uniq.
rewrite -size_filter_all.
bypr => &hr hpre.
have hcond : forall nn, condN lgv lcv lencv nn by smt().
have hc2 : forall nn, nn \in undup (map (fun (c0:ciphertext) => c0.`1) lcv) =>
             condN lgv lcv lencv nn by move=> nn _; apply hcond.
have hph := Lp_bound (undup (map (fun (c0:ciphertext) => c0.`1) lcv)) lcv lgv lencv hu hc2.
have -> : Pr[G5endB(RO).main() @ &hr : res]
        = Pr[Lp(RO).loop(undup (map (fun (c0:ciphertext) => c0.`1) lcv), false) @ &hr : res].
+ by byequiv G5endB_Lp => //; smt().
by byphoare hph => //; smt().
qed.

lemma G5endB_noBad1 (b : bool) :
  hoare [ G5endB(RO).main : noBad1 Mem.log Mem.lc = b ==> noBad1 Mem.log Mem.lc = b ].
proof. proc; while (noBad1 Mem.log Mem.lc = b); [ by inline RO.get; auto | by auto ]. qed.

lemma G5endB_boundQ (lcv : ciphertext list) (lgv : (ciphertext,plaintext) fmap)
                    (lencv : nonce list) :
  phoare [ G5endB(RO).main :
     Mem.lc = lcv /\ Mem.log = lgv /\ BNR.lenc = lencv /\ size lcv <= qdec /\
     noBad1 lgv lcv /\
     (forall nn, condN lgv lcv lencv nn) /\
     (forall n, ! ((n, C.ofintd 0) \in RO.m))
     ==> res /\ noBad1 Mem.log Mem.lc ]
  <= (qdec%r * (maxr pr_zeropol pr1_poly_out)).
proof.
conseq (G5endB_bound lcv lgv lencv) (G5endB_noBad1 true).
+ smt().
+ smt().
move=> &hr hp.
have h0 : 0%r <= maxr pr_zeropol pr1_poly_out by smt(ge0_pr_zeropol ge0_pr1_poly_out).
have hs : (size lcv)%r <= qdec%r by smt().
smt(RealOrder.ler_wpmul2r).
qed.

lemma L8c_main &m :
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : res /\ noBad1 Mem.log Mem.lc]
  <= qdec%r * (maxr pr_zeropol pr1_poly_out).
proof.
byphoare (_: true ==> res /\ noBad1 Mem.log Mem.lc) => //.
proc.
inline G5u(BNR_Adv(A), RO).distinguish.
inline BNR_Adv(A, Orc5u(RO)).main.
inline BNR(Orc5u(RO)).init.
inline RO.init.
seq 8 : (noBad1 Mem.log Mem.lc) 1%r (qdec%r * (maxr pr_zeropol pr1_poly_out)) 1%r 0%r
        (inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec).
+ wp; call (_: inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec).
  + by apply BNR_enc_inv.
  + by apply BNR_dec_inv.
  by auto => />; rewrite /inv0; smt(mem_empty ge0_qdec).
+ by conseq (_: _ ==> true).
+ wp.
  exists* Mem.lc; elim* => lcv.
  exists* Mem.log; elim* => lgv.
  exists* BNR.lenc; elim* => lencv.
  call (G5endB_boundQ lcv lgv lencv).
  auto => /> &hr h1 h2 h3 h4 h5 h6 h7 h8.
  split; first smt().
  move=> nn; apply (condN_of RO.m{hr} lgv lcv lencv BNR.ndec{hr} nn).
  + by rewrite /inv0.
  by apply h8.
+ hoare.
  by wp; call (G5endB_noBad1 false); auto => />; smt().
smt().
qed.

op ginvL (m1 m2 : OpCCRO.globS) (lg : (ciphertext,plaintext) fmap) (lenc : nonce list) =
  (forall x, x \in m1 <=> x \in m2) /\
  (forall n, (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
           = (mk_rs (oget m2.[(n, C.ofintd 0)])).`1) /\
  (forall n, ! (n \in lenc) => m1.[(n, C.ofintd 0)] = m2.[(n, C.ofintd 0)]) /\
  (forall n, n \in lenc =>
     (nlkp lg n) \in lg /\ (nlkp lg n).`1 = n /\
     (n, C.ofintd 0) \in m1 /\
     (mk_rs (oget m1.[(n, C.ofintd 0)])).`2
       = (nlkp lg n).`4
         - poly1305_eval (mk_rs (oget m1.[(n, C.ofintd 0)])).`1
                         (topol (nlkp lg n).`2 (nlkp lg n).`3)).

lemma ginv_ginvL (m1 m2 : OpCCRO.globS) lg lenc :
  ginv m1 m2 lg lenc => ginvL m1 m2 lg lenc.
proof. rewrite /ginv /ginvL /romOK; smt(domE). qed.

lemma ftest_test_poly (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list)
                      (lenc : nonce list) (n : nonce) (b1 b2 : block) :
  (n \in lenc =>
     (mk_rs b1).`1 = (mk_rs b2).`1 /\
     (mk_rs b1).`2 = (nlkp lg n).`4
       - poly1305_eval (mk_rs b1).`1 (topol (nlkp lg n).`2 (nlkp lg n).`3)) =>
  (! (n \in lenc) => b1 = b2) =>
  test_poly n lc (mk_rs b1).`1 (mk_rs b1).`2 = ftest lg lc lenc n b2.
proof.
rewrite /ftest; case: (n \in lenc) => hn /=.
+ move=> h; have [h3 h4] := h.
  rewrite /nlkpTest /nlkpTestR test_polyE eq_iff.
  apply eq_in_has => dq _ /=.
  rewrite h4 -h3 /poly1305.
  smt(poly_out_swap).
by move=> ->.
qed.

equiv G5end_G5endB : G5end(RO).main ~ G5endB(RO).main :
  ={Mem.log, Mem.lc, BNR.lenc} /\ ginvL RO.m{1} RO.m{2} Mem.log{1} BNR.lenc{1}
  ==> ={res}.
proof.
proc.
while (={Mem.log, Mem.lc, BNR.lenc, forged, i, ns} /\
       ginvL RO.m{1} RO.m{2} Mem.log{1} BNR.lenc{1}).
+ inline RO.get; sp 2 2.
  seq 1 1 : (#pre /\ r0{1} = r{2}); first by auto.
  wp; skip; rewrite /ginvL /=.
  smt(ftest_test_poly mem_set get_set_sameE get_setE domE).
by auto.
qed.

equiv dec45 : Orc4(RO).dec ~ Orc5v(RO).dec :
  ={arg, Mem.log, Mem.lc} ==> ={res, Mem.log, Mem.lc}.
proof. by proc; auto. qed.

lemma L8a &m :
  Pr[MainD(G5(BNR_Adv(A)), RO).distinguish() @ &m : res] =
  Pr[MainD(G5v(BNR_Adv(A)), RO).distinguish() @ &m : res].
proof.
byequiv => //.
proc.
seq 1 1 : (={glob A, RO.m} /\ RO.m{1} = empty); first by inline*; auto.
inline{1} G5(BNR_Adv(A), RO).distinguish.
inline{2} G5v(BNR_Adv(A), RO).distinguish.
inline{1} G4(BNR_Adv(A), RO).distinguish.
inline{1} BNR_Adv(A, Orc4(RO)).main.
inline{2} BNR_Adv(A, Orc5v(RO)).main.
inline{1} BNR(Orc4(RO)).init.
inline{2} BNR(Orc5v(RO)).init.
wp; call G5end_G5endB.
wp; call (_: ={Mem.log, Mem.lc, BNR.lenc, BNR.ndec} /\
             ginv RO.m{1} RO.m{2} Mem.log{1} BNR.lenc{1}).
+ proc; sp; if; 1,3: by auto.
  exists* p{1}; elim* => pv.
  wp; call (encRepro pv); auto; rewrite /check_plaintext /=; smt().
+ proc; sp; if; 1,3: by auto.
  by wp; call dec45; auto.
by auto => /> *; rewrite /ginv /romOK; smt(mem_empty ginv_ginvL).
qed.

equiv cc_self : Orc3(FinRO).cc ~ Orc3(FinRO).cc : ={arg, RO.m} ==> ={res, RO.m}.
proof. proc; sim. qed.

equiv Orc5vu_enc : Orc5v(FinRO).enc ~ Orc5u(FinRO).enc :
  ={arg, RO.m, Mem.log} ==> ={res, RO.m, Mem.log}.
proof. by proc; inline{1} FinRO.get; wp; rnd; wp; call cc_self; auto. qed.

equiv Orc5vu_dec : Orc5v(FinRO).dec ~ Orc5u(FinRO).dec :
  ={arg, Mem.log, Mem.lc} ==> ={res, Mem.log, Mem.lc}.
proof. by proc; auto. qed.

equiv G5endB_self : G5endB(FinRO).main ~ G5endB(FinRO).main :
  ={RO.m, Mem.log, Mem.lc, BNR.lenc} ==> ={res}.
proof. proc; sim. qed.

lemma L8b &m :
  Pr[MainD(G5v(BNR_Adv(A)), RO).distinguish() @ &m : res] =
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : res].
proof.
have hll : forall (_:nonce*C.counter), is_lossless dblock by move=> _; apply dblock_ll.
have h1 := FiniteRO.pr_RO_FinRO_D hll (G5v(BNR_Adv(A))) &m () (fun b => b).
have h2 := FiniteRO.pr_RO_FinRO_D hll (G5u(BNR_Adv(A))) &m () (fun b => b).
have h3 : Pr[MainD(G5v(BNR_Adv(A)), FinRO).distinguish() @ &m : res] =
          Pr[MainD(G5u(BNR_Adv(A)), FinRO).distinguish() @ &m : res].
+ byequiv => //; proc.
  seq 1 1 : (={glob A, RO.m}); first by sim.
  inline{1} G5v(BNR_Adv(A), FinRO).distinguish.
  inline{2} G5u(BNR_Adv(A), FinRO).distinguish.
  inline{1} BNR_Adv(A, Orc5v(FinRO)).main.
  inline{2} BNR_Adv(A, Orc5u(FinRO)).main.
  inline{1} BNR(Orc5v(FinRO)).init.
  inline{2} BNR(Orc5u(FinRO)).init.
  wp; call G5endB_self.
  wp; call (_: ={RO.m, Mem.log, Mem.lc, BNR.lenc, BNR.ndec}).
  + proc; sp; if; 1,3: by auto.
    by wp; call Orc5vu_enc; auto.
  + proc; sp; if; 1,3: by auto.
    by wp; call Orc5vu_dec; auto.
  by auto.
smt().
qed.

op dqj (j : int) (lc : ciphertext list) : ciphertext =
  nth witness lc (size lc - 1 - j).

op Ej (j : int) (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list) =
  j < size lc /\ (dqj j lc) \in lg.

op Ejc (j : int) (lc : ciphertext list) (lenc : nonce list) =
  j < size lc /\ (dqj j lc).`1 \in lenc.

module G5uF (Ad:CCA_Adv) = {
  proc main () : unit = {
    var b;
    RO.init();
    Mem.log <- empty; Mem.lc <- []; BNR.lenc <- []; BNR.ndec <- 0;
    b <@ Ad(BNR(Orc5u(RO))).main();
  }
}.

lemma G5endB_ll : islossless G5endB(RO).main.
proof.
proc; while (true) (size ns - i).
+ by move=> z; inline RO.get; auto; smt(dblock_ll).
by auto; smt().
qed.

lemma L8EjF (j : int) &m :
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : Ej j Mem.log Mem.lc]
  = Pr[G5uF(A).main() @ &m : Ej j Mem.log Mem.lc].
proof.
byequiv (_: ={glob A} ==> ={Mem.log, Mem.lc}) => //.
proc.
inline{1} G5u(BNR_Adv(A), RO).distinguish.
inline{1} BNR_Adv(A, Orc5u(RO)).main.
inline{1} BNR(Orc5u(RO)).init.
wp; call{1} G5endB_ll.
wp; sim.
qed.

lemma dqj_cons (j : int) (dq : ciphertext) (lc : ciphertext list) :
  0 <= j => j < size lc => dqj j (dq :: lc) = dqj j lc.
proof. by rewrite /dqj /= => h1 h2; smt(). qed.

lemma dqj_cons0 (j : int) (dq : ciphertext) (lc : ciphertext list) :
  j = size lc => dqj j (dq :: lc) = dq.
proof. by rewrite /dqj /= => ->; smt(). qed.

lemma Orc5u_enc_lc (lcv : ciphertext list) :
  hoare [ Orc5u(RO).enc : Mem.lc = lcv ==> Mem.lc = lcv ].
proof. by proc; inline*; wp; rnd; wp; while (Mem.lc = lcv); auto. qed.

lemma cc_lc (lcv : ciphertext list) (lgv : (ciphertext,plaintext) fmap) :
  hoare [ Orc3(RO).cc : Mem.lc = lcv /\ Mem.log = lgv ==> Mem.lc = lcv /\ Mem.log = lgv ].
proof. by proc; inline*; while (Mem.lc = lcv /\ Mem.log = lgv); auto. qed.

lemma Orc5u_enc_Ej (j : int) (lcv : ciphertext list) (lgv : (ciphertext,plaintext) fmap) :
  phoare [ Orc5u(RO).enc :
    Mem.lc = lcv /\ Mem.log = lgv /\ ! (Ej j lgv lcv) /\ j < size lcv
    ==> Ej j Mem.log Mem.lc ] <= pr1_poly_out.
proof.
proc.
sp 1.
seq 1 : (Mem.lc = lcv /\ Mem.log = lgv /\ ! Ej j lgv lcv /\ j < size lcv)
        1%r pr1_poly_out 0%r 1%r.
+ done.
+ done.
+ wp; rnd; skip => /> &hr h1 h2.
  apply (RealOrder.ler_trans (mu dpoly_out (pred1 ((dqj j lcv).`4)))).
  + by apply mu_sub => t /=; rewrite /Ej /pred1 mem_set; smt().
  by rewrite pr1_poly_outE.
+ by hoare; call (cc_lc lcv lgv); auto.
smt().
qed.

lemma Orc5u_enc_pres (j : int) (lcv : ciphertext list)
                     (lgv : (ciphertext,plaintext) fmap) (b : bool) (nn : nonce) :
  hoare [ Orc5u(RO).enc :
    Mem.lc = lcv /\ Mem.log = lgv /\ arg.`1 = nn /\ Ej j lgv lcv = b /\
    (j < size lcv => (dqj j lcv).`1 <> nn)
    ==> Mem.lc = lcv /\ Ej j Mem.log Mem.lc = b ].
proof.
proc.
sp 1.
seq 1 : (Mem.lc = lcv /\ Mem.log = lgv /\ n = nn /\ Ej j lgv lcv = b /\
         (j < size lcv => (dqj j lcv).`1 <> nn)).
+ by call (cc_lc lcv lgv); auto.
auto => /> &hr h1 t _.
rewrite /Ej mem_set eq_iff.
case: (j < size lcv) => hlt //=.
have := h1 hlt.
smt().
qed.

lemma Orc5u_dec_Ej (j : int) (b : bool) (c : int) :
  0 <= j =>
  hoare [ Orc5u(RO).dec :
    Ej j Mem.log Mem.lc = b /\ b2i (Ejc j Mem.lc BNR.lenc) = c
    ==> Ej j Mem.log Mem.lc = b /\ c <= b2i (Ejc j Mem.lc BNR.lenc) ].
proof.
move=> hj; proc; auto => /> &hr.
case: (cph{hr} \in Mem.log{hr}) => hc //=.
rewrite /Ej /Ejc.
case: (j < size Mem.lc{hr}) => hlt.
+ by rewrite !(dqj_cons j cph{hr} Mem.lc{hr} hj hlt) /=; smt(size_ge0).
case: (j = size Mem.lc{hr}) => he.
+ by rewrite !(dqj_cons0 j cph{hr} Mem.lc{hr} he) /=; smt(b2i_ge0 b2i_le1 size_ge0).
smt(size_ge0).
qed.

lemma L8Ej (j : int) &m :
  0 <= j =>
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : Ej j Mem.log Mem.lc]
  <= pr1_poly_out.
proof.
move=> hj.
rewrite (L8EjF j &m).
fel 5 (b2i (Ejc j Mem.lc BNR.lenc)) (fun _ => pr1_poly_out) 1
    (Ej j Mem.log Mem.lc)
    [BNR(Orc5u(RO)).enc :
       (check_plaintext BNR.lenc p /\ j < size Mem.lc /\ (dqj j Mem.lc).`1 = p.`1);
     Orc5u(RO).dec : (false)] true.
+ by rewrite StdBigop.Bigreal.BRA.big_int1.
+ by move=> &hr h _; smt().
+ by inline*; auto; rewrite /Ej /Ejc /=; smt().
+ proc; sp; rcondt 1; first by auto; smt().
  wp.
  exists* Mem.lc; elim* => lcv.
  exists* Mem.log; elim* => lgv.
  call (Orc5u_enc_Ej j lcv lgv).
  by auto; smt().
+ move=> c; proc; sp; rcondt 1; first by auto; smt().
  wp.
  exists* Mem.lc; elim* => lcv.
  call (Orc5u_enc_lc lcv).
  by auto; rewrite /Ejc /check_plaintext; smt(b2i_ge0).
+ move=> b c; proc; sp; if; last by auto.
  wp.
  exists* Mem.lc; elim* => lcv.
  exists* Mem.log; elim* => lgv.
  exists* p; elim* => pv.
  call (Orc5u_enc_pres j lcv lgv b pv.`1).
  by auto; rewrite /Ejc /check_plaintext; smt(b2i_ge0 b2i_le1).
+ by conseq (_: false ==> _).
+ by move=> c; conseq (_: false ==> _).
by move=> b c; conseq (Orc5u_dec_Ej j b c hj).
qed.

lemma noBad1_Ej (lg : (ciphertext,plaintext) fmap) (lc : ciphertext list) :
  ! noBad1 lg lc => exists j, 0 <= j < size lc /\ Ej j lg lc.
proof.
rewrite /noBad1 negb_forall /= => -[dq]; rewrite negb_imply => -[h1 h2].
have hi : 0 <= index dq lc < size lc by smt(index_ge0 index_mem).
exists (size lc - 1 - index dq lc); rewrite /Ej /dqj.
have -> : size lc - 1 - (size lc - 1 - index dq lc) = index dq lc by smt().
by rewrite nth_index //=; smt().
qed.

lemma G5endB_lc (lcv : ciphertext list) :
  hoare [ G5endB(RO).main : Mem.lc = lcv ==> Mem.lc = lcv ].
proof. by proc; while (Mem.lc = lcv); [ inline RO.get; auto | auto ]. qed.

lemma pr_range_bound (k : int) &m :
  0 <= k =>
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
      exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc]
  <= k%r * pr1_poly_out.
proof.
elim/natind: k => [k hk hk0 | k hk ih hk0].
+ have hk1 : k = 0 by smt().
  have h : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
               exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc] <= 0%r.
  + byphoare => //; hoare; conseq (_: _ ==> true) => //; smt().
  smt(ge0_pr1_poly_out).
have hle : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             exists j, 0 <= j < k+1 /\ Ej j Mem.log Mem.lc]
        <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             (exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc) \/ Ej k Mem.log Mem.lc].
+ rewrite Pr[mu_sub].
  move=> &hr [j hj].
  case: (j < k) => hjk; [ by left; exists j; smt() | ].
  right; have -> : k = j by smt().
  smt().
  done.
have h3 : 0%r <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             (exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc) /\ Ej k Mem.log Mem.lc]
  by rewrite Pr[mu_ge0].
have hor : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             (exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc) \/ Ej k Mem.log Mem.lc]
        <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             exists j, 0 <= j < k /\ Ej j Mem.log Mem.lc]
         + Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : Ej k Mem.log Mem.lc].
+ rewrite Pr[mu_or]; smt().
have h1 := ih hk.
have h2 := L8Ej k &m hk.
smt().
qed.

lemma L8bad1 &m :
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : ! noBad1 Mem.log Mem.lc]
  <= qdec%r * pr1_poly_out.
proof.
have h2 : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : ! (size Mem.lc <= qdec)] = 0%r.
+ byphoare => //; hoare.
  proc.
  inline G5u(BNR_Adv(A), RO).distinguish.
  inline BNR_Adv(A, Orc5u(RO)).main.
  inline BNR(Orc5u(RO)).init.
  inline RO.init.
  seq 8 : (inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec).
  + wp; call (_: inv0 RO.m Mem.log Mem.lc BNR.lenc BNR.ndec).
    + by apply BNR_enc_inv.
    + by apply BNR_dec_inv.
    by auto => />; rewrite /inv0; smt(mem_empty ge0_qdec).
  exists* Mem.lc; elim* => lcv.
  wp; call (G5endB_lc lcv).
  by auto => />; rewrite /inv0; smt().
have h1 : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : ! noBad1 Mem.log Mem.lc]
       <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             (exists j, 0 <= j < qdec /\ Ej j Mem.log Mem.lc) \/ ! (size Mem.lc <= qdec)].
+ by rewrite Pr[mu_sub] //; smt(noBad1_Ej).
have h4 : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             (exists j, 0 <= j < qdec /\ Ej j Mem.log Mem.lc) \/ ! (size Mem.lc <= qdec)]
       <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
             exists j, 0 <= j < qdec /\ Ej j Mem.log Mem.lc]
        + Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : ! (size Mem.lc <= qdec)].
+ have hg : 0%r <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m :
              ((exists j, 0 <= j < qdec /\ Ej j Mem.log Mem.lc) /\ ! (size Mem.lc <= qdec))]
    by rewrite Pr[mu_ge0].
  rewrite Pr[mu_or]; smt().
have h3 := pr_range_bound qdec &m ge0_qdec.
smt().
qed.

lemma L8c &m :
  Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : res] <=
  qdec%r * (maxr pr_zeropol pr1_poly_out) + qdec%r * pr1_poly_out.
proof.
have h1 := L8c_main &m.
have h2 := L8bad1 &m.
have h3 : Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : res /\ ! noBad1 Mem.log Mem.lc]
       <= Pr[MainD(G5u(BNR_Adv(A)), RO).distinguish() @ &m : ! noBad1 Mem.log Mem.lc].
+ by rewrite Pr[mu_sub].
rewrite Pr[mu_split (noBad1 Mem.log Mem.lc)].
smt().
qed.

lemma L8 &m :
  Pr[MainD(G5(BNR_Adv(A)), RO).distinguish() @ &m : res] <=
  qdec%r * (maxr pr_zeropol pr1_poly_out) + qdec%r * pr1_poly_out.
proof.
have h1 := L8a &m. have h2 := L8b &m. have h3 := L8c &m.
by rewrite h1 h2.
qed.

lemma step2 &m :
  Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res] <=
    Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
    qdec%r * (maxr pr_zeropol pr1_poly_out) + qdec%r * pr1_poly_out.
proof.
rewrite (L1 &m) (L2 &m).
have h3 := L3 &m. have h4 := L4 &m. have h5 := L5 &m. have h6 := L6 &m.
have h7 := L7 &m. have h8 := L8 &m.
smt().
qed.
  
  (* SCRATCHPAD END *)

lemma conclusion &m :
    Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
      Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
      (Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] -
       Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res]) +
       qdec%r * (maxr pr_zeropol pr1_poly_out) +
       qdec%r * pr1_poly_out.
proof.
have h1 := step1 &m.
have h2 := step2 &m.
smt().
qed.

end section PROOFS.
