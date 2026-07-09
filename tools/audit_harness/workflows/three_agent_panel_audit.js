export const meta = {
  name: 'live-followup-panel-audit',
  description: 'Three-agent panel audit on LIVE-RENDERED followups (each frontier replayed through the real ProofNodeManager via playground/node_boot, current code — no patches). agent#1 derives the mechanical demand from the next committed tactics, agent#2 judges the followup the agent actually reads, agent#3 refutes each 误导.',
  phases: [{ title: 'Demand' }, { title: 'Supply' }, { title: 'Verify' }, { title: 'Synthesize' }],
}

// Per-item files (item_<i>.json, one compact line each) — NOT the 4137-line array, which
// the Read tool truncates at 2000 lines so agents past ~#44 read half a file and fail.
const DIR = '.panel_audit_handoff/items'  // repo-relative; regenerate per README

const DEMAND = [
  'You are PROOF-WRITER agent #1 (DEMAND lens). You get a GOAL at one proof frontier, the next committed tactic(s)',
  'that resolve it (`next_tactics`), and `proof_context` (a window of the surrounding proof). NO panel access. A panel exists to supply',
  'MECHANICAL work; the SEMANTIC core is the prover\'s OWN. Process like a prover at the keyboard: stare at the goal,',
  'then read the next_tactics to see what HIGH-VALUE MECHANICAL (C) info they used — the named lemma applied/rewritten',
  '(+ exlim/lifted witnesses), the swap/seq/inline/sp/rcond INDEX, the frame/write-map/glob-drop, the alignment',
  'offset / which side / call-frontier procedure. Ground EACH in next_tactics (quote). RANK c_needs (highest-value',
  'first = most tedious-to-find / most wrong-turn-preventing). b_cores = the invariant/coupling/reduction IDEA the',
  'answer invents (the prover\'s OWN — list ONLY so #2 knows what the panel must NOT supply; a panel that omits B is',
  'NOT deficient, one that GUESSES a concrete B is overreaching; never treat missing B as a gap). a_readoff = visible',
  'in the goal. Re-derive the goal STRUCTURE precisely.',
].join('\n')
const DEMAND_SCHEMA = { type: 'object', additionalProperties: false,
  required: ['state_id','goal_structure','answer_route','b_cores','c_needs','a_readoff','demand_summary'],
  properties: { state_id:{type:'string'}, goal_structure:{type:'string'}, answer_route:{type:'string'},
    b_cores:{type:'array',items:{type:'string'}}, c_needs:{type:'array',items:{type:'string'}},
    a_readoff:{type:'array',items:{type:'string'}}, demand_summary:{type:'string'} } }

const SUPPLY = [
  'You are AUDITOR agent #2 (SUPPLY lens). You get the GOAL, the LIVE FOLLOWUP the prover actually reads (rendered',
  'just now through the real manager on current code — this IS the agent-facing panel text, not a structure dump),',
  'and an independent answer-grounded DEMAND (BLIND to the panel): ranked `c_needs` = the high-value MECHANICAL facts',
  'the answer used (what the panel is measured against); `b_cores` = the prover\'s OWN semantic work (panel must NOT',
  'supply/guess). Judge EACH distinct claim/element in the followup, EXACTLY one verdict:',
  '  super有用: supplies a real high-value MECHANICAL C the answer uses (exact named lemma / concrete index / frame',
  '    write-map / glob-drop / alignment offset) AND structurally CORRECT — OR a correct VAR-FRAME scaffold (names the',
  '    live vars to relate, predicate BLANKED). The prover builds on it.',
  '  necessary: IDE INFRASTRUCTURE the prover needs to work — the goal text itself, the status/progress line, the',
  '    last-result/manager feedback, the protocol reminder. NOT a mechanical hint, but NOT deletable boilerplate either.',
  '    Do NOT mark these 鸡肋 (the goal is the agent\'s ONLY source of the goal; a status bar is a needed progress cue).',
  '  鸡肋: USELESS boilerplate that SHOULD be trimmed — restates a hint generically, a dead/placeholder line, an',
  '    off-topic menu item, an inert status flag. Harmless but pure noise. (NOT the goal/status/feedback — those are necessary.)',
  '  误导: structural-truth FAILS for THIS goal, OR a wrong mechanical fact (wrong index / inapplicable lemma / wrong',
  '    label e.g. one-sided on a phoare or synchronized goal / a stale call frontier not in the goal), OR it GUESSES a',
  '    B-core concrete predicate (overreach).',
  'KEY: never mark "panel did not supply the invariant/B-core" as a gap — B is the prover\'s OWN. Re-derive each',
  'structural claim FROM THE GOAL first.',
  'ALSO REQUIRED — should_have_but_missing (面板该有却没有的): walk agent#1\'s ranked c_needs and list EACH one the panel',
  '  does NOT supply at all (the panel SHOULD have it but doesn\'t). This is the demand-coverage gap — the most important',
  '  output for measuring whether the panel delivers the high-value mechanical info. Rank by value (highest first).',
].join('\n')
const SUPPLY_SCHEMA = { type:'object', additionalProperties:false,
  required:['state_id','elements','should_have_but_missing','one_line'],
  properties:{ state_id:{type:'string'},
    elements:{type:'array',items:{type:'object',additionalProperties:false,
      required:['element','verdict','structural_truth','why'],
      properties:{ element:{type:'string'}, verdict:{type:'string',enum:['super有用','necessary','鸡肋','误导']},
        structural_truth:{type:'string',enum:['correct','partial','wrong','na']}, why:{type:'string'} } } },
    should_have_but_missing:{type:'array',items:{type:'string'},description:'ranked c_needs the panel SHOULD have but does not supply'},
    one_line:{type:'string'} } }

const VERIFY = [
  'You are VERIFIER agent #3 (adversarial). Agent #2 flagged followup elements as 误导. #2 sometimes MIS-READS the',
  'goal and calls a correct element wrong. Independently re-derive the GOAL structure and try to REFUTE each 误导:',
  'ruling = confirmed_误导 (goal really is as #2 said AND element really is wrong/misdirecting), refuted (element is',
  'CORRECT for the real goal — #2 mis-read), or partial. Quote the goal evidence. Default to REFUTE if #2\'s premise',
  'about the goal is not clearly supported by the goal text.',
].join('\n')
const VERIFY_SCHEMA = { type:'object', additionalProperties:false, required:['state_id','verdicts'],
  properties:{ state_id:{type:'string'}, verdicts:{type:'array',items:{type:'object',additionalProperties:false,
    required:['element','ruling','reason'],
    properties:{ element:{type:'string'}, ruling:{type:'string',enum:['confirmed_误导','refuted','partial']}, reason:{type:'string'} } } } } }

// N is passed deterministically via args (the selection script knows the exact count).
// Do NOT count the array with an LLM agent — it miscounts large arrays (89 -> 88) and
// silently drops the tail frontier.
const N = (typeof args === 'number' && args > 0) ? args : 89
log(`live corpus: ${N} frontiers`)

phase('Demand')
const idx = Array.from({ length: N }, (_, i) => i)
const results = await pipeline(idx,
  i => agent(DEMAND + `\n\nRead the JSON object at ${DIR}/item_${i}.json: id/lemma/phase/goal/next_tactics/proof_context (a window of the proof around this frontier). Derive ranked c_needs grounded in next_tactics. state_id = its "id".`,
    { label: `demand:${i}`, phase: 'Demand', schema: DEMAND_SCHEMA }),
  (demand, i) => agent(SUPPLY + `\n\nRead the JSON object at ${DIR}/item_${i}.json: use its "goal" and "followup" (the live agent-read panel). DEMAND (blind to panel):\n` + JSON.stringify(demand) + `\nJudge every element of the followup. state_id = its "id".`,
    { label: `supply:${i}`, phase: 'Supply', schema: SUPPLY_SCHEMA }).then(supply => ({ demand, supply, i })),
  (pair, i) => {
    const wrong = (pair.supply && pair.supply.elements || []).filter(e => e.verdict === '误导')
    if (!wrong.length) return { ...pair, verified: { verdicts: [] } }
    return agent(VERIFY + `\n\nRead the JSON object at ${DIR}/item_${i}.json, use its "goal" (ignore followup). Rule on each 误导:\n` + JSON.stringify(wrong),
      { label: `verify:${i}`, phase: 'Verify', schema: VERIFY_SCHEMA }).then(v => ({ ...pair, verified: v }))
  })

phase('Synthesize')
const clean = results.filter(Boolean)
const doc = await agent(
  'Synthesize a RE-AUDIT on LIVE-RENDERED followups (each frontier replayed through the real ProofNodeManager on CURRENT code via playground/node_boot — exactly what the prover reads, no patches) AFTER the fix wave (Fix A opener-shape, Fix B call-frontier method-tail pairing, Fix C roster gating, Fix-4 operator_lemmas pre-fill). From these {demand (agent#1, blind), supply (agent#2: per-element verdict + should_have_but_missing), verified (agent#3)} triples:\n' +
  JSON.stringify(clean, null, 2) + '\n\n' +
  'agent#2 verdicts are now FOUR: super有用 / necessary (goal/status/feedback IDE-infra — NOT 鸡肋) / 鸡肋 (trimmable noise) / 误导. Count a 误导 ONLY if agent#3 ruled confirmed_误导. Report:\n' +
  '1. HEADLINE — super有用 / necessary / 鸡肋 / confirmed-误导 counts + %; raw 误导 agent#3 REFUTED (single-agent FP rate). COMPARE to the PRIOR live round (pre-fix: super 6.4% / 鸡肋 85.6% / 误导 8.0% over 591 elements) — call out the delta. Note `necessary` is a NEW category that pulls IDE-infra OUT of the old 鸡肋 bucket.\n' +
  '2. DEMAND-COVERAGE (面板该有却没有的) — aggregate should_have_but_missing vs the c_needs SUPPLIED (super有用). What fraction of the high-value mechanical demand does the panel now deliver? Did Fix-4 (operator_lemmas pre-fill) move it? Group the top MISSING demands by type (named lemma / seq index / invariant body / frame).\n' +
  '3. ★ SUPER有用 by type (protect).\n' +
  '4. ❌ CONFIRMED 误导 grouped by producer/root-cause, RANKED by harm, each with the state. Explicitly check the Fix-targeted producers: did Fix A (opener byphoare/|·|), Fix B (call-frontier "no matching"/side-inversion), Fix C (roster on no-program) clear? What 误导 REMAINS (incl. Fix-B residuals: setup-count off-by-N, swap-on-non-permutation, buried sub-call)?\n' +
  '5. RESOLVED-CONFIRMATION on the LIVE surface for each shipped fix (A/B/C/Fix-4 + the earlier FIX#1/2/3). Quote the evidence.\n' +
  '6. 鸡肋 cut-list (trimmable noise only — NOT the necessary IDE-infra). 7. PER-PHASE verdict. 8. RANKED NEXT FIXES with code location.\n' +
  'Quantitative, decisive, trust agent#3 over agent#2 on goal structure. Skip items whose lemma is not in the public corpus.',
  { label: 'synthesize-live', phase: 'Synthesize' })
const conf = clean.flatMap(r => (r.verified && r.verified.verdicts || []).filter(v => v.ruling === 'confirmed_误导'))
const refuted = clean.flatMap(r => (r.verified && r.verified.verdicts || []).filter(v => v.ruling === 'refuted'))
const missing = clean.flatMap(r => (r.supply && r.supply.should_have_but_missing) || [])
return { states: clean.length, confirmed_误导: conf.length, refuted_误导: refuted.length, total_should_have_but_missing: missing.length, doc }
