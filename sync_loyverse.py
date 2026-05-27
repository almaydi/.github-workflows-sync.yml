import os
import datetime
import requests
import json

# 1. إعداد الرموز السرية والتواريخ الحية لآخر 30 يوماً
TOKEN = os.getenv("LOYVERSE_TOKEN")
if not TOKEN:
    print("خطأ: لم يتم العثور على الرمز السري LOYVERSE_TOKEN في إعدادات جيت هاب!")
    exit(1)

END_DATE = datetime.datetime.now()
START_DATE = END_DATE - datetime.timedelta(days=30)

from_date_str = START_DATE.strftime("%Y-%m-%d")
to_date_str = END_DATE.strftime("%Y-%m-%d")

HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BASE_URL = "https://api.loyverse.com/v1.0"

print(f"📦 بدء جلب البيانات الحية لـ ماونتن برجر من {from_date_str} إلى {to_date_str}...")

try:
    # 2. جلب أقسام المنيو
    cat_res = requests.get(f"{BASE_URL}/categories", headers=HEADERS)
    categories = cat_res.json().get("categories", []) if cat_res.status_code == 200 else []
    category_map = {c["id"]: c["name"] for c in categories}

    # 3. جلب تفاصيل المنتجات والرموز
    items_res = requests.get(f"{BASE_URL}/items?limit=250", headers=HEADERS)
    items = items_res.json().get("items", []) if items_res.status_code == 200 else []
    item_map = {}
    for i in items:
        item_map[i["id"]] = {
            "name": i["item_name"],
            "sku": i.get("sku", "N/A"),
            "category": category_map.get(i.get("category_id"), "عام")
        }

    # 4. جلب الفواتير والمقبوضات
    receipts_url = f"{BASE_URL}/receipts?created_at_min={from_date_str}T00:00:00.000Z&created_at_max={to_date_str}T23:59:59.000Z&limit=250"
    receipts_res = requests.get(receipts_url, headers=HEADERS)
    receipts = receipts_res.json().get("receipts", []) if receipts_res.status_code == 200 else []

    # 5. معالجة العمليات الحسابية وتجميع المبيعات
    processed_sales = {}
    total_sales = 0.0
    total_units = 0.0

    for r in receipts:
        if r.get("status") == "CANCELLED":
            continue
        for li in r.get("line_items", []):
            item_id = li.get("item_id")
            if not item_id:
                continue
               
            meta = item_map.get(item_id, {"name": li.get("item_name", "منتج عام"), "sku": "N/A", "category": "عام"})
            qty = float(li.get("quantity", 0))
            net_sales = float(li.get("total_money", {}).get("amount", 0))
            gross_sales = float(li.get("gross_total_money", {}).get("amount", 0))

            total_sales += net_sales
            total_units += qty

            if meta["name"] not in processed_sales:
                processed_sales[meta["name"]] = {
                    "Item name": meta["name"],
                    "SKU": meta["sku"],
                    "Category": meta["category"],
                    "Items sold": 0.0,
                    "Gross sales": 0.0,
                    "Net sales": 0.0
                }
           
            processed_sales[meta["name"]]["Items sold"] += qty
            processed_sales[meta["name"]]["Gross sales"] += gross_sales
            processed_sales[meta["name"]]["Net sales"] += net_sales

    # تحويل البيانات إلى قائمة وفرزها من الأعلى مبيعاً
    sales_list = list(processed_sales.values())
    sales_list.sort(key=lambda x: x["Net sales"], reverse=True)

    # حساب صافي النقدية الافتراضي للمصروفات الثابتة
    total_payouts = 3635.00
    net_cashflow = total_sales - total_payouts

    print(f"✅ تم تجميع البيانات بنجاح. إجمالي الأصناف المبيوعة: {len(sales_list)}")

    # 6. حقن البيانات الجديدة بداخل قالب الـ HTML وإعادة كتابته
    html_template = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقرير ماونتن برجر السحابي</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Cairo', sans-serif; }}</style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen p-6">
    <div class="max-w-7xl mx-auto">
        <header class="border-b border-slate-800 pb-6 mb-8 flex justify-between items-center">
            <div>
                <h1 class="text-3xl font-black text-amber-500">لوحة تحليلات ماونتن برجر التلقائية</h1>
                <p class="text-slate-400 text-sm mt-1">تحديث سحابي يومي مؤتمت بالكامل عبر جيت هاب وعن طريق مسارات API</p>
                <span class="text-xs bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded mt-2 inline-block font-bold">آخر تحديث مباشر: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
            </div>
            <button onclick="window.print()" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-xl text-sm font-bold transition">طباعة (PDF)</button>
        </header>

        <section class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div class="bg-slate-800 border border-slate-700 rounded-2xl p-5">
                <p class="text-xs text-slate-400 font-bold">صافي المبيعات الحية</p>
                <h3 class="text-xl sm:text-2xl font-black text-emerald-400 mt-2">{total_sales:,.2f} د.إ</h3>
            </div>
            <div class="bg-slate-800 border border-slate-700 rounded-2xl p-5">
                <p class="text-xs text-slate-400 font-bold">المصروفات النقدية المقدرة</p>
                <h3 class="text-xl sm:text-2xl font-black text-red-400 mt-2">{total_payouts:,.2f} د.إ</h3>
            </div>
            <div class="bg-slate-800 border border-slate-700 rounded-2xl p-5">
                <p class="text-xs text-slate-400 font-bold">صافي التدفق المتوفر</p>
                <h3 class="text-xl sm:text-2xl font-black text-blue-400 mt-2">{net_cashflow:,.2f} د.إ</h3>
            </div>
            <div class="bg-slate-800 border border-slate-700 rounded-2xl p-5">
                <p class="text-xs text-slate-400 font-bold">حجم قطع الوجبات</p>
                <h3 class="text-xl sm:text-2xl font-black text-amber-400 mt-2">{total_units:,.0f} قطعة</h3>
            </div>
        </section>

        <section class="bg-slate-800 border border-slate-700 rounded-2xl p-6">
            <div class="font-bold text-sm text-amber-500 mb-4">قائمة المبيعات التفصيلية الحية المستخرجة تلقائياً ({len(sales_list)} صنفاً)</div>
            <div class="overflow-x-auto">
                <table class="w-full text-right border-collapse text-sm">
                    <thead>
                        <tr class="border-b border-slate-700 text-slate-400 bg-slate-900/30">
                            <th class="p-3">اسم المنتج</th>
                            <th class="p-3">رمز SKU</th>
                            <th class="p-3">الفئة</th>
                            <th class="p-3 text-center">الكمية المباعة</th>
                            <th class="p-3 text-left">الصافي الفعلي</th>
                        </tr>
                    </thead>
                    <tbody>
    """
   
    # حقن صفوف الجدول ديناميكياً
    for item in sales_list:
        html_template += f"""
                        <tr class="border-b border-slate-700/50 hover:bg-slate-700/20">
                            <td class="p-3 font-bold text-white">{item['Item name']}</td>
                            <td class="p-3 font-mono text-slate-400 text-xs">{item['SKU']}</td>
                            <td class="p-3 text-slate-300">{item['Category']}</td>
                            <td class="p-3 text-center text-amber-400 font-bold">{item['Items sold']:.0f}</td>
                            <td class="p-3 text-left font-mono text-emerald-400 font-bold">{item['Net sales']:.2f} د.إ</td>
                        </tr>
        """
       
    html_template += """
                    </tbody>
                </table>
            </div>
        </section>
    </div>
</body>
</html>
    """

    # كتابة وحفظ ملف index.html الجديد
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("🚀 تم تحديث ملف index.html بالبيانات الحية المباشرة واكتملت المهمة!")

except Exception as e:
    print(f"❌ حدث خطأ فني أثناء استدعاء بيانات لوجيفيرس: {str(e)}")

 
