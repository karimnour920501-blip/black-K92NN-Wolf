// All financial arithmetic/display uses integer strings and BigInt, never binary floats.
export function decimalText(value){return value.replace(/[٠-٩۰-۹]/g,ch=>String(ch.charCodeAt(0)-(ch>='۰'?1776:1632))).replaceAll('٫','.')}
export function minor(amount,digits){
 amount=decimalText(amount);
 if(!Number.isInteger(digits)||digits<0||digits>6)throw Error('دقة العملة غير معروفة');
 if(!/^[0-9]+(?:\.[0-9]+)?$/.test(amount)||amount.length>32)throw Error('أدخل مبلغًا بالأرقام الإنجليزية، مثل 125.50');
 const [whole,fraction='']=amount.split('.');if(fraction.length>digits)throw Error('عدد الكسور أكبر من دقة العملة؛ لن نقرب المبلغ');
 const value=BigInt(whole)*10n**BigInt(digits)+BigInt(fraction.padEnd(digits,'0')||'0');
 if(value<=0n||value>1000000000000000n)throw Error('المبلغ يجب أن يكون موجبًا وضمن الحد');return value.toString();
}
export function money(value,digits){
 const n=BigInt(value),negative=n<0n,raw=(negative?-n:n).toString().padStart(digits+1,'0');
 return (negative?'-':'')+(digits?raw.slice(0,-digits)+'.'+raw.slice(-digits):raw);
}
export function identifier(value){value=decimalText(value);if(!/^[0-9]{1,19}$/.test(value)||BigInt(value)<1n||BigInt(value)>9223372036854775807n)throw Error('أدخل رقمًا صحيحًا موجبًا للمعرّف');return BigInt(value).toString()}
export function csvCell(value){let s=String(value??'');if(/^[\s]*[=+\-@]/.test(s)||/^[\t\r\n]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'}
