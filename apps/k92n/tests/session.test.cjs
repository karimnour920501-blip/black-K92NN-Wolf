'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
// A deterministic DOM/fetch double exercises the actual UI module's event handlers.
test('superseded connection cannot clear a newer operator session',async()=>{
 const nodes=new Map();
 function element(){return {value:'',textContent:'',hidden:true,disabled:false,required:false,children:[],reset(){},append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items}}}
 const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
 let statusCalls=0,aborts=0;
 const fetch=async(url,options)=>{
  if(url==='/api/status'&&++statusCalls===1)return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{aborts++;reject(new DOMException('Superseded','AbortError'))},{once:true}));
  const data=url==='/api/status'?{version:'test'}:[];
  return {ok:true,json:async()=>data};
 };
 const source=fs.readFileSync(path.join(__dirname,'../src/K92N.Host/wwwroot/app.js'),'utf8').replace(/^import .*\n/,'');
 const context=vm.createContext({document:{getElementById:get,querySelectorAll:()=>[],createElement:element},window:{addEventListener(){}},AbortController,DOMException,fetch,console});
 vm.runInContext(source,context);
 get('token').value='first-synthetic-token';const first=get('connectForm').onsubmit({preventDefault(){}});
 assert.equal(statusCalls,1);
 get('token').value='second-synthetic-token';const second=get('connectForm').onsubmit({preventDefault(){}});
 await Promise.all([first,second]);
 assert.equal(aborts,1);assert.equal(statusCalls,2);
 assert.equal(get('workspace').hidden,false);
 assert.match(get('status').textContent,/test/);
 assert.equal(get('token').value,'');
});
