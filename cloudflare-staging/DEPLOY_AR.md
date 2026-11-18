# تعليمات النشر — النسخة التجريبية

1. اربط Cloudflare بالمستودع والفرع cloudflare-staging-deployment.
2. حدد مجلد المشروع cloudflare-staging إذا كان إعداد Cloudflare يسمح بتحديد Root Directory.
3. استخدم ملف wrangler.jsonc الموجود في ذلك المجلد.
4. أنشئ Rate Limiting binding في Cloudflare باسم FLYBRAIN_PUBLIC_LIMITER. لا يوجد namespace ID افتراضي في هذا الملف؛ استخدم المعرف الذي تخصصه Cloudflare لحسابك.
5. انشر النسخة التجريبية فقط باسم flybrain-research-platform-staging.
6. اختبر GET /health ثم اختبارات MCP باستخدام scripts/smoke-test.sh.

لا تغيّر اسم Worker الإنتاج ولا تستبدل ملفه. لا تضع Cloudflare API Token في الملفات أو المستودع.
