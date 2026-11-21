# FASE Clean-Room Functional Replication and IP Compliance Policy

**Status:** staging governance specification.
**Applies to:** FlyBrain Autonomous Service Ecosystem (FASE), URCAL, adapters, plugins, workflows, dependencies, and deployment artifacts.

## 1. Foundational rule

FASE may independently implement a function or workflow only through a lawful design that respects protected expression, valid patent claims, trade secrets, trademarks, database rights, licences, and contractual restrictions. The objective is functional capability, not copying a competitor's protected implementation.

Changing names, colors, layout, or variable names does not by itself make a copy lawful. Rewriting code does not by itself avoid patent infringement, trade-secret misuse, or contractual violations. If the legal basis is uncertain, quarantine the candidate, select a materially different design, or seek qualified legal review.

This is an engineering policy, not a legal opinion or guarantee. Legal assessments depend on jurisdiction, claims, facts, dates, and applicable law.

## 2. Preferred engineering routes

1. Independently define neutral functional requirements and objective acceptance criteria.
2. Use a genuine clean-room implementation where appropriate: separate functional analysis from implementation, and provide implementers only an independently written specification.
3. Use published standards and documented APIs within their terms, access controls, and applicable law.
4. Reuse open-source components only after verifying the exact licence and satisfying its obligations.
5. If a method or implementation is restricted, design a technically distinct alternative that achieves the required outcome.
6. Use a legitimately licensed service only where necessary and after authorization and cost approval.

Never use leaked code, stolen credentials, confidential documentation obtained without authorization, or deceptive access methods.

## 3. Required rights review

Review every candidate for copyright, patent exposure, trade secrets, trademarks, design rights, database and dataset rights, software/model licences, API terms, privacy, and data-protection obligations.

A public URL or downloadable package is not proof of permission to reuse it. Record the source, licence version, SPDX identifier where available, attribution and notice obligations, modification obligations, source-disclosure requirements, redistribution limits, and intended deployment jurisdictions.

## 4. Clean-room workflow

1. Describe the desired capability in neutral functional language.
2. Record the sources used to define requirements and classify each as public, licensed, user-owned, or restricted.
3. Exclude proprietary code, leaked material, and confidential implementation details from the clean-room specification.
4. Have an independent reviewer check that the specification describes outcomes and standards rather than protected expression.
5. Implement from the clean-room specification and independently selected lawful references.
6. Record design decisions, authorship, dependencies, and code provenance.
7. Run similarity, dependency, secret, and licence scans as risk signals; automated scans do not establish legal clearance.
8. Review relevant patent claims and obtain qualified counsel where exposure is material or uncertain.
9. Test functionality and security against independently authored acceptance criteria.
10. Record the approval decision and rationale.

Clean-room separation must be genuine, not a paper exercise used to disguise copying or transfer confidential material.

## 5. Component compliance record

Each component record must include component ID and version; maintainer and source URL; retrieval date; component type; licence name and text/version; SPDX identifier where available; provenance; restricted-material access declaration; relevant rights review states; intended jurisdictions and distribution model; modifications; dependency and security scan references; reviewer and review date; decision and rationale; permitted uses; obligations; and next review date.

Review states: unreviewed, in_review, approved, approved_with_conditions, rejected, quarantined, expired.

Unknown provenance or licence is not approval.

## 6. Fail-closed decision gate

- approved: usable within the recorded scope.
- approved_with_conditions: usable only after all listed conditions are enforced.
- unreviewed, in_review, expired: blocked from release and production.
- rejected, quarantined: blocked and isolated until resolved.

Material changes to version, licence, ownership, distribution, hosting, or intended use trigger re-review. An automated scanner cannot override a blocked review state.

## 7. API and service emulation boundaries

A compatibility layer may expose provider-neutral interfaces and independently designed behavior. It must not bypass authentication, payment, quotas, rate limits, or access controls; impersonate a provider; abuse undocumented private endpoints; copy protected code or proprietary content; reproduce confusing branding; or claim compatibility beyond verified tests.

Use original names, documentation, branding, and user experience. Disclose material differences.

## 8. Escalation and remediation

Escalate material patent questions, disputed ownership, reverse-engineering or interoperability exceptions, database rights, and jurisdiction-specific uncertainty to qualified IP counsel. A design-around note is not legal clearance.

If a concern is raised, stop new distribution or deployment, preserve provenance records, isolate the affected component, assess replacement/redesign/licensing/removal, and document verified remediation. Do not conceal the component's origin or destroy relevant evidence.

## 9. Acceptance criteria

1. Every third-party component has a provenance and licence record.
2. Unknown or incompatible licences block release.
3. Clean-room specifications contain functional requirements, not copied expression or confidential details.
4. No implementation relies on leaked or improperly obtained material.
5. API adapters respect authentication, quotas, rate limits, and documented access rules.
6. Provider branding and identity are not misrepresented.
7. Material patent concerns are escalated; rewriting code is not treated as patent clearance.
8. Compliance decisions are versioned and auditable.
9. Automated scans are treated as signals, not legal determinations.
10. Production promotion requires completed compliance review and separate deployment authorization.

**Current status:** the policy specification and a fail-closed engineering evidence evaluator are present on staging. The evaluator does not perform legal clearance, patent searches, or grant licence approval; human review and qualified counsel remain necessary where indicated.
