# حزمة نشر FlyBrain-NOS / URCAL على Cloudflare

هذه الحزمة تنشئ نسخة Staging مستقلة من طبقة Cloudflare MCP Bridge، ولا تستبدل Worker الإنتاج.

## الملفات
- worker/index.js: جسر MCP للقراءة فقط.
- wrangler.jsonc: إعداد Worker التجريبي.
- scripts/smoke-test.sh: اختبارات HTTP.
- DEPLOY_AR.md: تعليمات النشر.

## النطاق
الجسر يسترجع مقتطفات من README.md وملفي README الخاصين بـ FlyBrain-NOS وURCAL في مستودع GitHub. مكونات Python والاختبارات والوثائق الأصلية تبقى في المستودع ولا تتحول تلقائياً إلى Worker.

## الأمان
- أداة ask_flybrain فقط.
- لا توجد عمليات كتابة أو حذف أو تعديل.
- لا توجد مفاتيح API أو كلمات مرور.
- يلزم إضافة Rate Limiting binding باسم FLYBRAIN_PUBLIC_LIMITER من لوحة Cloudflare قبل نجاح طلبات MCP.
- endpoint عام؛ لا ترسل معلومات سرية إليه.

لا تعتمد النسخة للإنتاج قبل اختبار /health وMCP ومراجعة Cloudflare Logs.
