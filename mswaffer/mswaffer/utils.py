# your_app/your_app/utils.py
import frappe

from frappe.model.naming import make_autoname
import uuid


def create_unique_constraints():
    # التأكد من عدم وجود بيانات مكررة قبل التنفيذ لتجنب الخطأ
    try:
        frappe.db.add_unique("MsOfferNotifications", ["msuser", "offer_id"], constraint_name="unique_muser_offer_id")
        frappe.db.add_unique("MSCategoryMap", ["ms_user", "user_category"], constraint_name="unique_muser_user_category")
        frappe.db.add_unique("VendorProduct", ["vendorid", "product_name"], constraint_name="unique_vendorid_product_name")
    except Exception as e:
        # بنستخدم pass هنا عشان لو الـ Index موجود فعلاً السكريبت ميتعطلش
        if "Duplicate key name" in str(e) or "already exists" in str(e):
            pass
        else:
            raise e
        


def map_offers_to_users_optimized():
    chunk_size = 2000  # حجم الدفعة الواحدة لضمان الخفة
    start = 0
    frappe.db.rollback()

    # 1. جلب التوليفات الموجودة حالياً (المستخدم + العرض)
    existing_records = frappe.db.get_all("MsOfferNotifications", 
        fields=["msuser", "offer_id"], 
        as_list=True
    )
    # تحويلها لـ set لسرعة البحث
    existing_set = set((r[0], str(r[1])) for r in existing_records)
    print ("existing_set" , existing_set)
    
    # 1. جلب العروض النشطة وتنظيمها في Dictionary حسب الفئة لسرعة الوصول
    active_offers = frappe.get_all("VendorProduct", 
                                   filters={"ready_to_publish": 1}, 
                                   fields=["name", "msmaincategory"])
    #print ("active_offers" , active_offers)
    
    offers_by_category = {}
    for offer in active_offers:
        cat = offer.msmaincategory
        if cat:
            if cat not in offers_by_category:
                offers_by_category[cat] = []
            offers_by_category[cat].append(offer.name)

    while True:
        # 2. جلب دفعة من المستخدمين
        users = frappe.get_all("MsUsers", limit_start=start, limit_page_length=chunk_size, fields=["name"])
        
        if not users:
            break
            
        user_names = [u.name for u in users]
        
        # 3. جلب اهتمامات هؤلاء المستخدمين
        user_interests = frappe.get_all("MSCategoryMap", 
                                        filters={"ms_user": ["in", user_names]}, 
                                        fields=["ms_user", "user_category"])
        
        rows_to_insert = []
        now_time = frappe.utils.now()

        # 4. بناء مصفوفة البيانات للإدخال المجمع
        for interest in user_interests:
            user_id = interest.ms_user
            category = interest.user_category
            
            if category in offers_by_category:
                for product_name in offers_by_category[category]:
                    unique_name = str(uuid.uuid4())
                    offer_id = str(product_name)
                    # التصحيح: نستخدم [List] وليس {Set} لضمان توافق SQL
                    if (user_id, offer_id) not in existing_set:
                        rows_to_insert.append([
                            unique_name,
                            str(user_id), 
                            str(product_name),
                            frappe.utils.now()
                        ])

        # 5. تنفيذ الإدخال المجمع (Bulk Insert)
        if rows_to_insert:
            try:
                #frappe.db.rollback()
                # التأكد من مطابقة أسماء الحقول في الجدول الهدف
                frappe.db.bulk_insert(
                    "MsOfferNotifications", 
                    ["name", "msuser", "offer_id","mscreateddate"], 
                    rows_to_insert
                )
                frappe.db.commit()
                # طباعة بسيطة للتأكد من التقدم في الـ Console
                print(f"Processed batch starting at {start}. Inserted {len(rows_to_insert)} records.")
            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(message=str(e), title="Bulk Insert Error in Map Offers")
                print(f"Error at start {start}: {str(e)}")

        # الانتقال للدفعة التالية وتفريغ الذاكرة
        start += chunk_size
        #frappe.destroy_scoped_local_cache()

    frappe.logger().info("تمت معالجة العروض بنجاح لجميع المستخدمين")

# هذه الدالة التي سيستدعيها الـ Scheduler
def map_offers_to_users_hourly():
    # إرسال المهمة للطابور الطويل لضمان عدم حدوث Timeout
    frappe.enqueue(
        'mswaffer.mswaffer.utils.map_offers_to_users_optimized',
        queue='long',
        timeout=3600 # ساعة كاملة كحد أقصى للتنفيذ
    )