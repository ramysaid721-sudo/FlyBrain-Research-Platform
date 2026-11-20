# Public Crossref Query Screening

## Enforcement points

The shared `supabase/functions/_shared/public_query_safety.ts` guard is called at three boundaries:

1. Direct MCP `research_search`, immediately before constructing the Crossref request.
2. MCP `task_submit` validation. Group submissions reuse this validation for every child query.
3. The task worker, immediately before its Crossref request. This is defense in depth if a legacy or alternate task-creation path ever places a query in the queue.

The worker and gateway import the same shared implementation so the pattern set and policy error remain consistent.

## Patterns screened

The current rules detect common forms of email addresses, private-key PEM headers, GitHub tokens, OpenAI-style keys, Stripe-style keys, Google API keys, AWS access-key IDs, Slack tokens, GitLab tokens, npm tokens, bearer tokens, JWT-like strings, and password/secret/API-key assignments.

Before matching, the guard checks the original query and up to two percent-decoded representations. This catches common URL-encoded and double-encoded variants of known patterns.

## Test

Run the unit tests with:

```sh
deno test supabase/functions/_shared/public_query_safety_test.ts
```

The tests cover ordinary bibliographic queries, known sensitive patterns, percent-encoded email variants, and the stable rejection error.

## Important limitations

This is a pattern-based safety filter, not a complete data-loss-prevention classifier. It cannot reliably identify every unpublished research idea, confidential passage, personal record, obfuscated secret, or novel credential format. The `data_classification=public` field is an explicit caller assertion for queued work, not proof that the query is public.

Do not send unpublished research, private records, credentials, or secrets to Crossref. A future stronger policy may require an explicit classification field on direct search requests and/or a reviewed DLP classifier. That would change the MCP input contract and must be handled as a separately reviewed API change.

## Deployment status

This change is committed to the security branch only. It has not been deployed to Supabase Staging or Production.
