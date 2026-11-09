# BLACK-K92NN-Wolf

مستودع يجمع وحدات مستقلة. وجود وحدة أو نجاح فحصها لا يعني نشرها أو اعتماد بقية الوحدات للإنتاج.

| الوحدة | المصدر | التشغيل والتحقق |
| --- | --- | --- |
| K92N ledger | [apps/k92n](apps/k92n) | [دليل التشغيل](apps/k92n/README-AR.md) و[تجربة المشغّل](apps/k92n/docs/PREPAYMENT-PILOT-1.0.2-AR.md) بعد دمج PR #39 |
| BLACKWOLF AI preview | [apps/blackwolf-ai](apps/blackwolf-ai) | [الدليل والحدود](apps/blackwolf-ai/README.md)؛ فحوص offline منفصلة عن اتصال OpenAI المدفوع |
| Control plane المستعاد | [components/control-plane](components/control-plane) | `cd components/control-plane && python3 -m unittest discover -s tests -v` |
| Runtime المستعاد | [components/runtime](components/runtime) | [الدليل](components/runtime/README.md)؛ وحدات مستعادة مع حفظ بصمات الأصل |
| UER reliability | [source/blackwolf-uer-v0.1.1-reliability](source/blackwolf-uer-v0.1.1-reliability) | [الدليل](source/blackwolf-uer-v0.1.1-reliability/README.md) و[اختبارات عقود التخزين](tests/Uer.Api.StoreContracts) |

## أين توجد الأدلة؟

- [GitHub Actions](../../actions): اقرأ نتيجة التشغيل للـ commit المقصود، لا وجود ملف workflow فقط.
- [recovery](recovery): مصدر الاستعادة وسجلها.
- `apps/k92n/evidence/`: أدلة تاريخية محفوظة؛ ليست حكمًا تلقائيًا على أحدث مصدر. الأدلة الجديدة تُحفظ كـ CI artifacts مع عمر احتفاظ محدد.

## قواعد الصيانة

كل وحدة تحتفظ ببياناتها وعقودها. لا تُدمج قواعد البيانات بين المشاريع بسبب تشابه الأسماء. لا تُحذف migrations أو بصمات الأصل أو أدلة الاستعادة للتنظيف. لا تُرفع قواعد بيانات التشغيل أو الأسرار أو caches أو build output إلى Git.

لم تُنشأ استضافة مدفوعة ضمن أعمال الصيانة. K92N مخصص حاليًا لتجربة مشغّل واحد ببيانات وهمية؛ اختبار الهاتف الفعلي والاستضافة مستقلان عن نجاح CI. `PRODUCTION_READY = FALSE`.
