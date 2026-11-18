"use strict";

const http = require("node:http");
const crypto = require("node:crypto");
const { spawn } = require("node:child_process");
const path = require("node:path");

const PORT = Number(process.env.PORT || 10000);
const ROOT = path.resolve(__dirname, "..");
const CONFIG = path.join(ROOT, "cloudflare-staging", "wrangler.jsonc");
const EXPECTED_WORKER = "flybrain-research-platform-staging";
const MAX_LOG_CHARS = 12000;
const jobs = new Map();
let activeJob = null;

function configured() {
  return Boolean(
    process.env.BRIDGE_ACCESS_TOKEN &&
    process.env.CLOUDFLARE_API_TOKEN &&
    process.env.CLOUDFLARE_ACCOUNT_ID
  );
}

function send(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store",
    "x-content-type-options": "nosniff"
  });
  res.end(payload);
}

function authorized(req) {
  const expected = process.env.BRIDGE_ACCESS_TOKEN || "";
  const header = req.headers.authorization || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!expected || !supplied) return false;
  const a = Buffer.from(expected);
  const b = Buffer.from(supplied);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", chunk => {
      data += chunk;
      if (Buffer.byteLength(data) > 4096) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      if (!data) return resolve({});
      try { resolve(JSON.parse(data)); }
      catch { reject(new Error("Invalid JSON")); }
    });
    req.on("error", reject);
  });
}

function runDeploy(job) {
  if (activeJob) return false;
  activeJob = job.id;
  job.status = "running";
  job.startedAt = new Date().toISOString();

  const child = spawn("npx", [
    "--yes",
    "wrangler@4",
    "deploy",
    "--config",
    "cloudflare-staging/wrangler.jsonc"
  ], {
    cwd: ROOT,
    env: {
      ...process.env,
      CLOUDFLARE_API_TOKEN: process.env.CLOUDFLARE_API_TOKEN,
      CLOUDFLARE_ACCOUNT_ID: process.env.CLOUDFLARE_ACCOUNT_ID,
      CI: "1"
    },
    shell: false,
    windowsHide: true
  });

  let output = "";
  const append = chunk => {
    output = (output + chunk.toString()).slice(-MAX_LOG_CHARS);
    job.output = output;
  };
  child.stdout.on("data", append);
  child.stderr.on("data", append);
  child.on("error", err => {
    job.status = "failed";
    job.error = err.message;
    job.finishedAt = new Date().toISOString();
    activeJob = null;
  });
  child.on("close", code => {
    job.status = code === 0 ? "succeeded" : "failed";
    job.exitCode = code;
    job.finishedAt = new Date().toISOString();
    activeJob = null;
  });
  return true;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");

  if (req.method === "GET" && url.pathname === "/health") {
    return send(res, 200, {
      status: "ok",
      service: "flybrain-cloudflare-staging-bridge",
      configured: configured(),
      cloudflareTokenConfigured: Boolean(process.env.CLOUDFLARE_API_TOKEN),
      cloudflareAccountConfigured: Boolean(process.env.CLOUDFLARE_ACCOUNT_ID),
      bridgeAuthenticationConfigured: Boolean(process.env.BRIDGE_ACCESS_TOKEN),
      targetWorker: EXPECTED_WORKER
    });
  }

  if (!authorized(req)) {
    return send(res, 401, { error: "Unauthorized" });
  }

  if (req.method === "POST" && url.pathname === "/deploy") {
    if (!configured()) {
      return send(res, 503, {
        error: "Deployment secrets are not configured",
        required: ["BRIDGE_ACCESS_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"]
      });
    }
    if (activeJob) return send(res, 409, { error: "A deployment is already running", jobId: activeJob });

    const job = {
      id: crypto.randomUUID(),
      status: "queued",
      createdAt: new Date().toISOString(),
      targetWorker: EXPECTED_WORKER
    };
    jobs.set(job.id, job);
    runDeploy(job);
    return send(res, 202, { accepted: true, jobId: job.id, status: job.status });
  }

  if (req.method === "GET" && url.pathname.startsWith("/deploy/status/")) {
    const id = url.pathname.split("/").pop();
    const job = jobs.get(id);
    if (!job) return send(res, 404, { error: "Deployment job not found" });
    return send(res, 200, job);
  }

  if (req.method === "GET" && url.pathname === "/") {
    return send(res, 200, { service: "FlyBrain Cloudflare staging deployment bridge", targetWorker: EXPECTED_WORKER });
  }

  return send(res, 404, { error: "Not found" });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log("FlyBrain Cloudflare staging bridge listening on port " + PORT);
});
