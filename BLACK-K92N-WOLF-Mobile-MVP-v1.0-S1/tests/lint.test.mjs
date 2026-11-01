import test from 'node:test';
import assert from 'node:assert/strict';
import { lintText, lintDirectory } from '../scripts/lint.mjs';

test('real Expo source meets narrow TypeScript AST lint rules', () => {
  const result = lintDirectory();
  assert.ok(result.count >= 10, 'must inspect actual TS/TSX app and components');
  assert.deepEqual(result.errors, []);
});

test('rejects console logging potentially sensitive app data', () => {
  assert.ok(lintText('x.ts', 'console.log(token);').some(i => i.rule === 'no-client-console-logging'));
});

test('rejects explicit any and TypeScript suppression', () => {
  assert.ok(lintText('x.ts', 'const x: any = 1;').some(i => i.rule === 'no-explicit-any'));
  assert.ok(lintText('x.ts', '// @ts-ignore\nconst x = 1').some(i => i.rule === 'no-typescript-check-bypass'));
});

test('rejects an unlabelled interactive React Native JSX widget', () => {
  const issues = lintText('x.tsx', 'const X = () => <Pressable onPress={() => {}} />;');
  assert.ok(issues.some(i => i.rule === 'interactive-element-needs-role'));
});

test('accepts labelled widgets and rejects text input missing an accessible label', () => {
  assert.deepEqual(lintText('x.tsx', 'const X = () => <TextInput accessibilityRole="text" accessibilityLabel="Name" />;'), []);
  assert.ok(lintText('x.tsx', 'const X = () => <TextInput accessibilityRole="text" />;')
    .some(i => i.rule === 'text-input-needs-label'));
});

test('rejects eval, dynamic Function and debugger', () => {
  const issues = lintText('x.ts', 'eval(input); new Function(input); debugger;');
  assert.ok(issues.some(i => i.rule === 'no-eval'));
  assert.ok(issues.some(i => i.rule === 'no-dynamic-function'));
  assert.ok(issues.some(i => i.rule === 'no-debugger'));
});
