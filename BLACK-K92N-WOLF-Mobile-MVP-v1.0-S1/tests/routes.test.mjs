import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
const root=new URL('../',import.meta.url);
test('all five tab routes and splash exist',()=>{for(const p of ['app/index.tsx','app/_layout.tsx','app/(tabs)/_layout.tsx',...['home','projects','commands','evidence','settings'].map(x=>`app/(tabs)/${x}.tsx`)]) assert.ok(existsSync(new URL(p,root)),p);});
test('splash never fabricates authenticated session',()=>{const splash=readFileSync(new URL('app/index.tsx',root),'utf8');assert.match(splash,/unauthorized/);assert.match(splash,/التجريبية/);assert.doesNotMatch(splash,/SecureStore\.setItem/);});
test('every tab is declared in navigation',()=>{const layout=readFileSync(new URL('app/(tabs)/_layout.tsx',root),'utf8');for(const route of ['home','projects','commands','evidence','settings'])assert.ok(layout.includes(`name="${route}"`),route);});
