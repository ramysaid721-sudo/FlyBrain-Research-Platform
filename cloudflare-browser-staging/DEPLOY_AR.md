# نشر FlyBrain Browser Worker — بيئة Staging

خدمة متصفح مستقلة ومصادقة تستخدم Cloudflare Browser Run ومحرك Playwright المتوافق مع Cloudflare. لا تستبدل جسر الاسترجاع الحالي أو خدمة الإنتاج.

## القدرات

- عرض صفحات HTTPS عامة باستخدام Playwright على Cloudflare Browser Run.
- تقييد طلبات الصفحة والموارد الفرعية وإعادة التوجيه بالنطاق المستهدف نفسه.
- فتح جلسات Chromium محمية بقائمة نطاقات مسموح بها.
- التنقل وقراءة النص والنقر وإدخال النصوص والتقاط الصور وإغلاق الجلسات.

## التبديل التلقائي بين المزودين

يتبع محوّل FlyBrain ترتيباً يبدأ بأقل الخيارات تكلفة:

1. يحاول استخراج الصفحة عبر HTTPS العادي أولاً.
2. إذا كانت الصفحة تحتاج JavaScript أو فشل الاستخراج، يحاول Cloudflare Browser Run باستخدام Playwright.
3. إذا تعذر Cloudflare أو فشل، يحاول Browserless فقط عند وجود مفتاحه وتفعيل علم الاستخدام صراحةً.
4. إذا تعذر المتصفحان، يعيد نتيجة HTTP مع تنبيه إلى احتمال نقص المحتوى المعتمد على JavaScript.

Playwright محرك أتمتة وليس خدمة استضافة مستقلة؛ يعمل هنا فوق Cloudflare Browser Run. أما Browserless فهو مزود استضافة متصفح بديل.

## الأمان وضبط التكلفة

- يتطلب كل طلب MCP ترويسة Bearer token.
- يحفظ السر `FLYBRAIN_BROWSER_API_TOKEN` في Cloudflare Worker Secrets فقط.
- يقبل Playwright صفحات HTTPS عامة فقط، ويمنع طلبات المتصفح إلى أي مضيف غير المضيف المستهدف.
- لا يتم تجاوز CAPTCHA أو تسجيل الدخول أو أنظمة الحماية.
- يبقى Cloudflare وBrowserless معطلين ما لم تُضبط بيانات الاعتماد وأعلام الاستخدام صراحةً.
- لا يتم تفعيل خطة مدفوعة أو تغيير إعدادات الفوترة تلقائياً.

## إعداد Cloudflare Staging

1. اسم Worker: `flybrain-browser-staging`.
2. المجلد الجذري: `cloudflare-browser-staging`.
3. تأكد من وجود Browser binding باسم `BROWSER`.
4. أضف `FLYBRAIN_BROWSER_API_TOKEN` كسر في إعدادات Worker.
5. انشر Staging فقط، ثم تحقق من `/health`.

## إعداد Vercel Preview للفرع التجريبي

- `FLYBRAIN_BROWSER_WORKER_URL`: رابط HTTPS الكامل لـ Worker وينتهي بـ `/mcp`.
- `FLYBRAIN_BROWSER_API_TOKEN`: السر نفسه المستخدم في Cloudflare Worker.
- `FLYBRAIN_BROWSER_RUN_ALLOW_USAGE`: لا تضبطه على true إلا بعد التأكد من أن الخطة لا تفرض رسوماً وأن الحصة المجانية مناسبة.
- `BROWSERLESS_TOKEN`: اختياري لخطة Browserless المجانية.
- `BROWSERLESS_ALLOW_USAGE`: لا تضبطه على true إلا بعد التأكد من تعطيل أي تجاوز مدفوع.
- `FLYBRAIN_WEB_FETCH_PROVIDER`: اتركه فارغاً أو اضبطه على `auto`.

يجب وضع هذه المتغيرات في Preview للفرع `flybrain-browser-worker-staging` فقط، وليس في Production.

## الاختبارات

```sh
npm install --no-audit --no-fund
npm run check
npm test
npx wrangler deploy --dry-run
```

نجاح الفحص المحلي لا يثبت أن Browser Run أو سر المصادقة يعملان فعلياً. يلزم اختبار حي بعد نشر Staging.
