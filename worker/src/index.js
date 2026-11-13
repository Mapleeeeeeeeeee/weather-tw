// Triggers the deploy workflow with probe=true: the workflow checks CWA against the live site and only builds/deploys on change.
async function dispatch(env) {
  const res = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "weather-tw-cron",
    },
    body: JSON.stringify({ ref: env.REF, inputs: { probe: "true" } }),
  });
  if (res.status !== 204) throw new Error(`dispatch failed: ${res.status} ${await res.text()}`);
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },
  // GET /  -> manual trigger check (needs the same token, so it is not an open endpoint: only reports configuration)
  async fetch(_req, env) {
    return new Response(env.GITHUB_TOKEN ? "weather-tw-cron: token set\n" : "weather-tw-cron: GITHUB_TOKEN missing\n", { status: env.GITHUB_TOKEN ? 200 : 500 });
  },
};
