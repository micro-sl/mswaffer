import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import frappe
from frappe.utils import now_datetime, get_datetime, time_diff_in_seconds
import time




#USER_CHAT_ID = 6237558719 # Moahmad adel 
async def send_direct_message(messageid):
    TOKEN = frappe.db.get_single_value('MsMasterSettings', 'telegram_bot_id')
    #result = frappe.db.sql("select value from tabSingles where doctype like 'MsMasterSettings' and field like 'telegram_bot_id';")
    #TOKEN = result[0].value if result else None

    print ("TOKEN" , TOKEN)

    
    active_offers = frappe.get_all("MsOfferNotifications", 
                                   filters={"is_send": 0,"name": messageid}, 
                                   fields=["name", "msuser", "offer_id","mscreateddate"])
    
    for offer in active_offers:
        user_id = frappe.get_doc('MsUsers', str(offer["msuser"]))
        USER_CHAT_ID = user_id.telegram_id


        product_doc = frappe.get_doc('VendorProduct', str(offer["offer_id"]))
        print ("=======",str(product_doc.linkurl))
        url= str(product_doc.linkurl)
        photo= str(product_doc.full_image_url )
        product_name= str(product_doc.product_name )
        product_price= str(product_doc.original_price )
        current_price= str(product_doc.current_price )
        formatted_price_after = "{:,.0f}".format(float(current_price))
        formatted_price_before = "{:,.0f}".format(float(product_price))
        discount_percentage= str(int(round(int(product_doc.discount_percentage))))
        # 1. معالجة اسم المنتج (أول 30 حرف فقط) مع إضافة نقاط إذا كان أطول
        short_name = (product_name[:27] + '...') if len(product_name) > 30 else product_name

        # 2. تجهيز نص الوصف (Caption) بتنسيق Markdown متناسق
        # استخدمنا الرموز التعبيرية (Emojis) لتحسين الشكل البصري
        caption_text = (
            f"📦 *{short_name}*\n"
            f"-----------------------\n"
            f"💰 *السعر:* {formatted_price_before}  \n"
            f"📉 *الخصم:* {discount_percentage}% \n"
            f"🔥 *السعر بعد الخصم:* {formatted_price_after}  \n"
        )        


    # إنشاء كائن البوت
        bot = Bot(token=TOKEN)
        
        # تحضير الأزرار
        keyboard = [
            [InlineKeyboardButton("معاينة  🛒", url=url)],
            [InlineKeyboardButton("مشاركة 🔗", switch_inline_query="شوف المنتج ده!")],
            [InlineKeyboardButton("غير مهتم ❌", callback_data="not_interested")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # إرسال الصورة مع النص والأزرار
            await bot.send_photo(
                chat_id=USER_CHAT_ID,
                photo=photo,  # صورة عشوائية للتجربة
                caption=caption_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            print(f"تم الإرسال بنجاح للمستخدم: {USER_CHAT_ID}")
            return True
        except Exception as e:
            print(f"حدث خطأ أثناء الإرسال: {e}")
            return False


def send_telegram_message(messageid=""):
    #messageid="3ba705f4-65c4-432b-8ba9-3313ca19386e"
    success = asyncio.run(send_direct_message(messageid))
    return success



def start_telegram_broadcasting():
    # بنشغل العملية في الخلفية عشان السيستم ميفصلش
    frappe.enqueue('mswaffer.mswaffer.telegrambot.process_offers', timeout=10000)

def process_offers():
    print ("process_offers")
    # 1. هنجيب العروض اللي متبعتتش (مثلاً هناخد 500 في كل مرة عشان الميموري)
    offers = frappe.get_all("MsOfferNotifications", 
                            filters={"is_send": 0}, 
                            fields=["name", "msuser", "offer_id"],
                            limit_page_length=500) ############ Set offer limit to 500

    print ("offers" , offers)
    if not offers:
        return

    for offer in offers:
        # 2. التأكد من شرط الدقيقة لكل مستخدم
        # هنفترض إن بيانات المستخدم متخزنة في Doctype اسمه ' MsUsers'
        last_sent = frappe.db.get_value("MsUsers", offer.msuser, "last_sent_time")
        
        should_send = True
        if last_sent:
            diff = time_diff_in_seconds(now_datetime(), get_datetime(last_sent))
            if diff < 90:
                should_send = False

        if should_send:
            # 3. إرسال الرسالة
            success = send_telegram_message(str(offer.name))
            
            if success:
                # تحديث السجل عشان ميبعتش تاني
                frappe.db.set_value("MsOfferNotifications", offer.name, "is_send", 1)
                # تحديث وقت آخر إرسال للمستخدم
                frappe.db.set_value("MsUsers", offer.msuser, "last_sent_time", now_datetime())
                
                # 4. احترام قيود تلجرام العامة (بين كل رسالة ورسالة تانية بسيطة)
                # بنستنى جزء من الثانية عشان ميحصلش بلوك من تلجرام (Flood Control)
                time.sleep(0.09) 
        
        # بنعمل commit كل شوية عشان الداتا تسمع في الداتابيز أول بأول
        frappe.db.commit()

    # 5. استدعاء الدالة لنفسها تاني عشان تكمل باقي الملايين (Recursive Background Job)
    #frappe.enqueue('mswaffer.mswaffer.telegrambot.process_offers', timeout=10000)