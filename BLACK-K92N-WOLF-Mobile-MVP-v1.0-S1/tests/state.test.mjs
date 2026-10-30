import test from 'node:test';
import assert from 'node:assert/strict';
import { UI_STATES, describeState, classifyHttpStatus, canRetryAutomatically } from '../src/domain/ui-state.mjs';
test('all UI states are distinct and have safe Arabic descriptions', () => { assert.equal(UI_STATES.length, 9); assert.equal(new Set(UI_STATES).size, 9); for (const state of UI_STATES) { const d=describeState(state); assert.ok(d.title.length>3); assert.ok(d.detail.length>8); } });
test('HTTP error mapping is explicit and fail-closed', () => { for (const [code, state] of [[401,'unauthorized'],[403,'forbidden'],[404,'notFound'],[409,'conflict'],[429,'rateLimited'],[500,'serverError'],[503,'serverError']]) assert.equal(classifyHttpStatus(code),state); assert.equal(classifyHttpStatus(200),null); assert.equal(classifyHttpStatus(400),null); });
test('only safe reads may automatically retry server failures', () => { assert.equal(canRetryAutomatically('GET',503),true); assert.equal(canRetryAutomatically('HEAD',500),true); assert.equal(canRetryAutomatically('POST',503),false); assert.equal(canRetryAutomatically('DELETE',503),false); assert.equal(canRetryAutomatically('GET',403),false); });
test('unknown state is rejected', () => assert.throws(()=>describeState('verified'),RangeError));
