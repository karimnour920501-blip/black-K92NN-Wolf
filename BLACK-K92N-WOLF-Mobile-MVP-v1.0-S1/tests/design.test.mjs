import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const tokens=JSON.parse(readFileSync(new URL('../src/design/tokens.json',import.meta.url)));
test('royal design palette has expected canonical values',()=>{ assert.equal(tokens.colors.background,'#080B10'); assert.equal(tokens.colors.gold,'#C7A45A'); assert.equal(tokens.touchTarget,44); });
test('spacing is monotonic and divisible by four',()=>{ assert.equal(tokens.spacing[0],0); for(let i=1;i<tokens.spacing.length;i++){ assert.ok(tokens.spacing[i]>tokens.spacing[i-1]); assert.equal(tokens.spacing[i]%4,0); }});
test('all colors use 6 digit hex codes',()=>{ for(const c of Object.values(tokens.colors)) assert.match(c,/^#[0-9A-F]{6}$/); });
function lum(hex){const rgb=hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(c=>c<=0.04045?c/12.92:((c+0.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;}
function contrast(a,b){const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);}
test('primary and secondary text meet WCAG AA normal-text contrast',()=>{for(const fg of [tokens.colors.text,tokens.colors.muted]) assert.ok(contrast(fg,tokens.colors.background)>=4.5,fg);});
