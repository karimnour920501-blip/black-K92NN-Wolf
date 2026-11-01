/**
 * Dependency-free (beyond existing TypeScript) AST source linter for the S1 Expo app.
 * Not a substitute for TypeScript or a complete ESLint/react-native rule set.
 * ```npm run lint``` enforces a deliberately narrow, reproducible security and A11y policy.
 */
import ts from 'typescript';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../', import.meta.url));
const IGNORED = new Set(['node_modules', '.expo', 'dist', 'web-build']);
const EXTENSIONS = new Set(['.ts', '.tsx']);
const SENSITIVE_WIDGETS = new Set(['Pressable', 'TouchableOpacity', 'TouchableHighlight', 'TextInput']);

function walk(path) {
  const files = [];
  for (const entry of readdirSync(path, { withFileTypes: true })) {
    if (IGNORED.has(entry.name)) continue;
    const absolute = join(path, entry.name);
    if (entry.isDirectory()) files.push(...walk(absolute));
    else if (entry.isFile() && (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) &&
             !entry.name.endsWith('.d.ts')) files.push(absolute);
  }
  return files;
}

function hasJsxAttribute(node, name) {
  return node.attributes.properties.some(
    p => ts.isJsxAttribute(p) && p.name.text === name
  );
}

export function lintText(filename, content) {
  const source = ts.createSourceFile(
    filename, content, ts.ScriptTarget.Latest, true,
    filename.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  );
  const issues = [];
  function report(node, rule) {
    const { line, character } = source.getLineAndCharacterOfPosition(node.getStart(source));
    issues.push({ line: line + 1, column: character + 1, rule });
  }

  for (const d of source.parseDiagnostics)
    issues.push({ line: source.getLineAndCharacterOfPosition(d.start || 0).line + 1,
                  column: 1, rule: 'syntax-error:' + d.code });
  if (/@ts-(ignore|nocheck)/.test(content))
    issues.push({ line: 1, column: 1, rule: 'no-typescript-check-bypass' });

  function visit(node) {
    if (node.kind === ts.SyntaxKind.AnyKeyword) report(node, 'no-explicit-any');
    if (node.kind === ts.SyntaxKind.DebuggerStatement) report(node, 'no-debugger');
    if (ts.isCallExpression(node)) {
      if (ts.isIdentifier(node.expression) && node.expression.text === 'eval')
        report(node, 'no-eval');
      if (ts.isPropertyAccessExpression(node.expression) &&
          ts.isIdentifier(node.expression.expression) &&
          node.expression.expression.text === 'console' &&
          ['log', 'debug', 'info'].includes(node.expression.name.text))
        report(node, 'no-client-console-logging');
    }
    if (ts.isNewExpression(node) && ts.isIdentifier(node.expression) &&
        node.expression.text === 'Function') report(node, 'no-dynamic-function');
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
        ts.isIdentifier(node.tagName) && SENSITIVE_WIDGETS.has(node.tagName.text)) {
      if (!hasJsxAttribute(node, 'accessibilityRole'))
        report(node, 'interactive-element-needs-role');
      if (node.tagName.text === 'TextInput' && !hasJsxAttribute(node, 'accessibilityLabel'))
        report(node, 'text-input-needs-label');
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  return issues;
}

export function lintDirectory(root = ROOT) {
  const files = [...walk(join(root, 'app')), ...walk(join(root, 'src'))];
  if (files.length === 0) throw new Error('No Expo TypeScript source files found');
  const errors = [];
  for (const file of files)
    for (const result of lintText(file, readFileSync(file, 'utf8')))
      errors.push({ path: relative(root, file), ...result });
  return { count: files.length, errors };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(new URL('file://' + process.argv[1]))) {
  const { count, errors } = lintDirectory();
  for (const e of errors)
    console.error(e.path + ':' + e.line + ':' + e.column + ': ' + e.rule);
  console.log('TypeScript AST lint: ' + count + ' files checked, ' + errors.length + ' issues');
  if (errors.length) process.exitCode = 1;
}
