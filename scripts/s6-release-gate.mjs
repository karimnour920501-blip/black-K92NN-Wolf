#!/usr/bin/env node
/**
 * BLACK-K92N-WOLF Mobile S6 fail-closed RELEASE EVIDENCE checker.
 * Checks record completeness, NOT authenticity of remote test claims.
 * Requires human review of every linked artifact before release approval.
 */
import { readFileSync } from 'node:fs';

export const REQUIRED_GATES = Object.freeze([
  'android_build', 'ios_build',
  ...Array.from({ length: 8 }, (_, n) => 'e2e_' + String(n + 1).padStart(2, '0')),
  'jwt_validation', 'rbac', 'tenant_isolation', 'accessibility',
  'rtl_ltr', 'ui_states', 'secure_logging', 'backend_authorization',
  'typescript', 'lint', 'unit_tests', 'integration_tests',
  'dependency_scan', 'manual_qa', 'zero_critical_defects',
  'pr_review'
]);

const SHA40 = /^[a-f0-9]{40}$/;
const REPO = 'karimnour920501-blip/black-K92NN-Wolf';
const TRUSTED_GITHUB = 'https://github.com/' + REPO + '/';
const TRUSTED_EXPO = 'https://expo.dev/';

function evidenceUrlValid(value) {
  if (typeof value !== 'string') return false;
  try {
    const u = new URL(value);
    if (u.protocol !== 'https:' || u.username || u.password) return false;
    if (u.href.startsWith(TRUSTED_GITHUB)) return !!u.pathname.slice(('/' + REPO + '/').length);
    if (u.href.startsWith(TRUSTED_EXPO)) return u.pathname.length > 12;
    return false;
  } catch { return false; }
}

export function validate(manifest, { expectedSha } = {}) {
  const errors = [];
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest))
    return { ok: false, errors: ['Invalid evidence manifest object'] };
  if (manifest.schema_version !== 1 || manifest.sprint !== 'S6' || manifest.release !== 'Mobile MVP v1.0')
    errors.push('Incorrect evidence schema/version/sprint');
  if (!SHA40.test(manifest.candidate_commit || ''))
    errors.push('Candidate commit must be a real 40-character hex commit SHA');
  if (expectedSha && manifest.candidate_commit !== expectedSha)
    errors.push('Candidate commit does not match the checked-out GitHub ref');
  if (!manifest.gates || typeof manifest.gates !== 'object' || Array.isArray(manifest.gates)) {
    errors.push('Missing gates object');
    return { ok: false, errors };
  }

  for (const name of REQUIRED_GATES) {
    const gate = manifest.gates[name];
    if (!gate || typeof gate !== 'object') {
      errors.push(name + ': missing gate');
      continue;
    }
    if (gate.status !== 'passed') {
      errors.push(name + ': not passed (' + String(gate.status || 'missing') + ')');
      continue;
    }
    if (!Array.isArray(gate.evidence) || gate.evidence.length === 0 ||
        !gate.evidence.every(e => evidenceUrlValid(e))) {
      errors.push(name + ': needs one or more trusted HTTPS evidence URLs');
    }
    if (name.startsWith('e2e_')) {
      if (!Array.isArray(gate.platforms) ||
          !['android', 'ios'].every(p => gate.platforms.includes(p))) {
        errors.push(name + ': needs separate Android and iOS device/emulator evidence');
      }
      if (!Array.isArray(gate.evidence) || gate.evidence.length < 2)
        errors.push(name + ': needs at least two linked artifacts (Android + iOS)');
    }
    if (name === 'zero_critical_defects' && gate.open_critical !== 0)
      errors.push(name + ': documented open_critical must equal 0');
  }
  for (const key of Object.keys(manifest.gates))
    if (!REQUIRED_GATES.includes(key)) errors.push('Unknown gate: ' + key);
  return { ok: errors.length === 0, errors };
}

if (process.argv[1] && new URL('file://' + process.argv[1]).href === import.meta.url) {
  const path = process.argv[2] || 'mobile/s6/release-evidence.json';
  try {
    const manifest = JSON.parse(readFileSync(path, 'utf8'));
    const result = validate(manifest, { expectedSha: process.env.GITHUB_SHA });
    if (!result.ok) {
      console.error('S6 RELEASE BLOCKED — no production or release-candidate approval.');
      for (const issue of result.errors) console.error('- ' + issue);
      process.exitCode = 1;
    } else {
      console.log('S6 EVIDENCE MANIFEST GATE PASSED (links and metadata only).');
      console.log('MANUAL SECURITY / QA / RELEASE APPROVAL IS STILL REQUIRED.');
    }
  } catch (err) {
    console.error('S6 RELEASE BLOCKED — missing or malformed evidence manifest: ' + (err.code || err.name));
    process.exitCode = 1;
  }
}
