export const meta = {
  name: 'panel-fix-verify',
  description: 'Adversarially judge OLD-vs-NEW panel-producer changes from the 7 re-audit fix commits',
  phases: [{ title: 'Judge', detail: 'one skeptical judge per changed item' }, { title: 'Synthesize', detail: 'tally + flag regressions' }],
}

const DIR = '.panel_audit_handoff'  // repo-relative; regenerate per README

const VERDICT = {
  type: 'object', additionalProperties: false,
  required: ['state_id', 'per_change', 'overall'],
  properties: {
    state_id: { type: 'string' },
    per_change: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['producer', 'verdict', 'reason'],
        properties: {
          producer: { type: 'string', enum: ['goal_operators', 'operator_route', 'opener_reduce'] },
          verdict: { type: 'string', enum: ['improvement', 'neutral', 'regression'] },
          reason: { type: 'string', description: 'grounded ONLY in the goal text' },
        },
      },
    },
    overall: { type: 'string', enum: ['improvement', 'neutral', 'regression'] },
  },
}

const JUDGE = `You are an INDEPENDENT, SKEPTICAL panel reviewer. You did NOT make these changes and have no stake in them being good. A separate engineer changed some EasyCrypt proof-panel producers; your job is to catch any change that made the panel WORSE.

Read the FULL goal: run \`cat \${DIR}/items/item_<i>.json\` (or read it) and use the "goal" field — the real EasyCrypt goal. Also read \`\${DIR}/judgment_args.json\` and find the record whose "i" == <i>; its "changed" field has the OLD vs NEW producer output, and "next_tactics" is the committed proof's actual next moves (ground truth for the route).

RE-DERIVE the goal's structure YOURSELF. Then judge each changed producer:

- goal_operators (the "Goal operators" lookup list): REMOVED tokens should be TYPES (int/bool/list/ptxt/ZModE.exp/fmap/key/nonce/…) or BOUND VARIABLES (binders like result_R, A_L, r_L, j0) — NOT real operators. ADDED tokens should be REAL operators/functions that actually appear in the goal conclusion (e.g. big, predT, sxor2, oget). verdict=improvement if junk removed / real ops surfaced; regression if a REAL operator was removed or a NON-operator (type/binder/garbage) was added; neutral if a wash.
- operator_route (the operator_lemmas pre-fill head op): the goal's load-bearing caret is EITHER group exponentiation \`^\` (g^x, DH/Schnorr) OR the field/word XOR digraph \`+^\` (xor). Check WHICH the goal conclusion actually uses. NEW reroutes (^)->(+^). verdict=improvement if the goal uses \`+^\` (so (+^) is correct and the old (^) was wrong); regression if the goal actually uses a real group \`^\` (then rerouting is wrong).
- opener_reduce (the opener reduction menu): the lead reduction should fit the goal — \`byphoare\` for a single \`Pr[…] = / <= value\`, \`byequiv\` for a 2-program \`Pr[A]=Pr[B]\` (equality post for \`=\`, implication post for \`<=\`, \`\\/ bad\` only for a genuine up-to-bad bound), \`ler_trans\` for a \`|Pr-Pr|\`/sum bound. Compare to next_tactics[0]. verdict=improvement if NEW leads with / suggests the form matching the committed opener and OLD did not; regression if NEW now mis-routes.

Default to 'regression' for a change you cannot justify from the goal. Be specific: cite the operator/shape you see in the goal.`

const SYNTH = `You are aggregating independent reviewer verdicts on panel-producer changes. Tally improvement/neutral/regression per producer and overall, and LIST every regression (state_id + producer + reason) verbatim so it can be fixed. Then give a one-paragraph bottom line: did the fix wave land cleanly, and what (if anything) regressed. Input verdicts: `

const idx = Array.isArray(args) ? args : JSON.parse(args)
phase('Judge')
const verdicts = await parallel(idx.map((i) => () =>
  agent(JUDGE.replaceAll('<i>', String(i)).replaceAll('${DIR}', DIR),
    { schema: VERDICT, label: `judge:i${i}`, phase: 'Judge' })
))
const ok = verdicts.filter(Boolean)
phase('Synthesize')

const tally = { improvement: 0, neutral: 0, regression: 0 }
const regressions = []
for (const v of ok) {
  tally[v.overall] = (tally[v.overall] || 0) + 1
  for (const c of (v.per_change || [])) {
    if (c.verdict === 'regression') regressions.push({ state_id: v.state_id, producer: c.producer, reason: c.reason })
  }
}
const synth = await agent(SYNTH + JSON.stringify(ok), {
  schema: {
    type: 'object', additionalProperties: false,
    required: ['bottom_line', 'regression_count', 'doc'],
    properties: {
      bottom_line: { type: 'string' },
      regression_count: { type: 'number' },
      doc: { type: 'string', description: 'the full written verification report' },
    },
  }, label: 'synthesize', phase: 'Synthesize',
})
return { judged: ok.length, overall_tally: tally, deterministic_regressions: regressions, synthesis: synth }
