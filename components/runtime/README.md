# WOLF DEPLOY Runtime Core · 0.1.0

نواة تشغيل محلية قابلة للاختبار، تُنفّذ مسارًا حقيقيًا محدودًا: تتحقق من موقع ثابت داخل `projects/`، تنسخه بأمان إلى مساحة النشر، ثم تعرضه عبر `/preview/{job_id}/`.

## التشغيل

يتطلب Python 3.10 أو أحدث، ولا يحتاج حزمًا خارجية:

```bash
cd wolf-deploy-runtime
python runtime.py
```

افتح `http://127.0.0.1:8088`، أو انشر المثال:

```bash
curl -X POST http://127.0.0.1:8088/api/jobs \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-release-001' \
  -d '{"source_dir":"example-site"}'
```

تابع الحالة عبر `GET /api/jobs`، والأحداث عبر `GET /api/jobs/{id}/events`، والمعاينة عبر `GET /preview/{id}/`.

يمكن ضبط `WOLF_HOST` و`WOLF_PORT` و`WOLF_PROJECTS_ROOT` و`WOLF_PUBLISHED_ROOT` و`WOLF_DB_PATH`. يظل الربط الافتراضي على loopback. لا تعرض الخدمة على شبكة عامة قبل إضافة المصادقة والعزل المناسبين.

## ما يعمل الآن

- API HTTP ولوحة تحكم تفاعلية.
- طابور دائم في SQLite WAL وعامل خلفي يلتقط المهام.
- آلة حالات تتحقق من الانتقالات، ومفتاح idempotency مع رفض إعادة استخدامه لطلب مختلف.
- leases وheartbeat ومحاولة استرداد المهام التي انتهت lease الخاصة بها.
- سجل أحداث لكل مهمة مع سلسلة SHA-256 قابلة للتحقق.
- تحقق من ملفات ثابتة، ومنع symlinks، وحدود حجم وعدد الملفات، ونشر ذري إلى مساحة محلية.
- تقديم الملفات المنشورة مع `nosniff` وContent Security Policy.

## حدود النسخة

هذه نواة أحادية العقدة لنشر مواقع ثابتة محليًا. لا يوجد GitHub webhook، أو بناء Docker، أو Kubernetes، أو PostgreSQL متعدد العقد، أو تسجيل دخول، أو أسرار مُدارة، أو canary/rollback لمزوّد خارجي، أو تشغيل أوامر من ملفات المشروع. لذلك فهي **MVP تشغيل محلي** وليست منصة نشر سحابية أو جاهزية إنتاج عامة. لا تُحسب KPIs افتراضية كأنها نتائج فعلية.

## الاختبارات

```bash
python -m unittest discover -s tests -v
```