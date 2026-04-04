# Copyright (c) 2026, m@micro-sl.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class VendorProduct(Document):
	def before_save(self):
		self.validate_unique_if_not_empty()

	def validate_unique_if_not_empty(self):
        # 1. نتأكد أن الحقل ليس فارغاً
		if self.vendor_id:
            # 2. نبحث في قاعدة البيانات عن سجل آخر بنفس القيمة
            # مع استثناء السجل الحالي (self.name) لتجنب الخطأ عند التحديث
			duplicate = frappe.db.exists(self.doctype, {
                "vendor_id": self.vendor_id,
                "name": ["!=", self.name]
            })
            
			if duplicate:
                # 3. إطلاق خطأ يمنع الحفظ ويظهر رسالة للمستخدم
				frappe.throw(
					_("The value '{0}' already exists in another record ({1}). Duplicates are not allowed.").format(
	                        self.vendor_id, duplicate
                    )
                )

