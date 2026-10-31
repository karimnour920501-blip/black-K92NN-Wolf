# BLACK-K92N-WOLF — Computer Use Integration v0.1

هذه حزمة برمجية منظمة كي تُنسخ إلى جذر المستودع `black-K92NN-Wolf`؛ المكوّن الجديد داخل `components/computer-use` والعمل السابق لا يتغير.

## التنفيذ الذي تم اختباره

- تم اختبار دورة استدعاءات Responses API عبر نموذج محاكاة، بما يشمل حفظ `previous_response_id` وإرجاع `function_call_output` مع `call_id` المطابق.
- تم إجراء تفاعل فعلي مع متصفح Chromium: إدخال `Mira` وحفظ بطاقة محلية والتحقق من ظهور `Badge ready: Mira`.
- تم حفظ لقطة الشاشة والنتيجة في مجلد `evidence`.
- لا تستخدم التجربة المحلية مفتاح OpenAI؛ لا تعد اختبارًا للشبكة أو للوحة تحكم حقيقية.

## التشغيل من iPhone عبر GitHub Actions

بعد إضافة ملفات الحزمة إلى فرع تجريبي في GitHub، يمكن إطلاق Workflow باسم `Computer Use — local fixture gate` يدوياً من تبويب Actions. هذا المسار يستعمل GitHub-hosted Linux runner، وليس هاتفك أو خادم Hetzner مباشرة.

## التشغيل على خادم Docker مستقل

```bash
cd components/computer-use
docker build -t wolf-cua-worker:local .
python -m unittest discover -s tests -v
python -m wolf_cua.cli --output evidence
```

للتجربة الحية فقط مع توفر اشتراك API وصلاحية النموذج ودفع التكاليف:

```bash
python -m pip install -r requirements-host.txt
# Configure OPENAI_API_KEY securely in the HOST environment.
python -m wolf_cua.cli --live --output evidence
```

**الأمان:** يمنع هذا المثال الوصول الخارجي للمتصفح بشكل مقصود؛ تشغيل الشيفرة داخل Python وحده ليس Sandbox. تُطلب موافقة منفصلة على كل شيفرة ينتجها النموذج، ويُغلق العامل عند الفشل أو الانتهاء. لا تستخدمه لتسجيل الدخول أو الحسابات الحقيقية قبل إضافة مصادقة وصلاحيات ومراجعة نهائية للعزل.

**حالة GitHub:** محتويات الحزمة محلية قابلة للتقديم في Pull Request؛ لا يُعتبر `main` محدثًا إلا بعد Commit وCI وReview وMerge مثبتة.
