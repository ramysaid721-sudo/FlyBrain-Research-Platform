const CONTROL_URL =
  "https://zjhzfjzadrpsbfphxgjw.supabase.co/functions/v1/flybrain-control";
const SANDBOX_NAME = "flybrain-worker-staging";
const REPOSITORY = "https://github.com/ramysaid721-sudo/FlyBrain-Research-Platform";
const BRANCH = "flybrain-browser-worker-staging";
const PROJECT_ID = "prj_t8lRtZksDIniAxwjdc5NvuXGSyiX";
const TEAM_ID = "team_A93FQsqKOuw7ixNR784ufHzZ";

async function control(token, payload) {
  const response = await fetch(CONTROL_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-flybrain-token": token,
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok !== true) {
    const error = new Error(`Control plane ${payload.action} failed: HTTP ${response.status}`);
    error.statusCode = response.status;
    throw error;
  }
  return data.result;
}

async function failClaim(token, executionId, leaseToken, error) {
  if (!executionId || !leaseToken) return;
  try {
    await control(token, {
      action: "fail",
      execution_id: executionId,
      lease_token: leaseToken,
      error: String(error).slice(0, 900),
    });
  } catch (_) {
    // The lease watchdog will recover the task if the control plane is unavailable.
  }
}

async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "method_not_allowed" });
  }

  const token = req.headers["x-flybrain-token"];
  if (typeof token !== "string" || token.length < 40) {
    return res.status(401).json({ error: "unauthorized" });
  }

  let claim;
  let sandbox;
  let executionId;
  let leaseToken;
  let completed = false;

  try {
    claim = await control(token, {
      action: "claim",
      worker_id: "vercel-sandbox-dispatcher",
      lease_seconds: 300,
    });

    if (!claim || claim.claimed !== true) {
      return res.status(204).end();
    }

    executionId = claim.execution_id;
    leaseToken = claim.lease_token;
    if (!executionId || !leaseToken || !claim.task) {
      throw new Error("Claim response is missing its lease or task payload");
    }

    const { Sandbox } = await import("@vercel/sandbox");
    sandbox = await Sandbox.getOrCreate({
      name: SANDBOX_NAME,
      teamId: TEAM_ID,
      projectId: PROJECT_ID,
      region: "sin1",
      resources: { vcpus: 1 },
      timeout: 60000,
      persistent: true,
      networkPolicy: {
        mode: "custom",
        allowedDomains: [
          "github.com",
          "api.github.com",
          "raw.githubusercontent.com",
          "zjhzfjzadrpsbfphxgjw.supabase.co",
        ],
      },
    });

    const command = await sandbox.runCommand({
      cmd: "bash",
      args: [
        "-lc",
        [
          "set -e",
          "if [ ! -d /vercel/FlyBrain-Research-Platform/.git ]; then",
          `  git clone --depth 1 --branch ${BRANCH} ${REPOSITORY} /vercel/FlyBrain-Research-Platform`,
          "else",
          `  cd /vercel/FlyBrain-Research-Platform && git fetch origin ${BRANCH} && git checkout -B ${BRANCH} FETCH_HEAD`,
          "fi",
          "cd /vercel/FlyBrain-Research-Platform",
          "python3 worker/flybrain_worker.py",
        ].join("\n"),
      ],
      cwd: "/vercel",
      env: {
        FLYBRAIN_CONTROL_URL: CONTROL_URL,
        FLYBRAIN_WORKER_TOKEN: token,
        FLYBRAIN_TASK_JSON: JSON.stringify(claim.task),
        FLYBRAIN_EXECUTION_ID: executionId,
        FLYBRAIN_LEASE_TOKEN: leaseToken,
        PYTHONUNBUFFERED: "1",
      },
      timeoutMs: 40000,
    });

    const stdout = await command.stdout();
    const stderr = await command.stderr();
    if (command.exitCode !== 0) {
      throw new Error(`Worker exited ${command.exitCode}: ${String(stderr || stdout).slice(0, 700)}`);
    }

    completed = true;
    return res.status(200).json({
      ok: true,
      worker: "vercel-sandbox",
      task_id: claim.task.id,
      execution_id: executionId,
      result: String(stdout || "").slice(0, 1200),
    });
  } catch (error) {
    if (!completed) {
      await failClaim(token, executionId, leaseToken, error && error.message ? error.message : error);
    }
    return res.status(error && error.statusCode === 401 ? 401 : 500).json({
      ok: false,
      error: "worker_dispatch_failed",
      detail: String(error && error.message ? error.message : error).slice(0, 500),
    });
  } finally {
    if (sandbox) {
      try {
        await sandbox.stop();
      } catch (_) {
        // Persistent snapshots are best-effort; lease recovery remains authoritative.
      }
    }
  }
}

module.exports = handler;
module.exports.config = { maxDuration: 60 };
