# BLACK-K92N-WOLF — UER P1 Hardening Candidate

**20 أكتوبر 2026** · المعمارية **FROZEN** · الإصدار: **0.1.1 / Patch Candidate**

## ما استلمته
مصدر نسخة Lifecycle Audit Patch السابقة، لا أرشيف UER P1 ZIP الأصلي.

SHA-256 لملف `Program.cs` قبل التعديل: `ad59260d8fa61703dfb771a35786ae494f6878d406d23001c3a510d45c8722fd`

SHA-256 بعد التعديل: `b4ca92644a3e34f1304b8fd9d60642be4f82e56cdfe27130934b1eded11db185`

## ما تغير
- قبل `docker rm -f`: تأكيد اسم الحاوية، تطابق الفلتر حسب attempt_id، ثم inspect والتحقق من job_id وattempt_id وepoch وblackwolf.uer.
- بعد الإزالة: تأكيد عدم وجود الحاوية باستخدام استعلامات Docker، دون تفسير أخطاء CLI كدليل غياب.
- تسجيل `container_absence_verified` في `lifecycle_audit` داخل معاملة SQLite.
- رفض `Store.Complete()` دون وجود حدث تنظيف واحد محدد للمحاولة.
- عزل `QUARANTINED` بدل تمرير نتيجة اختبار غير موثقة في حالات غياب `wait/logs` أو فشل التنظيف.
- في استعادة التشغيل: تطبيق منطق إزالة الهوية نفسه وعدم إعطاء صلاحية إعادة التنفيذ التلقائية.
- عند فشل تسجيل العزل في SQLite: يوقف العامل بدل الانتقال إلى عمل آخر.

## نتائج محلية حقيقية
- **15/15 PASS**: فحص ثابت للمصدر وخصائص SQLite باستخدام Python.
- `bash -n`: **PASS**.
- 9 اختبارات Store Contracts بلغة C# مكتوبة في الحزمة لكن **NOT_RUN**.
- بناء .NET **BLOCKED** (SDK غير متاح).
- Docker **BLOCKED** (CLI غير متاح).
- الاختبارات الرسمية: **0/10 VERIFIED**.
- ضوابط P1 الرسمية: **0/3 VERIFIED**.

## حدود النتيجة
فحوص النص وPython ليست اختبارات تشغيل لكود C#. ودليل التنظيف المسجل محليًا لا يشكّل توقيعًا مستقلًا
ولا يثبت غياب آثار سابقة خارج النظام. ما زالت الهوية وقاعدة البيانات وDocker ليست معاملة ذرّية واحدة.

## قرار الإصدار
`release_decision: BLOCKED`

**Production Ready: FALSE**

اطّلع على `README.md` و`docs/RELEASE_GATES.md` و`docs/SECURITY_AND_LIMITATIONS.md`، ثم شغّل 
`./scripts/verify_on_isolated_host.sh` على جهاز اختبار مخصص يحتوي على .NET 8 وDocker.
