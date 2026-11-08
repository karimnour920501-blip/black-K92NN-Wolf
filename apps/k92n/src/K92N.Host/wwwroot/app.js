'use strict';const $=x=>document.getElementById(x);let token='',projection=null;
async function request(path,body){if(!token)throw Error('أدخل رمز المشغّل أولًا');const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store'});const data=await r.json();if(!r.ok)throw Error(data.error||'HTTP '+r.status);return data}
function action(fn){return async()=>{try{$('message').textContent='';await fn()}catch(e){$('message').textContent=e.message}}}
$('connect').onclick=action(async()=>{token=$('token').value;$('token').value='';$('status').textContent=JSON.stringify(await request('status'),null,2)});
$('disconnect').onclick=()=>{token='';projection=null;$('token').value='';$('status').textContent='تم نسيان الرمز';$('output').textContent='';};
$('record').onclick=action(async()=>{const id=$('entity').value.trim(),text=$('text').value.trim();if(!id||!text)throw Error('المعرّف والنص مطلوبان');const event=await request('events',{kind:$('kind').value,entityId:id,payload:{text,status:'RECORDED'}});$('output').textContent=JSON.stringify(event,null,2);$('text').value=''});
$('replay').onclick=action(async()=>{projection=await request('replay');$('output').textContent=JSON.stringify(projection,null,2)});
$('integrity').onclick=action(async()=>{$('output').textContent=JSON.stringify(await request('integrity'),null,2)});
$('export').onclick=action(async()=>{if(!projection)throw Error('نفّذ إعادة البناء أولًا');const u=URL.createObjectURL(new Blob([JSON.stringify(projection,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='K92N-projection.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)});

$('exportEvents').onclick=action(async()=>{const events=await request('events');const u=URL.createObjectURL(new Blob([JSON.stringify(events,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='K92N-events.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)});
