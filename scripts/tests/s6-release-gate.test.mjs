import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { REQUIRED_GATES, validate } from '../s6-release-gate.mjs';

const runUrl = 'https://github.com/karimnour920501-blip/black-K92NN-Wolf/actions/runs/40996051123';
const issueUrl = 'https://github.com/karimnour920501-blip/black-K92NN-Wolf/issues/24';
const candidate = 'a'.repeat(40);

function syntheticComplete() {
  return {
    schema_version: 1, sprint: 'S6', release: 'Mobile MVP v1.0',
    candidate_commit: candidate,
    gates: Object.fromEntries(REQUIRED_GATES.map(name => [
      name, {
        status: 'passed',
        evidence: name.startsWith('e2e_') ? [runUrl, issueUrl] : [runUrl],
        ...(name.startsWith('e2e_') ? { platforms: ['android', 'ios'] } : {}),
        ...(name === 'zero_critical_defects' ? { open_critical: 0 } : {})
      }
    ]))
  };
}

test('a complete synthetic manifest passes schema validation only', () => {
  const r = validate(syntheticComplete(), { expectedSha: candidate });
  assert.deepEqual(r, { ok: true, errors: [] });
});

test('pending gates block release regardless of code quality', () => {
  const record = syntheticComplete();
  record.gates.ios_build.status = 'pending';
  const r = validate(record, { expectedSha: candidate });
  assert.equal(r.ok, false);
  assert.match(r.errors.join('\n'), /ios_build: not passed/);
});

test('missing gates and incorrect source SHA fail closed', () => {
  const record = syntheticComplete();
  delete record.gates.rbac;
  const r = validate(record, { expectedSha: 'b'.repeat(40) });
  assert.equal(r.ok, false);
  assert.match(r.errors.join('\n'), /rbac: missing gate/);
  assert.match(r.errors.join('\n'), /Candidate commit does not match/);
});

test('URL placeholders or untrusted evidence do not satisfy evidence gate', () => {
  const record = syntheticComplete();
  record.gates.manual_qa.evidence = ['https://example.com/fake'];
  const r = validate(record, { expectedSha: candidate });
  assert.equal(r.ok, false);
  assert.match(r.errors.join('\n'), /manual_qa: needs one or more trusted/);
});

test('E2E record without both platforms or sufficient artifacts cannot pass', () => {
  const record = syntheticComplete();
  record.gates.e2e_05.platforms = ['android'];
  record.gates.e2e_05.evidence = [runUrl];
  const r = validate(record, { expectedSha: candidate });
  assert.equal(r.ok, false);
  assert.match(r.errors.join('\n'), /e2e_05: needs separate Android and iOS/);
  assert.match(r.errors.join('\n'), /e2e_05: needs at least two/);
});

test('critical defects cannot be marked passed with nonzero open criticals', () => {
  const record = syntheticComplete();
  record.gates.zero_critical_defects.open_critical = 1;
  assert.match(validate(record).errors.join('\n'), /open_critical must equal 0/);
});

test('checked-in release evidence manifest remains blocked', () => {
  const r = spawnSync(process.execPath, [
    new URL('../s6-release-gate.mjs', import.meta.url).pathname,
    new URL('../../mobile/s6/release-evidence.json', import.meta.url).pathname
  ], { encoding: 'utf8' });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /S6 RELEASE BLOCKED/);
});
