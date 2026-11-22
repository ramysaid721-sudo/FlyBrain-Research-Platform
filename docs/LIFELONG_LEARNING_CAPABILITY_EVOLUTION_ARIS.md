# Lifelong Learning, Capability Evolution, and ARIS Evidence Observatory

**Status:** architecture and implementation specification; not a claim of deployed autonomous learning.  
**Target:** FlyBrain / URCAL.  
**Operating principle:** learn what is needed to solve the problem, verify what was learned, turn validated knowledge into reusable capability, and continuously identify safe improvements.

## 1. Mission

FlyBrain should evolve from a task executor into a continuously improving research-and-engineering system with:
- on-demand acquisition of knowledge across disciplines, languages, history, science, engineering, law, economics, and current affairs;
- skill and tool discovery, evaluation, composition, and maintenance;
- problem-driven learning rather than indiscriminate accumulation;
- controlled self-improvement of its own workflows, adapters, tests, and documentation;
- persistent, resumable background work with measurable cost and safety limits;
- an evidence observatory for documenting alleged international crimes and tracing the supply, finance, and decision networks behind weapons systems, using Gaza as a priority case study.

## 2. Problem-driven learning cycle

For each user objective, the learning orchestrator should:

1. **Frame the problem:** define the outcome, scope, constraints, affected parties, deadline, and success criteria.
2. **Identify knowledge gaps:** map required disciplines, languages, methods, datasets, tools, and expert roles.
3. **Build a learning plan:** rank gaps by relevance, expected value, uncertainty, acquisition cost, and risk.
4. **Acquire lawful sources:** prioritize peer-reviewed research, official records, standards, primary documents, public datasets, public-domain works, licensed material, and user-provided files.
5. **Extract and normalize:** identify concepts, methods, claims, definitions, evidence, citations, and disagreements.
6. **Cross-check:** seek independent corroboration; distinguish source repetition from independent evidence.
7. **Practice:** solve benchmark problems, reproduce calculations where possible, run controlled experiments, and test tools in sandboxes.
8. **Create a capability candidate:** encode the validated method as a skill, workflow, adapter, dataset, or reference procedure.
9. **Evaluate:** run unit, integration, adversarial, regression, quality, and safety tests against a baseline.
10. **Promote or reject:** publish internally only when acceptance criteria pass; retain provenance and rollback path.
11. **Monitor drift:** schedule revalidation when sources, standards, news, APIs, or dependencies change.

Learning is not complete merely because text was downloaded or summarized. Completion requires demonstrated comprehension or successful performance on defined tasks.

## 3. Knowledge and copyright policy

- Ingest complete works only when they are public domain, openly licensed for the intended use, supplied by the user with appropriate rights, or otherwise lawfully accessible for that use.
- For copyrighted books and materials not supplied or licensed for full ingestion, use lawful summaries, bibliographic metadata, reviews, limited quotations where permitted, and targeted study of user-provided excerpts. Do not reproduce or store unauthorized full-text copies.
- Preserve source identity, edition, author, publication date, license, access date, and page/section references.
- Keep factual claims, interpretations, hypotheses, and generated summaries in separate fields.
- Support multilingual retrieval and translation while retaining the original-language source and marking machine translations.
- For current affairs, attach publication timestamps and update status; do not treat stale reports as current facts.

## 4. Skill and specialization discovery

Maintain a versioned capability registry. Each skill record should include:
- skill identifier, name, domain, description, version, maintainer/source;
- required tools, permissions, dependencies, models, datasets, and runtime;
- input/output schema and reproducible usage examples;
- supported languages and known limitations;
- evidence base, provenance, validation date, benchmark results;
- security classification, data sensitivity, and risk tier;
- cost, latency, reliability, and fallback options;
- lifecycle state: discovered, sandboxed, evaluated, approved, active, deprecated, or quarantined.

A skill is not activated merely because a source describes it. It must be tested in an isolated environment and pass capability-specific acceptance tests. Skills with overlapping functions should be benchmarked and composed only where integration improves outcomes.

## 5. Self-improvement and capability evolution

A continuous improvement loop should:
- detect repeated failures, bottlenecks, manual work, unused tools, and unexploited capabilities;
- formulate a measurable improvement hypothesis;
- inspect the relevant code and dependencies;
- create a separate branch or sandbox experiment;
- implement the smallest reversible change;
- add tests before changing production behaviour;
- compare against a baseline for accuracy, reliability, latency, cost, security, and human impact;
- produce a change report with evidence and rollback instructions;
- promote only after required approvals and tests.

The system may autonomously read, analyze, draft, test, and modify isolated development branches within granted scopes. Production deployments, privilege expansion, external financial commitments, publication of allegations, and irreversible actions require specific approval. General permission to continue is not blanket authorization for every high-impact action.

## 6. Continuous operation architecture

Implement a durable job architecture rather than relying on one uninterrupted process:
- scheduler for periodic scans and user-defined research cycles;
- durable queue with idempotent jobs, checkpoints, retries with backoff, and dead-letter handling;
- workers separated by task class (research, coding, evaluation, translation, monitoring);
- persistent project memory and provenance store;
- resource manager for compute, storage, API quotas, and cost ceilings;
- health monitoring, audit logs, alerts, and graceful shutdown/restart;
- pause, resume, cancel, and priority controls;
- human review gates for sensitive or high-impact work.

"24/7" means the system can continue scheduled work when infrastructure, credentials, quotas, and budget are available. It does not mean unlimited compute, guaranteed access to every source, perfect knowledge, or uninterrupted service. On quota exhaustion or provider outage, jobs pause safely and resume from checkpoints.

## 7. ARIS — Gaza Atrocity Documentation and Arms-Network Observatory

**Working label:** ARIS, pending confirmation of the exact prior project name and charter.  
**Purpose:** create a rigorous, source-transparent observatory documenting alleged international crimes affecting Gaza and investigating the end-to-end networks that enable weapons production, transfer, financing, and use. The system must document evidence and institutional relationships, not produce unsupported verdicts or personal attacks.

### 7.1 Two linked evidence tracks

**Track A — Incident and harm documentation**
- time, location, incident description, affected civilian objects and persons where safely and lawfully documented;
- source files, original URLs, publication timestamps, geolocation confidence, and chain of custody;
- satellite imagery, verified video/photo, witness accounts, medical records, official statements, and forensic/technical analysis where lawfully available;
- event chronology, corroboration, contradictions, alternative explanations, and confidence levels;
- applicable legal frameworks and clearly attributed findings by competent bodies;
- strict privacy, informed-consent, trauma-aware handling, and protection of witnesses and survivors.

**Track B — Weapons lifecycle and enabling-network tracing**
Map the documented chain from:
1. concept, research, design, and intellectual property;
2. raw materials, mining, refining, and chemical/metallurgical inputs;
3. component manufacturers and sub-tier suppliers;
4. assembly, integration, testing, and certification;
5. brokers, distributors, export licences, and government approvals;
6. shipping, freight forwarders, ports, routes, insurers, and logistics providers;
7. prime contractors, subcontractors, and end users;
8. banks, lenders, bond underwriters, asset managers, pension funds, insurers, and other investors;
9. corporate ownership, board governance, lobbying, political donations, procurement decisions, and public policy;
10. maintenance, upgrades, spare parts, software, targeting systems, and post-sale support.

Each relationship must be represented as a sourced, time-bounded edge in a graph: entity A — relationship — entity B, with source, date, jurisdiction, confidence, and caveat. Distinguish direct supply from indirect exposure, investment from control, lawful commercial activity from a legally established violation, and allegation from adjudicated fact.

### 7.2 Evidence and legal safeguards

- Use public records and lawfully obtained material; do not hack, trespass, steal credentials, solicit classified information, or endanger sources.
- Preserve originals, cryptographic hashes, metadata, collection logs, access history, and chain-of-custody records.
- Corroborate high-impact claims with multiple genuinely independent sources whenever possible.
- Maintain a claim ledger with status: unverified lead, corroborated fact, contested claim, expert assessment, official allegation, formal finding, or final adjudication.
- Never infer criminal intent, complicity, or individual guilt from employment, nationality, religion, political identity, shareholding alone, or mere association.
- For named people, require a high evidentiary threshold, public-interest justification, precise attribution, right-of-reply workflow where appropriate, and legal review before publication.
- Do not publish private addresses, personal contact details, family information, or other data that could enable harassment or physical harm.
- Separate advocacy language from evidence records. The observatory can communicate the human consequences of documented events without altering, embellishing, or decontextualizing evidence.
- Protect witnesses, survivors, journalists, researchers, and vulnerable communities from retaliation and re-identification.

### 7.3 Outputs

- searchable incident timeline and evidence catalogue;
- interactive supply-chain and financial-network graph;
- company, contract, shipment, licence, and investment profiles;
- traceable reports showing the source behind every material claim;
- uncertainty and missing-link maps;
- periodic change alerts when ownership, contracts, financing, sanctions, export licences, or public findings change;
- reproducible research packages for journalists, legal teams, investigators, and human-rights organizations.

### 7.4 Acceptance tests

1. Every material factual claim resolves to a source record.
2. Source copies and syndications are not miscounted as independent corroboration.
3. Direct and indirect links are visibly distinguished.
4. Financial exposure is not misrepresented as operational control or criminal complicity.
5. Allegations are not presented as court findings.
6. Conflicting evidence and uncertainty remain visible.
7. Sensitive witness information is access-controlled and excluded from public exports.
8. Every published named-person claim passes attribution and legal-review gates.
9. No automated system independently declares a person or company guilty.
10. Reports can be reproduced from preserved source records and documented methods.
11. Updates retain historical versions and do not silently rewrite prior findings.
12. The system can pause publication when provenance, safety, or legal review is incomplete.

## 8. Integration with FlyBrain frameworks

This architecture should connect to:
- Sun Tzu doctrine for situational awareness, evidence quality, adaptation, resource preservation, and conflict minimization;
- MSR for bounded initiative, provider resilience, and staged change;
- Strategic Intelligence Governance for provenance, source independence, and anti-manipulation;
- Rhetoric Defense for identifying narrative manipulation without attributing it to identity groups;
- URCAL for policy enforcement, quotas, auditability, and provider-neutral execution;
- Cognee or equivalent memory for durable, source-linked knowledge;
- scheduled workers and durable queues for continuous research and revalidation.

## 9. Phased implementation

**Phase 1 — Foundations:** capability registry schema, learning-plan schema, source/provenance model, job/checkpoint model, and ARIS evidence ontology.

**Phase 2 — Working prototype:** one bounded learning workflow, one sandbox skill evaluation, durable scheduled jobs, and a small ARIS public-record pilot.

**Phase 3 — Validation:** reproducible benchmarks, chain-of-custody workflow, privacy/security review, human review, and independent evaluation.

**Phase 4 — Controlled expansion:** add domains, languages, sources, skills, and workers based on measured value and available resources.

## 10. Current implementation boundary

This document is a specification only. It does not claim that continuous workers, autonomous skill acquisition, self-modifying production runtime, or the ARIS observatory have been deployed. The exact historical ARIS charter was not recovered during this repository check; the ARIS label and scope above are therefore provisional and must be reconciled with the original project materials before public launch.
