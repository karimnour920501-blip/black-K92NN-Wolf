import {test} from 'node:test';import assert from 'node:assert/strict';
import {minor,money,identifier,csvCell} from '../src/K92N.Host/wwwroot/money.mjs';
test('decimal conversion is exact beyond binary safe integers',()=>{assert.equal(minor('10000000000000.00',2),'1000000000000000');assert.equal(money('9007199254740993',2),'90071992547409.93')});
test('reject excess precision without rounding',()=>assert.throws(()=>minor('1.001',2)));
test('reject negative, zero, exponent and locale ambiguity',()=>{for(const s of ['-1','0','1e2','1,23','Infinity','NaN'])assert.throws(()=>minor(s,2))});
test('JPY/SYP integer and KWD precision',()=>{assert.equal(minor('123',0),'123');assert.equal(minor('1.234',3),'1234');assert.throws(()=>minor('1.1',0))});
test('signed balances use exact formatted minor units',()=>{assert.equal(money('-2550',2),'-25.50');assert.equal(money('5',2),'0.05');assert.equal(money('0',0),'0')});
test('identifiers stay strings beyond safe integer range',()=>{assert.equal(identifier('9007199254740993'),'9007199254740993');for(const s of ['0','-1','1e3','9223372036854775808'])assert.throws(()=>identifier(s))});
test('CSV formula cells are escaped',()=>{for(const s of ['=1+1',' +SUM(A1:A2)','-1','@SUM(A1:A2)','\tcmd'])assert.ok(csvCell(s).startsWith('"\''));assert.equal(csvCell('a"b'),'"a""b"')});

test('Arabic keyboard digits normalize exactly without guessing separators',()=>{assert.equal(minor('١٢٥٫٥٠',2),'12550');assert.equal(minor('۱۲۵٫۵۰',2),'12550');assert.equal(identifier('٧'),'7');assert.throws(()=>minor('١٬٠٠٠',2))});
