#!/usr/bin/env node
"use strict";

const fs = require("node:fs");

const normalize = (value) => {
  const status = String(value || "skipped").toLowerCase();
  if (["success", "failure", "cancelled", "skipped"].includes(status)) return status;
  return "skipped";
};
const env = process.env;
const checkout = normalize(env.CHECKOUT);
const restore = normalize(env.RESTORE);
const stages = {
  restore: checkout === "success" ? restore : checkout === "failure" ? "failure" : "skipped",
  build: normalize(env.BUILD),
  tests: normalize(env.TESTS),
};
const complete = Object.values(stages).every((value) => value === "success");
const gateIds = (env.GATES || "G1,G2,G3,G4,G5,G6,G7")
  .split(",").map((id) => id.trim()).filter(Boolean);
const gates = Object.fromEntries(gateIds.map((id) => [
  id,
  { state: complete ? "blocked" : "not_measurable", evidence: null },
]));
const state = {
  schema_version: "1.0",
  run: {
    id: env.RUN_ID || "",
    commit: env.COMMIT || "",
    branch: env.BRANCH || "",
    timestamp: env.TIMESTAMP || new Date().toISOString(),
  },
  stages,
  gates,
  verified: false,
  notes: complete
    ? "المراحل اكتملت؛ البوابات محجوبة بانتظار أدلة مرتبطة ومتحقق منها."
    : "فشلت أو تخطت مرحلة؛ البوابات غير قابلة للقياس.",
};
const destination = env.GATES_OUTPUT || "gates.json";
fs.writeFileSync(destination, JSON.stringify(state, null, 2) + "\n");
console.log(JSON.stringify(state, null, 2));
