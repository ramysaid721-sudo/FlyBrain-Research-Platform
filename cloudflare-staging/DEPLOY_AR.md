# تعليمات إعداد ونشر FlyBrain على Cloudflare — بيئة تجريبية

## النطاق
هذه نسخة تجريبية منفصلة باسم `flybrain-research-platform-staging`، ولا تستبدل Worker الإنتاج.

## إعداد الربط
1. اربط مستودع GitHub بحساب Cloudflare.
2. اختر الفرع `cloudflare-staging-deployment`.
3. اجعل Root Directory هو `cloudflare-staging`.
4. استخدم ملف الإعداد `wrangler.jsonc` الموجود داخل هذا المجلد.
5. تأكد من ظهور Rate Limiting binding باسم `FLYBRAIN_PUBLIC_LIMITER`. يتضمن الملف معرّف namespace تجريبياً مستقلاً `26111702`؛ يجب التحقق من قبوله في حساب Cloudflare قبل النشر.
6. اسم Worker المقترح هو `flybrain-research-platform-staging`.

## الاختبار
بعد النشر، تحقق من:
- `GET /health` وأن `rate_limiter_binding` تساوي `true`.
- `POST /mcp` لطلبات initialize وtools/list.
- تشغيل `bash scripts/smoke-test.sh https://YOUR-STAGING-WORKER.workers.dev`.

## الأمان
لا تضع Cloudflare API Token أو كلمات مرور في المستودع. لا تغيّر Worker الإنتاج أو اسمه أو ملف إعداده. لا تنشر قبل مراجعة إعدادات البيئة التجريبية.
