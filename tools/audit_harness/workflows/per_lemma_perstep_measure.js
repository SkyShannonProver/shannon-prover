export const meta = {
  name: 'pir-panel-perstep',
  description: 'Classify each PIR_correct proof step: was the thin panel "nothing to give" or "under-delivered"?',
  phases: [{ title: 'Judge', detail: 'one judge per proof step' }, { title: 'Synthesize', detail: 'tally + verdict' }],
}

const STEPS = '.panel_audit_handoff/pir_steps.json'  // repo-relative; regenerate per README

const VERDICT = {
  type: 'object', additionalProperties: false,
  required: ['i', 'tactic', 'demand', 'supply', 'verdict', 'missing_thing'],
  properties: {
    i: { type: 'number' },
    tactic: { type: 'string' },
    demand: { type: 'string', description: 'the MECHANICAL help (a lemma name? invariant frame? tactic form? alignment?) that would have made THIS step easier — or "none" if this is pure intro/case/bookkeeping/auto where no tool supply applies' },
    supply: { type: 'string', description: 'what the panel actually gave relevant to the demand' },
    verdict: { type: 'string', enum: ['nothing_to_give', 'under_delivered', 'misrouted', 'adequate'] },
    missing_thing: { type: 'string', description: 'if under_delivered/misrouted: the concrete thing the panel should have named (e.g. "lemma name big_consT", "operator route should be big not (+^)", "invariant frame: relate big a s, big a s\', j"); else ""' },
  },
}

const JUDGE = `You are a SKEPTICAL prover-experience reviewer. You are looking at ONE step of a real EasyCrypt proof (PIR_correct) and the L4 panel the agent saw when DECIDING that step. Question: was the panel's thinness because there was genuinely nothing mechanical to give at this step, or because we UNDER-DELIVERED help the step actually needed?

Read your step: run \`python3 -c "import json,sys; print(json.dumps(json.load(open('STEPS_PATH'))[IDX]))"\` — fields: i, tactic (the move the prover committed), phase, goal_snippet (the conclusion), panel (the full L4 followup the agent read).

Judge honestly:
- What MECHANICAL help (the kind a tool can supply — a specific LEMMA NAME to rewrite/apply with, an invariant FRAME = which vars to relate, a tactic FORM, an alignment offset/seq index) would have made THIS step easier? If the step is pure intro / destructuring / case-split / \`auto\` / bookkeeping where NO tool supply meaningfully helps (the prover just structures hypotheses), demand = "none".
- What did the panel actually give? (Look at the "Goal operators", "Need more?" routes, any frontier/seq/invariant content.)
- verdict: "nothing_to_give" (demand is none — thin is CORRECT here); "under_delivered" (the step needed a concrete lemma/frame/index the panel did NOT name — e.g. it does \`rewrite big_consT\` but the panel never names big_consT); "misrouted" (the panel pointed at the WRONG thing — e.g. routes operator_lemmas to (+^) when the step rewrites with a big-lemma); "adequate" (panel named what the step needed).
Be concrete: name the lemma/frame the step used (read the tactic) and check whether the panel named it.`

const idx = Array.isArray(args) ? args : JSON.parse(args)
phase('Judge')
const verdicts = await parallel(idx.map((i) => () =>
  agent(JUDGE.replaceAll('STEPS_PATH', STEPS).replaceAll('IDX', String(i)),
    { schema: VERDICT, label: `step:${i}`, phase: 'Judge' })
))
const ok = verdicts.filter(Boolean)

phase('Synthesize')
const tally = { nothing_to_give: 0, under_delivered: 0, misrouted: 0, adequate: 0 }
for (const v of ok) tally[v.verdict] = (tally[v.verdict] || 0) + 1
const missing = ok.filter((v) => v.verdict === 'under_delivered' || v.verdict === 'misrouted')
  .map((v) => ({ i: v.i, tactic: v.tactic, missing: v.missing_thing }))

const synth = await agent(
  `You are answering the owner's question: on PIR_correct, is the L4 panel thin because the lemma is too simple to need mechanical help, or because we UNDER-DELIVER the help it needs? Here are per-step verdicts over all 32 steps:\n${JSON.stringify(ok)}\n\nWrite a tight markdown answer: (1) the headline (simple-vs-under-delivered, with the counts: how many steps genuinely had nothing to give vs how many under-delivered/misrouted); (2) WHAT was most commonly under-delivered (group the missing_thing — lemma names? which ones recur? invariant frame?); (3) the single highest-leverage fix for THIS lemma and roughly how many of its steps it would help; (4) one honest sentence on whether PIR is representative or a worst-case for the current panel. Be concrete and cite step indices + lemma names.`,
  { schema: { type: 'object', additionalProperties: false, required: ['doc'], properties: { doc: { type: 'string' } } },
    label: 'synthesize', phase: 'Synthesize' }
)
return { steps: ok.length, tally, under_delivered_steps: missing, answer: synth.doc }
