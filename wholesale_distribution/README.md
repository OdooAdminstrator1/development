<h1 align="center">Wholesale Distribution</h1>

<p align="center">
  <a href="#english"><b>🇬🇧&nbsp;English</b></a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#arabic"><b>🇸🇦&nbsp;العربية</b></a>
</p>

<p align="center">
  <i>Odoo&nbsp;19 · Sales / Distribution · LGPL-3</i>
</p>

> **Note** — GitHub Markdown does not run JavaScript, so a live toggle button is
> not possible here. Use the **English / العربية** links above to jump between the
> two language sections, or expand the collapsible blocks.

---

<a id="english"></a>

# 🇬🇧 English

<details open>
<summary><b>Table of contents</b></summary>

1. [What is this project?](#en-what)
2. [Settings](#en-settings)
3. [Entities](#en-entities)
4. [Workflow](#en-workflow)
5. [Things worth knowing](#en-important)
6. [For mobile developers](#en-mobile)

</details>

<a id="en-what"></a>
## 1. What is this project?

**Wholesale Distribution** is a transactional buffer built on top of `sale.order`
for selling goods to retailers through **mobile outlets (trucks)** and
**retail outlets (shops)**.

A field *distributer* loads stock onto a truck, drives a route, sells to retailers
from a phone, and collects cash. The module keeps all of that activity in a private
"distribution" buffer so it never pollutes the standard Sales/Accounting apps. At the
end of the day every run is **aggregated into a single master order and a single
clean invoice**, keeping the ledger tidy.

Key ideas:

- Distribution orders take a **dedicated sequence**, never generate their own
  delivery picking, and are never invoiced individually.
- Inventory moves through an **explicit pipeline** (Charge → Run close → End-of-day
  aggregation), not through normal sale-order delivery.
- Distribution data is **isolated** from the standard Sales app via record rules.

<a id="en-settings"></a>
## 2. Settings

`Wholesale Distribution → Configuration → Settings`

| Setting | What it is | Used for |
| --- | --- | --- |
| **Distribution Umbrella Location** | A *view* stock location | Virtual parent of every outlet's stock location. |
| **Delivery Location** | An *internal* stock location | Where run-close transfers deposit sold goods; the master order ships **from** here. |
| **General Distribution Customer** | A partner (`res.partner`) | The customer on the daily aggregated master order / invoice. |
| **Distributors Can Open Runs** | Boolean | If on, a distributer may open a run from the mobile app. If off, only a cashier/manager opens runs. |

> All three location/partner settings must be configured before closing a run or
> running the end-of-day batch — the actions raise a clear error if they are missing.

**Access groups**

- **Cashier** — operates delivery runs from the **back office only** (Odoo backend, not the mobile app).
- **Distributer (Portal)** — the field distributer's portal identity used by the mobile API.
- **Distribution Manager** — closes runs, manages the fleet, runs the end-of-day batch.
  The `admin` user is granted this group automatically on install.

<a id="en-entities"></a>
## 3. Entities

| Entity | Model | Description |
| --- | --- | --- |
| **Outlet** | `distribution.outlet` | A truck or a shop. Owns a stock location and an optional default distributer. |
| **Delivery Run** | `distribution.delivery.run` | One day's activity for one outlet. Holds the orders, payments, and inventory transfers. **An outlet can have only one *open* run at a time.** |
| **Distributer** | `hr.employee` | The physical person running the route. Belongs to the *Distribution* department and has no internal Odoo seat — only a portal user for the mobile API. |
| **Distribution Order** | `sale.order` (`is_distribution_order = True`) | A sale made to a retailer during the run. Dedicated sequence; never invoiced or delivered on its own. |
| **General Order** | `sale.order` (`is_distribution_master_order = True`) | The aggregated end-of-day master order. Standard sequence; produces the single delivery and the single clean invoice. |
| **Temporary Payment** | `distribution.payment` | Cash collected against an order. State `collected` (held by distributer) → `validated` (handed to cashier and posted to accounting). |

Menu layout:

```
Wholesale Distribution
├── Delivery Runs
├── Orders
│   ├── Distribution Orders
│   └── General Orders
├── Close Day            (end-of-day aggregation wizard)
└── Configuration
    ├── Outlets
    ├── Distributers
    └── Settings
```

<a id="en-workflow"></a>
## 4. Workflow

1. **Configure** the settings and create your **Outlets**, each with a stock location
   and (optionally) a default distributer.
2. **Open a run** for an outlet (back office, or from the mobile app if allowed).
3. **Charge** the outlet — this creates a *draft* internal transfer from the main
   warehouse to the outlet location. Add the products you are loading and validate it.
4. The **distributer sells**: creates distribution orders and records **temporary
   payments** (`collected`) as retailers pay.
5. **Discharge** (optional) returns unsold stock from the outlet back to the main
   warehouse; the resulting transfer opens for review.
6. **Close the run** (manager/cashier):
   - The cashier counts the physical cash and types it into **Cashier Intake**.
   - Closing **refuses** unless the counted amount equals the collected total.
   - One **accounting payment** is created (partner = the **distributer**), the
     Cashier Intake is reset to zero, sold goods move *outlet → delivery location*,
     and the temporary payments flip `collected → validated`.
   - The run becomes **Closed** (fully settled) or **Partially Closed** (money still owed).
7. **Late payment after close?** Recording a new payment on a closed/partially-closed
   run flips it to **Requires Validate**. A manager clicks **Validate**
   (`action_validate_payment_run`): it books one accounting payment, reconciles it
   against the general (master) invoice, and returns the run to Closed / Partially Closed.
   No inventory moves in this step.
8. **Close Day** (end-of-day batch): aggregates all eligible (non-open, not-yet-batched)
   runs into **one General Order** → confirms it → ships from the *Delivery Location* →
   creates and posts **one invoice** → reconciles the runs' accounting payments against
   that invoice → links the runs to the master order.

Run states: `Open → Partially Closed / Requires Validate → Closed`.

<a id="en-important"></a>
## 5. Things worth knowing

- **One open run per outlet** is enforced; close the current run before opening another.
- **Cashier intake must match** the collected total or the run will not close — this is
  the cash-reconciliation safety gate.
- **Distribution orders are invisible** in the standard Sales app (record rules +
  a `_search` filter). They only appear through the distribution menus and the run.
- **The ledger stays clean**: individual distribution orders are never invoiced; only
  the daily General Order produces an `account.move`.
- **Inventory is never auto-delivered** from a distribution sale order; the explicit
  Charge / Close / master-delivery pipeline owns all stock moves.
- **Reconciliation caveat**: the close-time accounting payment is booked on the
  **distributer's** receivable account. For it to settle the master invoice (raised on
  the *General Customer*), both partners should resolve to the **same receivable
  account**; otherwise validation raises a descriptive error.

<a id="en-mobile"></a>
## 6. For mobile developers

The field app talks to Odoo over a small **JSON-RPC** API under
`/api/v1/distribution` (every endpoint is `POST`).

- Auth uses **two tokens**: an integration key (executes the work) and a
  per-distributer portal key (identity). The app never sends outlet/employee ids —
  the server derives them from the distributer's portal user.
- Endpoints cover: open run, create order, add payment, list/detail runs, product
  catalog, outlet quantities, order search.

📖 **Full API reference:** [`Mobile API`](controllers/README.md)

---

<a id="arabic"></a>

<div dir="rtl">

# 🇸🇦 العربية

<details open>
<summary><b>المحتويات</b></summary>

1. [ما هذا المشروع؟](#ar-what)
2. [الإعدادات](#ar-settings)
3. [الكيانات](#ar-entities)
4. [سير العمل](#ar-workflow)
5. [أمور يجدر معرفتها](#ar-important)
6. [لمطوّري تطبيق الجوال](#ar-mobile)

</details>

<a id="ar-what"></a>

## ١. ما هذا المشروع؟

**التوزيع بالجملة** هو طبقة معاملات مبنية فوق `sale.order` لبيع البضائع لتجار التجزئة
عبر **منافذ متنقّلة (شاحنات)** و**منافذ ثابتة (محلات)**.

يقوم **الموزّع** الميداني بتحميل البضاعة على الشاحنة، ويسير في خط سير، ويبيع لتجار
التجزئة من هاتفه، ويحصّل النقد. يحتفظ التطبيق بكل هذا النشاط في طبقة توزيع خاصة كي لا
يختلط بتطبيقَي المبيعات والمحاسبة القياسيين. وفي نهاية اليوم تُجمَّع كل الجولات في
**أمر رئيسي واحد وفاتورة واحدة نظيفة**، فيبقى دفتر الأستاذ مرتّبًا.

الأفكار الأساسية:

- أوامر التوزيع لها **تسلسل ترقيم مخصّص**، ولا تُنشئ سند تسليم خاصًا بها، ولا تُفوتر
  بشكل فردي.
- يتحرك المخزون عبر **مسار صريح** (شحن ← إغلاق الجولة ← تجميع نهاية اليوم)، وليس عبر
  تسليم أمر البيع العادي.
- بيانات التوزيع **معزولة** عن تطبيق المبيعات القياسي عبر قواعد السجلات.

<a id="ar-settings"></a>

## ٢. الإعدادات

`التوزيع بالجملة ← الإعدادات ← الضبط`

| الإعداد | ما هو | الاستخدام |
| --- | --- | --- |
| **موقع التوزيع المظلّة** | موقع مخزون من نوع *عرض* | الأب الافتراضي لكل مواقع مخزون المنافذ. |
| **موقع التسليم** | موقع مخزون *داخلي* | حيث تودِع تحويلات إغلاق الجولة البضاعة المباعة؛ ومنه يشحن الأمر الرئيسي. |
| **عميل التوزيع العام** | جهة اتصال (`res.partner`) | العميل في الأمر/الفاتورة الرئيسية المجمّعة يوميًا. |
| **يمكن للموزّعين فتح الجولات** | قيمة منطقية | إن فُعِّلت، يمكن للموزّع فتح جولة من التطبيق. وإلا، يفتحها الكاشير/المدير فقط. |

> يجب ضبط إعدادات المواقع والعميل الثلاثة قبل إغلاق أي جولة أو تشغيل دفعة نهاية اليوم —
> وإلا ظهرت رسالة خطأ واضحة.

**مجموعات الصلاحيات**

- **كاشير** — يدير جولات التسليم من **المكتب الخلفي فقط** (واجهة Odoo، وليس تطبيق الجوال).
- **موزّع (بوابة)** — هوية البوابة للموزّع الميداني التي يستخدمها تطبيق الجوال.
- **مدير التوزيع** — يغلق الجولات، ويدير الأسطول، ويشغّل دفعة نهاية اليوم. ويُمنح
  المستخدم `admin` هذه المجموعة تلقائيًا عند التثبيت.

<a id="ar-entities"></a>

## ٣. الكيانات

| الكيان | النموذج | الوصف |
| --- | --- | --- |
| **المنفذ** | `distribution.outlet` | شاحنة أو محل. يملك موقع مخزون وموزّعًا افتراضيًا اختياريًا. |
| **جولة التسليم** | `distribution.delivery.run` | نشاط يوم واحد لمنفذ واحد. تحوي الأوامر والمدفوعات والتحويلات المخزنية. **لا يمكن أن يكون للمنفذ سوى جولة *مفتوحة* واحدة في آنٍ واحد.** |
| **الموزّع** | `hr.employee` | الشخص الفعلي الذي يسير في الخط. ينتمي لقسم *التوزيع* وليس له مقعد Odoo داخلي — بل مستخدم بوابة فقط لتطبيق الجوال. |
| **أمر التوزيع** | `sale.order` (`is_distribution_order = True`) | بيع لتاجر تجزئة أثناء الجولة. تسلسل مخصّص؛ لا يُفوتر ولا يُسلَّم بمفرده. |
| **الأمر العام** | `sale.order` (`is_distribution_master_order = True`) | الأمر الرئيسي المجمّع لنهاية اليوم. تسلسل قياسي؛ يُنتج التسليم الوحيد والفاتورة النظيفة الوحيدة. |
| **الدفعة المؤقتة** | `distribution.payment` | نقد محصّل مقابل أمر. الحالة `محصّل` (بحوزة الموزّع) ← `معتمد` (سُلِّم للكاشير ورُحِّل محاسبيًا). |

تخطيط القائمة:

```
التوزيع بالجملة
├── جولات التسليم
├── الأوامر
│   ├── أوامر التوزيع
│   └── الأوامر العامة
├── إغلاق اليوم        (معالج تجميع نهاية اليوم)
└── الإعدادات
    ├── المنافذ
    ├── الموزّعون
    └── الضبط
```

<a id="ar-workflow"></a>

## ٤. سير العمل

1. **اضبط** الإعدادات وأنشئ **المنافذ**، لكل منها موقع مخزون و(اختياريًا) موزّع افتراضي.
2. **افتح جولة** لمنفذ (من المكتب الخلفي، أو من التطبيق إن كان مسموحًا).
3. **اشحن** المنفذ — يُنشئ هذا تحويلًا داخليًا *مسودّة* من المستودع الرئيسي إلى موقع
   المنفذ. أضف المنتجات التي تحمّلها وصادق عليه.
4. **يبيع الموزّع**: يُنشئ أوامر توزيع ويسجّل **مدفوعات مؤقتة** (`محصّل`) كلما دفع التجار.
5. **التفريغ** (اختياري) يعيد المخزون غير المباع من المنفذ إلى المستودع الرئيسي؛ ويُفتح
   التحويل الناتج للمراجعة.
6. **أغلق الجولة** (المدير/الكاشير):
   - يَعُدّ الكاشير النقد الفعلي ويُدخله في **نقد الكاشير**.
   - **يُرفض** الإغلاق ما لم يطابق المبلغ المعدود إجمالي المحصّل.
   - تُنشأ **دفعة محاسبية** واحدة (جهة الاتصال = **الموزّع**)، ويُصفَّر حقل نقد الكاشير،
     وتنتقل البضاعة المباعة *من المنفذ ← موقع التسليم*، وتتحول المدفوعات المؤقتة من
     `محصّل ← معتمد`.
   - تصبح الجولة **مغلقة** (مسوّاة بالكامل) أو **مغلقة جزئيًا** (ما زال هناك مستحقات).
7. **دفعة متأخرة بعد الإغلاق؟** تسجيل دفعة جديدة على جولة مغلقة/مغلقة جزئيًا يحوّلها إلى
   **بحاجة لاعتماد**. ينقر المدير **اعتماد** (`action_validate_payment_run`): تُرحَّل
   دفعة محاسبية واحدة، وتُطابَق مع الفاتورة الرئيسية، وتعود الجولة إلى مغلقة/مغلقة جزئيًا.
   لا تتحرك أي بضاعة في هذه الخطوة.
8. **إغلاق اليوم** (دفعة نهاية اليوم): تُجمّع كل الجولات المؤهلة (غير المفتوحة وغير
   المُجمّعة بعد) في **أمر عام واحد** ← يُؤكَّد ← يُشحن من *موقع التسليم* ← تُنشأ وتُرحَّل
   **فاتورة واحدة** ← تُطابَق مدفوعات الجولات معها ← تُربط الجولات بالأمر الرئيسي.

حالات الجولة: `مفتوحة ← مغلقة جزئيًا / بحاجة لاعتماد ← مغلقة`.

<a id="ar-important"></a>

## ٥. أمور يجدر معرفتها

- **جولة مفتوحة واحدة لكل منفذ** مفروضة؛ أغلق الجولة الحالية قبل فتح أخرى.
- **يجب أن يطابق نقد الكاشير** إجمالي المحصّل وإلا لن تُغلق الجولة — هذه بوابة أمان
  تسوية النقد.
- **أوامر التوزيع مخفية** في تطبيق المبيعات القياسي (قواعد السجلات + مرشّح `_search`).
  تظهر فقط عبر قوائم التوزيع والجولة.
- **يبقى دفتر الأستاذ نظيفًا**: لا تُفوتر أوامر التوزيع الفردية؛ فقط الأمر العام اليومي
  يُنتج قيدًا محاسبيًا.
- **لا يُسلَّم المخزون تلقائيًا** من أمر بيع توزيعي؛ مسار الشحن/الإغلاق/تسليم الأمر
  الرئيسي هو من يملك كل حركات المخزون.
- **ملاحظة التسوية**: تُرحَّل الدفعة المحاسبية وقت الإغلاق على حساب ذمم **الموزّع**.
  ولكي تُسوّي الفاتورة الرئيسية (المصدَرة على *العميل العام*) ينبغي أن يؤول الطرفان إلى
  **نفس حساب الذمم**؛ وإلا ظهرت رسالة خطأ واضحة.

<a id="ar-mobile"></a>

## ٦. لمطوّري تطبيق الجوال

يتواصل التطبيق الميداني مع Odoo عبر واجهة **JSON-RPC** صغيرة تحت
`/api/v1/distribution` (كل نقطة نهاية من نوع `POST`).

- المصادقة تستخدم **رمزين**: رمز تكامل (ينفّذ العمل) ورمز بوابة لكل موزّع (الهوية).
  لا يرسل التطبيق معرّفات المنفذ/الموظف — يستنتجها الخادم من مستخدم بوابة الموزّع.
- تغطّي النقاط: فتح جولة، إنشاء أمر، إضافة دفعة، قائمة/تفاصيل الجولات، كتالوج المنتجات،
  كميات المنفذ، بحث الأوامر.

📖 **المرجع الكامل للواجهة:** [`Mobile API`](controllers/README.md)

</div>
