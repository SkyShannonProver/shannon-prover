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
  (* SCRATCHPAD END *)

lemma conclusion &m :
    Pr[CCA_game(BNR_Adv(A), RealOrcls(ChaChaPoly)).main() @ &m : res] <=
      Pr[CCA_game(CCA_CPA_Adv(BNR_Adv(A)), EncRnd).main() @ &m : res] +
      (Pr[Indist.Distinguish(D(BNR_Adv(A)), IndBlock).game() @ &m : res] -
       Pr[Indist.Distinguish(D(BNR_Adv(A)), IndRO).game() @ &m : res]) +
       qdec%r * (maxr pr_zeropol pr1_poly_out) +
       qdec%r * pr1_poly_out.
proof.
  (* PROVE THIS — replace this line with a machine-checkable proof *)
  admit.
qed.

end section PROOFS.
