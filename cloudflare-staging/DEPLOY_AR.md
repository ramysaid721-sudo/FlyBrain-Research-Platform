# تعليمات إعداد ونشر FlyBrain على Cloudflare — بيئة Staging

## النطاق
هذه نسخة تجريبية مستقلة باسم `flybrain-research-platform-staging`، ولا تستبدل Worker الإنتاج ولا تعدّله.

## مسار النشر المعتمد
النشر يُدار من خلال ملف GitHub Actions التالي:

`.github/workflows/deploy-flybrain-staging.yml`

- عند تحديث ملفات `cloudflare-staging/**` على فرع `main`، يبدأ سير العمل نشر نسخة Staging تلقائياً.
- يمكن تشغيل سير العمل يدوياً من GitHub Actions باستخدام `workflow_dispatch`.
- يستخدم سير العمل أسرار GitHub Actions المسماة `CLOUDFLARE_API_TOKEN` و`CLOUDFLARE_ACCOUNT_ID`. لا تضع قيم هذه الأسرار في المستودع أو المحادثات.
- لا تستخدم الفرع القديم `cloudflare-staging-deployment` كمصدر للنشر؛ فهو ليس مسار النشر المعتمد حالياً.

## إعداد Worker
- الاسم: `flybrain-research-platform-staging`.
- ملف الإعداد: `cloudflare-staging/wrangler.jsonc`.
- يجب أن يكون ربط تحديد المعدل باسم `FLYBRAIN_PUBLIC_LIMITER` متاحاً.
- يجب أن يكون `namespace_id` نصاً رقمياً موجباً وفق مخطط Cloudflare Workers الحالي.

## الاختبار بعد النشر
بعد نجاح نشر Staging، نفّذ:

```bash
bash scripts/smoke-test.sh https://YOUR-STAGING-WORKER.workers.dev
```

وتحقق من:
1. أن `GET /health` يعيد الحالة `ok` وأن `rate_limiter_binding` تساوي `true`.
2. نجاح طلب MCP `initialize`.
3. ظهور أداة `ask_flybrain` في `tools/list`.
4. نجاح استدعاء قراءة تجريبي لـ `ask_flybrain`.

## الأمان
لا تضع Cloudflare API Token أو كلمات المرور في المستودع أو المحادثة. لا تغيّر Worker الإنتاج أو اسمه أو إعداداته. جميع الخطوات هنا تخص Staging فقط.
