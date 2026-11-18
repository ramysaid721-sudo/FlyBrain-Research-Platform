# تشغيل FlyBrain MCP على Vercel

هذه الحزمة تضيف مدخلاً متوافقاً مع Python Functions إلى خادم FlyBrain MCP الحالي، دون تغيير خادم Cloudflare أو ملفات الإنتاج.

## المسار

- نقطة MCP: `/api/mcp`
- نقطة الفحص: `/api/health` (تُضاف كوظيفة مستقلة عند الحاجة)
- الأداة: `ask_flybrain`
- النقل: Streamable HTTP stateless
- المصادقة: Bearer token عبر متغير البيئة `FLYBRAIN_CHAT_API_TOKEN`

## تهيئة المشروع

يجب أن ينفذ أمر التثبيت في Vercel بالترتيب التالي:

```bash
python -m zipfile -e FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip .release
python scripts/apply_chat_bridge.py --source .release/FlyBrain_Research_Platform_v0.14.0
python -m pip install -e .release/FlyBrain_Research_Platform_v0.14.0/components/FlyBrain-NOS
```

ثم يضبط متغير البيئة `FLYBRAIN_CHAT_API_TOKEN` بقيمة عشوائية قوية لا تقل عن 32 حرفاً، و`FLYBRAIN_CHAT_LEDGER=/tmp/flybrain-chat.sqlite3`.

لا تُحفظ الرموز السرية في GitHub أو ملفات المستودع. مساحة `/tmp` مؤقتة في بيئة Serverless، لذلك لا تستخدمها كسجل دائم.

## النشر والاختبار

بعد إعداد المشروع على Vercel، انشر فرع `vercel-mcp-adapter` كـ Preview أولاً، ثم اختبر:

1. MCP `initialize`
2. MCP `tools/list`
3. `tools/call` للأداة `ask_flybrain`
4. طلباً غير مصادق عليه للتأكد من إرجاع 401

لا يُعد إنشاء مشروع Vercel أو نجاح البناء دليلاً على أن أداة MCP تعمل؛ لا يعتمد العنوان قبل اجتياز الاختبارات الأربعة.
