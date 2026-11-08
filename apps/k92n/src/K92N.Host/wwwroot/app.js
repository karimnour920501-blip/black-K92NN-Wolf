import {minor,money,identifier,csvCell,decimalText} from './money.mjs';
const $=id=>document.getElementById(id);
const state={token:'',session:0,abort:new AbortController(),currencies:[],accounts:[],rows:[],next:null,customer:null,account:null,pending:null,busy:false};
const codes={UNAUTHORIZED:'رمز المشغّل غير صحيح؛ أعد الاتصال.',PRECISION_VIOLATION:'كسور المبلغ تتجاوز دقة العملة. لم يتم تقريب المبلغ.',NEGATIVE_AMOUNT:'المبلغ السالب غير مسموح.',PERIOD_LOCKED:'الفترة مقفلة. اختر تاريخًا مفتوحًا.',INVALID_REQUEST:'راجع الحقول والمعرّفات والمبلغ.',UNKNOWN_CURRENCY:'العملة غير مسجلة.',IDEMPOTENCY_CONFLICT:'المفتاح مرتبط بمحتوى مختلف. افحص العملية السابقة.',ALREADY_REVERSED:'سبق عكس هذا القيد.',STORAGE_REJECTED:'رفضت قاعدة البيانات العملية؛ تحقق من الحسابات وعدم تكرار رقم الحساب أو رمزه.',INVALID_LINE:'بيانات السطر غير صالحة.',BUSY:'الخادم مشغول. أعد المحاولة.'};
class ApiError extends Error{constructor(code,status){super(codes[code]||('رفض الخادم العملية: '+code));this.status=status}}
class Stale extends Error{}
let lookupVersion=0;
function newKey(){if(typeof crypto.randomUUID!=='function')throw Error('يلزم HTTPS أو localhost لإنشاء مفتاح عملية آمن.');return crypto.randomUUID()}
function message(text){$('message').textContent=text}
function today(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
$('entryDate').value=today();$('reverseDate').value=today();
function controls(){for(const f of document.querySelectorAll('.write-fields'))f.disabled=state.busy||!!state.pending;$('pendingNotice').hidden=!state.pending;$('retry').disabled=state.busy}
async function api(path,body){
 if(!state.token)throw Error('اتصل برمز المشغّل أولًا.');
 const session=state.session,token=state.token,signal=state.abort.signal;
 const r=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal});
 const data=await r.json();if(session!==state.session)throw new Stale();
 if(!r.ok)throw new ApiError(data.error||'HTTP_'+r.status,r.status);return data;
}
function action(fn){return async event=>{event?.preventDefault();try{await fn()}catch(e){if(e instanceof Stale||e.name==='AbortError')return;message(e instanceof TypeError?'تعذر الاتصال بالخادم. تحقق من الشبكة؛ لم نعرض عملية غير مؤكدة كأنها محفوظة.':e.message)}}}
function clearSession(){lookupVersion++;state.abort.abort();state.abort=new AbortController();state.session++;state.token='';state.pending=null;state.busy=false;state.rows=[];state.next=null;state.customer=null;state.account=null;state.accounts=[];state.currencies=[];$('token').value='';$('workspace').hidden=true;$('output').textContent='';$('balances').replaceChildren();$('statement').replaceChildren();$('accountsList').replaceChildren();$('integrityResult').textContent='';$('statementScope').textContent='';$('status').textContent='غير متصل';$('postingForm').reset();$('reversalForm').reset();$('accountForm').reset();$('eventForm').reset();$('entryDate').value=today();$('reverseDate').value=today();controls()}
function option(value,text){const node=document.createElement('option');node.value=value;node.textContent=text;return node}
async function loadAccounts(){const rows=await api('accounts');state.accounts=rows;for(const name of ['control','counter']){const select=$(name),old=select.value;select.replaceChildren(...rows.map(a=>option(a.id,`${a.id} · ${a.name}`)));if(rows.some(a=>a.id===old))select.value=old;else if(name==='control'&&rows.length>1)select.value=rows[1].id;}
 $('accountsList').replaceChildren(...rows.map(a=>{const li=document.createElement('li');li.textContent=`${a.id} — ${a.code} — ${a.name}`;return li}));
 if(!rows.length)message('متصل. افتح «إعداد الحسابات» وأنشئ حساب الصندوق وحساب الذمم أولًا.');
}
$('connectForm').onsubmit=action(async()=>{const token=$('token').value.trim();clearSession();state.token=token;try{const status=await api('status');state.currencies=await api('currencies');$('currency').replaceChildren(...state.currencies.map(c=>option(c.code,c.code)));$('currency').value='USD';await loadAccounts();$('workspace').hidden=false;$('status').textContent=`متصل · تجربة مشغّل واحد · ${status.version}`;message(state.accounts.length?'تم الاتصال. استخدم بيانات وهمية.':'متصل. افتح «إعداد الحسابات» لإنشاء الحسابات.');changeCurrency()}catch(e){clearSession();throw e}});
$('disconnect').onclick=()=>{const uncertain=!!state.pending||state.busy;clearSession();message(uncertain?'تم فصل الاتصال. قد تكون العملية الأخيرة سُجلت؛ افحص كشف العميل بعد الاتصال قبل إعادة إدخالها.':'تم فصل الاتصال ومسح بيانات العرض والرمز من الذاكرة.')};
function digits(code){const c=state.currencies.find(c=>c.code===code);if(!c)throw Error('العملة غير معروفة.');return c.minorUnits}
function changeCurrency(){$('baseLabel').hidden=$('currency').value==='USD';$('baseAmount').required=$('currency').value!=='USD'}
$('currency').onchange=changeCurrency;
function currentCustomer(){return identifier($('customer').value.trim())}
function currentAccount(){return identifier($('control').value)}
function showBalances(balances){$('balances').replaceChildren(...Object.entries(balances).map(([code,value])=>{const box=document.createElement('div');box.className='balance';const title=document.createElement('span');title.textContent=code;const number=document.createElement('strong');number.textContent=money(value,digits(code));box.append(title,number);return box}));if(!Object.keys(balances).length)$('balances').textContent='لا يوجد رصيد مسجل لهذا العميل والحساب.'}
function renderRows(){const nodes=state.rows.map(row=>{const card=document.createElement('article');card.className='movement';const top=document.createElement('div');top.className='row';const title=document.createElement('strong');title.textContent=row.entryType==='DEBT'?'دين':row.entryType==='PAYMENT'?'دفعة':row.entryType==='REVERSAL'?'قيد عكسي':'حركة';const amount=document.createElement('span');amount.className='value';amount.textContent=money((BigInt(row.debitMinor)-BigInt(row.creditMinor)).toString(),digits(row.currency))+' '+row.currency;top.append(title,amount);const description=document.createElement('p');description.textContent=row.description;const meta=document.createElement('p');meta.className='meta';meta.textContent=`${row.date} · قيد ${row.entryId} · سطر ${row.lineNo}`+(row.isReversed?' · تم عكسه':'')+(row.reversesEntryId?` · يعكس القيد ${row.reversesEntryId}`:'');card.append(top,description,meta);if(!row.isReversed){const button=document.createElement('button');button.className='secondary';button.type='button';button.textContent='اختيار للعكس';button.onclick=()=>{$('reverseId').value=row.entryId;$('reason').focus()};card.append(button)}return card});$('statement').replaceChildren(...nodes);if(!nodes.length){const p=document.createElement('p');p.className='empty';p.textContent='لا توجد حركات لهذا العميل والحساب.';$('statement').append(p)}$('older').hidden=!state.next}
async function statement(older=false){const version=++lookupVersion;const customer=older?state.customer:currentCustomer(),account=older?state.account:currentAccount();if(!customer||!account)throw Error('اختر العميل والحساب.');const cursor=older&&state.next?`&beforeEntryId=${state.next.entryId}&beforeLineNo=${state.next.lineNo}`:'';const result=await api(`customers/${customer}/statement?accountId=${account}&limit=30${cursor}`);if(version!==lookupVersion)throw new Stale();$('statementScope').textContent=`الكشف المحمل: العميل ${customer} · الحساب ${account}`;state.customer=customer;state.account=account;state.rows=older?[...state.rows,...result.lines]:result.lines;state.next=result.next;showBalances(result.balances);renderRows()}
$('lookupForm').onsubmit=action(()=>statement());$('older').onclick=action(()=>statement(true));
async function sendPending(){
 if(!state.pending||state.busy)return;const pending=state.pending,session=state.session;state.busy=true;controls();message('جارٍ تأكيد الحفظ…');
 try{
  let result;
  if(pending.path==='pilot/accounts'){const found=(await api('accounts')).find(a=>a.id===pending.body.id&&a.code===pending.body.code&&a.name===pending.body.name);if(found)result={id:found.id};}
  result??=await api(pending.path,pending.body);
  state.pending=null;state.busy=false;controls();message(`تم الحفظ والتأكيد. الرقم: ${result.id}`);pending.complete(result);
  try{await loadAccounts();if(state.accounts.length&&$('customer').value)await statement()}catch(e){if(!(e instanceof Stale)&&e.name!=='AbortError')message(`تم الحفظ والتأكيد. الرقم: ${result.id}. تعذر تحديث الكشف؛ أعد عرضه.`)}
 }catch(e){if(session!==state.session)return;if(e instanceof ApiError&&e.status>=400&&e.status<500&&e.status!==408){state.pending=null;message(e.message)}else message('لم يصل تأكيد الحفظ. استخدم «تأكيد العملية السابقة»؛ سنرسل نفس المحتوى والمفتاح.');state.busy=false;controls();}
}
function write(path,body,complete){if(state.pending||state.busy)throw Error('أكد العملية السابقة أولًا.');state.pending={path,body,complete};return sendPending()}
$('retry').onclick=action(sendPending);
$('accountForm').onsubmit=action(()=>write('pilot/accounts',{id:identifier($('accountId').value.trim()),code:$('accountCode').value.trim(),name:$('accountName').value.trim()},()=>{$('accountForm').reset()}));
$('postingForm').onsubmit=action(()=>{
 const currency=$('currency').value,amount=decimalText($('amount').value.trim()),base=decimalText($('baseAmount').value.trim());minor(amount,digits(currency));if(currency!=='USD')minor(base,2);
 const control=currentAccount(),counter=identifier($('counter').value);if(control===counter)throw Error('حساب الذمم والحساب المقابل يجب أن يكونا مختلفين.');const description=$('description').value.trim();if(!description)throw Error('وصف الحركة مطلوب.');
 const body={customerId:currentCustomer(),controlAccountId:control,counterAccountId:counter,entryDate:$('entryDate').value,kind:document.querySelector('[name=kind]:checked').value,currencyCode:currency,amount,baseAmount:currency==='USD'?null:base,description,idempotencyKey:newKey()};
 return write('pilot/postings',body,()=>{$('amount').value='';$('baseAmount').value='';$('description').value=''});
});
$('reversalForm').onsubmit=action(()=>{const reason=$('reason').value.trim();if(!reason)throw Error('سبب العكس مطلوب.');return write('pilot/reversals',{entryId:identifier($('reverseId').value.trim()),date:$('reverseDate').value,reason,idempotencyKey:newKey()},()=>{$('reverseId').value='';$('reason').value='';$('confirmReverse').checked=false})});
$('checkIntegrity').onclick=action(async()=>{const report=await api('integrity');$('integrityResult').textContent=report.isValid?`متسق داخليًا · ${report.entriesChecked} قيد · HeadHash: ${report.headHash}`:`الفحص غير صالح: ${report.problem}`});
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('exportStatement').onclick=action(()=>{if(!state.customer)throw Error('اعرض الكشف أولًا.');const rows=[['entry_id','line_no','date','description','currency','debit_minor','credit_minor','debit_base_minor','credit_base_minor'],...state.rows.map(r=>[r.entryId,r.lineNo,r.date,r.description,r.currency,r.debitMinor,r.creditMinor,r.debitBaseMinor,r.creditBaseMinor])];download(`K92N-customer-${state.customer}-loaded.csv`,'\ufeff'+rows.map(r=>r.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8');message('تم تصدير الحركات المحملة. المبالغ بوحداتها الصغرى الصحيحة؛ ليس هذا الملف نسخة احتياطية للدفتر.')});
$('eventForm').onsubmit=action(async()=>{if(state.busy||state.pending)throw Error('أكد العملية المحاسبية السابقة أولًا.');state.busy=true;controls();try{const event=await api('events',{kind:$('kind').value,entityId:$('entity').value.trim(),payload:{text:$('text').value.trim(),status:'RECORDED'}});$('output').textContent=JSON.stringify(event,null,2);$('text').value='';message('تم تسجيل الحدث.')}catch(e){if(e instanceof TypeError)message('انقطع الاتصال. افحص سجل القرارات قبل إعادة إرسال الحدث لتجنب تكراره.');else throw e}finally{state.busy=false;controls()}});
$('replay').onclick=action(async()=>{$('output').textContent=JSON.stringify(await api('replay'),null,2)});
$('exportEvents').onclick=action(async()=>download('K92N-events.json',JSON.stringify(await api('events'),null,2),'application/json'));

window.addEventListener('beforeunload',event=>{if(state.pending||state.busy){event.preventDefault();event.returnValue=''}});

window.addEventListener('pagehide',()=>clearSession());
