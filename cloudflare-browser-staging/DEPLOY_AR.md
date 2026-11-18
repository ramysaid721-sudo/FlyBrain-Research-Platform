# نشر FlyBrain Browser Worker — نسخة Staging

هذه خدمة مستقلة للتصفح الآلي عبر Cloudflare Browser Run. لا تستبدل Worker الإنتاج ولا جسر الاسترجاع الحالي.

## ما توفره

- جلسات Chromium سحابية.
- فتح الصفحات والتنقل بينها.
- قراءة النص الظاهر وبيانات الصفحة.
- النقر عبر CSS selector وإدخال النصوص والضغط على مفاتيح محددة.
- التقاط لقطات PNG.
- إغلاق الجلسات وتحرير موارد Browser Run.

## الحماية

1. جميع طلبات MCP تتطلب ترويسة `Authorization: Bearer`.
2. يجب إنشاء سر مستقل باسم `FLYBRAIN_BROWSER_API_TOKEN` في Cloudflare Worker Secrets. هذا ليس Cloudflare API Token.
3. كل جلسة جديدة تتطلب قائمة نطاقات مسموح بها `allowedDomains`، وتفرض Cloudflare Browser Run هذه القيود طوال عمر الجلسة.
4. مهلة الخمول 60 ثانية، ويجب استدعاء `browser_session_close` عند الانتهاء.
5. لا تضع كلمة مرور أو مفتاح API في عنوان URL أو محتوى مستودع GitHub.

## خطوات الربط والنشر

- افتح Workers & Pages في Cloudflare.
- أنشئ Worker منفصلاً باسم `flybrain-browser-staging`.
- اربطه بالمستودع `ramysaid721-sudo/FlyBrain-Research-Platform`.
- عيّن Root directory إلى `cloudflare-browser-staging`.
- استخدم إعداد `wrangler.jsonc` الموجود.
- تأكد من وجود Browser binding باسم `BROWSER`.
- أضف السر `FLYBRAIN_BROWSER_API_TOKEN` من Settings → Variables and Secrets.
- انشر نسخة Staging فقط.

يمكن تنفيذ إعداد السر والنشر من Wrangler داخل هذا المجلد:
```sh
npx wrangler secret put FLYBRAIN_BROWSER_API_TOKEN
npx wrangler deploy
```

## التحقق

- افتح `/health` وتأكد من ظهور `browserBinding: true` و`authenticationConfigured: true`.
- أرسل طلب MCP مصادقاً عليه إلى `/mcp`.
- نفّذ `initialize` ثم `tools/list`.
- افتح جلسة اختبار بنطاق مسموح، اقرأ الصفحة، التقط صورة، ثم أغلق الجلسة.
- راقب Browser Run usage. الخطة المجانية الموثقة تتيح 10 دقائق Browser Run يومياً وثلاث جلسات متزامنة؛ لا تفترض أن الاستخدام غير محدود.

لم يتم نشر هذا Worker من خلال هذا التغيير البرمجي؛ يتطلب النشر ربط Cloudflare المصرح به.
