# Connect FlyBrain Browser Staging to Cloudflare Workers Builds

This is the preferred no-extra-CI-service deployment path. It connects the existing
Cloudflare Worker to this GitHub repository using Cloudflare's native Git integration.
It does not require adding a Cloudflare API token to GitHub Actions.

## Target (staging only)

- Git repository: `ramysaid721-sudo/FlyBrain-Research-Platform`
- Branch to watch: `flybrain-browser-worker-staging`
- Worker project root: `cloudflare-browser-staging`
- Wrangler Worker name: `flybrain-browser-staging`
- Wrangler config: `cloudflare-browser-staging/wrangler.jsonc`
- Deploy command: `npx wrangler deploy`
- Build command: leave empty (the Worker package has no compile/build step)

The Worker name in Cloudflare must exactly match the Wrangler `name` above.
Do not connect this staging Worker to the repository's `main` branch and do not
change or deploy any production Worker.

## One-time account authorization and connection

Cloudflare requires an account owner/member to authorize the GitHub App. This
OAuth/account authorization cannot be performed by a repository commit or by an
unauthenticated API call.

1. Sign in to the Cloudflare dashboard and open **Workers & Pages**.
2. Select the existing staging Worker named `flybrain-browser-staging`.
   If it does not exist, stop: create it as a staging-only Worker first; do not
   import/deploy the repository to a production Worker.
3. Open **Settings → Builds → Connect**.
4. Authorize the GitHub account when prompted and select
   `ramysaid721-sudo/FlyBrain-Research-Platform`.
5. Set the watched production/deploy branch to
   `flybrain-browser-worker-staging`.
6. Set the project root directory to `cloudflare-browser-staging`.
7. Leave the build command empty and use `npx wrangler deploy` as the deploy command.
8. Save the settings. The first deployment will be triggered by a subsequent push
   to the selected staging branch. Verify the resulting Worker URL and build status
   in Cloudflare and the GitHub commit checks.

## Security and cost guardrails

- Keep this connection scoped to the staging Worker and staging branch.
- Do not add secrets to Git, commit `.dev.vars`, or paste API tokens into issues/PRs.
- Keep Cloudflare Browser Run usage disabled until account limits and the free quota
  have been confirmed.
- Do not enable Browserless or configure a paid plan as part of this connection.
- Keep the existing Vercel Preview provider flags disabled until the Worker URL and
  authentication secret have been configured and tested.
- Do not merge PR #14 or alter production as part of this setup.

## Official documentation

- https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/
- https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/
- https://developers.cloudflare.com/workers/ci-cd/builds/configuration/
