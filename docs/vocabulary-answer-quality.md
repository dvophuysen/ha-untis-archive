# Meaning grading and reversible history correction — 1.13.6

## Release behavior

Only meaning mode uses semantic grading. Spelling mode keeps its spelling rules.
Ownership, source validity and unit membership are checked before any paid call.
The public request cannot supply a verdict or a grading override.

1. Exact normalized book answers: no model call. Whole answer is compared;
   negation and additional content cannot pass through substring/edit-distance matching.
2. Small editorial reference set: alternatives are bound to the Spanish source
   word, complete printed meanings and translation direction. Printed entries
   are unchanged. Geografie/Geographie, etwas angrenzen and auf einem Ausflug
   are accepted for their reviewed source entries. Hauptsprache receives a
   clarification for Amtssprache.
3. Other meaning answers: gpt-5-mini, Foundry 2 only, medium reasoning. No fallback
   to Foundry 1. Review separates input quality, specificity and equivalence.
4. Unclear input, broader answers, invalid output or provider failure: no attempt
   is recorded. The child can rephrase or continue without a grade. Confirmation
   alone cannot manufacture a correct attempt.
5. Weighted model decisions and their source context are stored alongside the
   attempt. Feedback quotes the stored book text, not a model-generated quotation.

No automatic retrospective regrading. Model calls use the existing metered
AI gateway and provider-side conversation storage remains disabled.

## Measurements, 2026-09-20

The initial low-reasoning candidate was rejected: 24/30 exact decisions,
including an overgenerous proper-name classification and overly harsh handling
of transcription fragments.

The revised medium-reasoning prompt was measured on 30 individual real Azure
requests: 26 exact reference decisions, two neutral provider refusals, one
conservative clarification (bekannt versus berühmt), and one overly strict
classification (Hauptsprache versus Amtssprache). The latter is handled by the
source-bound editorial rule, covered by automated scope tests.

An additional 12-case holdout used the actual application gateway, local isolated
accounting and no learner writes. This covered German-to-Spanish alternatives
and counterexamples, Latin and English. 11/12 matched the reference decision;
ser conocido versus ser famoso received a neutral clarification rather than the
reference acceptance. All 12 calls used gpt-5-mini and settled in the local ledger.
The test database contained zero learning attempts.

Across these 42 cases, the released decision policy matches 38 expected decisions
and leaves four cases ungraded: two provider refusals and the conservative
bekannt/berühmt distinction in both directions. In this finite reference set,
no wrong answer is accepted and no valid answer is penalized by the final policy.
This is a bounded calibration result, not a guarantee for arbitrary future inputs
or a claim that model outputs are deterministic. Novel model-reviewed answers
remain open to parent review. The editorial cases are regression cases, not
independent holdout evidence.

Measured latency for the revised 30-request run: median 12.67 seconds,
range 5.75–15.89 seconds. Exact and editorial matches need no Azure request.
Technical grading and transcription waiting time is excluded from the new
answer clock; duration never downgrades mastery.

## History and skipping

1.13.5 supplies a parent-only preview/commit/reverse operation. A digest protects
against a changed selection. Reviews append exclusions; raw attempts are never
rewritten. Learning states are replayed from included attempts, including aliases.
The UI distinguishes skipping without a grade from explicitly giving up, and
counts ungraded cards separately. Leaving a card disposes its microphone callback.

Deployment and a child's actual correction are separate operations. Installing
this release alone neither excludes any historic attempts nor proves that the
live correction has been applied.
