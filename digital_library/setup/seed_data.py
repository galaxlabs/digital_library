from __future__ import annotations

import frappe


def upsert(doctype: str, name: str | None = None, filters: dict | None = None, values: dict | None = None):
    values = values or {}
    existing = name if name and frappe.db.exists(doctype, name) else None
    if not existing and filters:
        existing = frappe.db.get_value(doctype, filters, "name")
    doc = frappe.get_doc(doctype, existing) if existing else frappe.new_doc(doctype)
    doc.update(values)
    if name and not existing:
        doc.name = name
    doc.save(ignore_permissions=True)
    return doc


def seed():
    for role_name in ("DL Reader", "DL Author", "DL Publisher"):
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)

    
    categories = [
        ("islamic", "اسلامی کتب / Islamic Studies", "Islamic Studies", "🕌", "#0F5D4A", 1),
        ("educational", "تعلیمی / Educational", "Educational / Textbooks", "📚", "#2563EB", 2),
        ("technical", "ٹیکنیکل / Technical", "Technical / Engineering", "⚙️", "#6366F1", 3),
        ("dictionary", "لغت / Dictionary", "Dictionary / Reference", "📖", "#8B5CF6", 4),
        ("stories", "افسانے / Stories", "Stories / Literature", "📘", "#EC4899", 5),
        ("dual-language", "دو لسانی / Dual Language", "Dual Language Books", "🌐", "#14B8A6", 6),
        ("poetry", "شاعری / Poetry", "Poetry / شاعری", "📝", "#F59E0B", 7),
        ("history", "تاریخ / History", "History / تحقیقی", "🏛️", "#78716C", 8),
    ]
    for slug, name_ur, name_en, icon, color, order in categories:
        upsert(
            "Book Category",
            slug,
            values={
                "category_name": name_en,
                "slug": slug,
                "icon": icon,
                "color": color,
                "sort_order": order,
                "active": 1,
            },
        )

    languages = [
        ("ur", "Urdu", "RTL", "Noto Nastaliq Urdu", 1),
        ("ar", "Arabic", "RTL", "Amiri", 2),
        ("fa", "Persian", "RTL", "Noto Nastaliq Urdu", 3),
        ("ps", "Pashto", "RTL", "Noto Nastaliq Urdu", 4),
        ("en", "English", "LTR", "Inter", 5),
        ("hi", "Hindi", "LTR", "Noto Sans Devanagari", 6),
    ]
    for code, name, direction, font, order in languages:
        upsert(
            "App Language",
            code,
            values={
                "language_name": name,
                "language_code": code,
                "direction": direction,
                "default_font": font,
                "enabled": 1,
                "sort_order": order,
            },
        )

    if not frappe.db.exists("Currency", "PKR"):
        frappe.get_doc({"doctype": "Currency", "currency_name": "Pakistani Rupee", "name": "PKR"}).insert(ignore_permissions=True)

    book = upsert(
        "Digital Book",
        "al-qarar",
        values={
            "title": "اصل قرار کہیں اور ہے",
            "subtitle": "اضطراب سے سکون تک کا سفر",
            "slug": "al-qarar",
            "author": "Spiritual Guide",
            "category": "islamic",
            "description": "A premium Urdu Islamic reader experience exploring anxiety, meaning, and spiritual tranquility.",
            "status": "Published",
            "base_language": "ur",
            "is_paid": 1,
            "default_price": 1500,
            "currency": "PKR",
            "total_pages": 415,
            "sort_order": 1,
            "version": "1.0.0",
            "featured": 1,
            "allow_preview": 1,
            "preview_start_page": 2,
            "preview_end_page": 20,
        },
    )

    translation = upsert(
        "Book Translation",
        filters={"book": book.name, "language": "ur"},
        values={
            "book": book.name,
            "language": "ur",
            "title": "اصل قرار کہیں اور ہے",
            "subtitle": "اضطراب سے سکون تک کا سفر",
            "direction": "RTL",
            "font_family": "Noto Nastaliq Urdu",
            "package_version": "1.0.0",
            "total_pages": 415,
            "is_published": 1,
        },
    )

    frappe.db.delete("Book Chapter", {"book": book.name})
    chapters = [
        ("پیش لفظ", "Preliminary", 2, 6),
        ("آداب مطالعہ", "Preliminary", 7, 12),
        ("تمہید", "Preliminary", 13, 20),
        ("بابِ اول: انسان اور زمین کے درمیان عدمِ مطابقت", "Chapter", 21, 59),
        ("باب دوم: انسان حیاتیات سے ما وراء ایک شعوری وجود", "Chapter", 61, 138),
        ("باب سوم: انسانی شعور اور وجودی اضطراب", "Chapter", 140, 181),
        ("بابِ چہارم: روح اور انسانی شناخت", "Chapter", 183, 226),
        ("بابِ پنجم: سکونِ قلب کی تلاش", "Chapter", 228, 292),
        ("بابِ ششم: سفرِ مراجعت", "Chapter", 294, 339),
        ("بابِ ہفتم: ادراک سے عمل تک، ایک نئی زندگی کا آغاز", "Chapter", 341, 415),
    ]
    for index, (title, chapter_type, start_page, end_page) in enumerate(chapters, start=1):
        frappe.get_doc(
            {
                "doctype": "Book Chapter",
                "book": book.name,
                "translation": translation.name,
                "title": title,
                "chapter_type": chapter_type,
                "start_page": start_page,
                "end_page": end_page,
                "sort_order": index,
                "is_expandable": 0,
            }
        ).insert(ignore_permissions=True)

    # TEMP: seed a handful of real preview pages with plain-text content so the
    # mobile reader has something genuine to fetch and render while the
    # AES-256-GCM encrypted_file pipeline is not yet built. Remove/replace once
    # the real encryption + content-import workflow exists.
    frappe.db.delete("Book Page", {"book": book.name})
    sample_pages = [
        (2, "Chapter Start", "پیش لفظ",
         "بسم اللہ الرحمن الرحیم\n\nیہ کتاب اس سوال کے گرد گھومتی ہے جو ہر انسان کے دل میں کسی نہ کسی موڑ پر ضرور پیدا ہوتا ہے: حقیقی سکون کہاں ملتا ہے؟ دنیا کی ساری رنگینیاں، کامیابیاں اور آسائشیں حاصل کر لینے کے بعد بھی دل کے کسی گوشے میں ایک خالی پن کیوں باقی رہ جاتا ہے؟"),
        (3, "Text", "پیش لفظ",
         "یہ تحریر کسی فلسفیانہ بحث کے لیے نہیں لکھی گئی، بلکہ ایک عام انسان کے اس سفر کی کہانی ہے جو اضطراب سے سکون کی طرف جاتا ہے۔ ہر باب میں ایک نیا زاویہ کھلتا ہے، اور قاری کو خود اپنے اندر جھانکنے کی دعوت دی جاتی ہے۔"),
        (4, "Text", "پیش لفظ",
         "اس کتاب کے صفحات پر آپ کو سادہ زبان میں گہری باتیں ملیں گی۔ مقصد یہ ہے کہ قاری صرف معلومات حاصل نہ کرے بلکہ اپنی ذات کے ساتھ ایک نیا تعلق قائم کرے۔"),
        (5, "Text", "پیش لفظ",
         "(یہ صرف ٹیسٹ کے لیے نمونہ متن ہے — اصل کتاب کا متن بعد میں شامل کیا جائے گا۔)"),
        (6, "Text", "پیش لفظ",
         "(نمونہ صفحہ نمبر 6 — ریڈر اسکرین کی جانچ کے لیے۔)"),
    ]
    for page_number, page_type, chapter_name, text in sample_pages:
        frappe.get_doc(
            {
                "doctype": "Book Page",
                "book": book.name,
                "translation": translation.name,
                "page_number": page_number,
                "page_type": page_type,
                "chapter": chapter_name,
                "content_text": text,
            }
        ).insert(ignore_permissions=True)

    config = frappe.get_single("App Remote Config")
    config.update(
        {
            "app_version_min_android": "1.0.0",
            "app_version_min_ios": "1.0.0",
            "maintenance_mode": 0,
            "maintenance_message": "",
            "default_language": "ur",
            "enable_google_login": 0,
            "enable_phone_login": 1,
            "enable_guest_preview": 1,
            "enable_page_sound": 1,
            "enable_page_curl": 1,
            "enable_screenshot_block": 1,
            "enable_watermark": 1,
            "support_whatsapp": "+923001234567",
            "privacy_policy_url": "https://dev.galaxylabs.online/privacy",
            "terms_url": "https://dev.galaxylabs.online/terms",
        }
    )
    config.save(ignore_permissions=True)

    upsert(
        "App Theme",
        "Classic Islamic Sepia",
        values={
            "theme_name": "Classic Islamic Sepia",
            "primary_color": "#0F5D4A",
            "secondary_color": "#C8A24A",
            "background_color": "#F8F1E3",
            "reader_paper_color": "#FFF8E8",
            "text_color": "#241B12",
            "pattern_opacity": 0.06,
            "card_radius": 24,
            "mode": "Sepia",
            "active": 1,
        },
    )

    reader_themes = [
        ("Light Reader", "Light", "#241B12", "#FFFFFF", 20, 1.8),
        ("Dark Reader", "Dark", "#F8F1E3", "#1A1F2C", 20, 1.8),
        ("Sepia Reader", "Sepia", "#241B12", "#FFF8E8", 20, 1.8),
    ]
    for theme_name, mode, font_color, background_color, font_size, line_height in reader_themes:
        upsert(
            "Reader Theme",
            theme_name,
            values={
                "theme_name": theme_name,
                "mode": mode,
                "font_color": font_color,
                "background_color": background_color,
                "pattern_opacity": 0.04,
                "default_font_size": font_size,
                "line_height": line_height,
                "active": 1,
            },
        )

    text_rows = [
        ("home.continue_reading", "Home", "Continue Reading", "مطالعہ جاری رکھیں"),
        ("book.buy_now", "Book", "Buy Now", "خریدیں"),
        ("book.redeem_code", "Book", "Redeem Code", "کوڈ درج کریں"),
        ("book.download", "Book", "Download", "ڈاؤن لوڈ کریں"),
        ("book.read", "Book", "Read", "مطالعہ کریں"),
        ("reader.settings", "Reader", "Reader Settings", "مطالعہ کی ترتیبات"),
        ("reader.bookmark", "Reader", "Bookmark", "نشان زد کریں"),
        ("profile.logout", "Profile", "Logout", "لاگ آؤٹ"),
    ]
    for key, module, default_text, urdu in text_rows:
        upsert(
            "App Text Key",
            key,
            values={"key": key, "module": module, "default_text": default_text, "active": 1},
        )
        upsert(
            "App Text Translation",
            filters={"text_key": key, "language": "ur"},
            values={"text_key": key, "language": "ur", "value": urdu, "version": 1, "active": 1},
        )

    campaign = upsert(
        "Promo Code Campaign",
        "Al-Qarar Launch Preview",
        values={
            "campaign_name": "Al-Qarar Launch Preview",
            "book": book.name,
            "code_type": "Single-use",
            "total_codes": 1,
            "purpose": "Marketing",
            "status": "Active",
        },
    )
    upsert(
        "Promo Code",
        "ALQARAR-PREVIEW",
        values={
            "campaign": campaign.name,
            "code": "ALQARAR-PREVIEW",
            "book": book.name,
            "status": "Unused",
            "max_uses": 1,
            "used_count": 0,
        },
    )


    payment_methods = [
        {
            "name": "bank_transfer_pkr",
            "method_name": "Bank Transfer - PKR",
            "method_code": "bank_transfer_pkr",
            "method_type": "Bank Transfer",
            "provider": "Bank",
            "country": "PK",
            "currency": "PKR",
            "enabled": 1,
            "display_to_user": 1,
            "sort_order": 1,
            "fee_type": "Unknown",
            "settlement_days": 1,
            "verification_mode": "Manual Review",
            "requires_payment_proof": 1,
            "account_title": "Al-Qarar Digital Library",
            "account_number": "Shown after account setup",
            "instructions": "Transfer the exact amount, then upload payment proof with your transaction reference.",
            "support_contact": "+923001234567",
            "test_mode": 0,
            "notes": "No bank login credentials are stored here.",
        },
        {
            "name": "jazzcash_pkr",
            "method_name": "JazzCash - PKR",
            "method_code": "jazzcash_pkr",
            "method_type": "Wallet",
            "provider": "JazzCash",
            "country": "PK",
            "currency": "PKR",
            "enabled": 1,
            "display_to_user": 1,
            "sort_order": 2,
            "fee_type": "Unknown",
            "settlement_days": 1,
            "verification_mode": "Reference Match",
            "requires_payment_proof": 1,
            "account_title": "Al-Qarar Digital Library",
            "merchant_id": "Shown after merchant setup",
            "instructions": "Send the exact amount through JazzCash and enter the transaction reference for review.",
            "support_contact": "+923001234567",
            "test_mode": 0,
        },
        {
            "name": "easypaisa_pkr",
            "method_name": "EasyPaisa - PKR",
            "method_code": "easypaisa_pkr",
            "method_type": "Wallet",
            "provider": "EasyPaisa",
            "country": "PK",
            "currency": "PKR",
            "enabled": 1,
            "display_to_user": 1,
            "sort_order": 3,
            "fee_type": "Unknown",
            "settlement_days": 1,
            "verification_mode": "Reference Match",
            "requires_payment_proof": 1,
            "account_title": "Al-Qarar Digital Library",
            "merchant_id": "Shown after merchant setup",
            "instructions": "Send the exact amount through EasyPaisa and enter the transaction reference for review.",
            "support_contact": "+923001234567",
            "test_mode": 0,
        },
        {
            "name": "international_card_future",
            "method_name": "International Card - Future",
            "method_code": "international_card_future",
            "method_type": "Card",
            "provider": "Other",
            "country": "International",
            "currency": "PKR",
            "enabled": 0,
            "display_to_user": 0,
            "sort_order": 99,
            "fee_type": "Unknown",
            "verification_mode": "API Polling",
            "requires_payment_proof": 0,
            "instructions": "Future card provider placeholder.",
            "test_mode": 1,
        },
    ]
    for method in payment_methods:
        method_name = method.pop("name")
        upsert("Payment Method", method_name, values=method)

    for method_code in ["bank_transfer_pkr", "jazzcash_pkr", "easypaisa_pkr"]:
        method_doc = frappe.get_doc("Payment Method", method_code)
        upsert(
            "Payment Reconciliation Rule",
            f"Default Rule - {method_doc.method_name}",
            values={
                "rule_name": f"Default Rule - {method_doc.method_name}",
                "payment_method": method_doc.name,
                "enabled": 1,
                "priority": 1,
                "match_by_reference": 1,
                "match_by_amount": 1,
                "match_by_phone": 0,
                "match_by_user_name": 0,
                "allowed_amount_difference": 0,
                "allowed_time_window_hours": 72,
                "auto_verify_min_confidence": 95,
                "create_entitlement_on_verify": 1,
                "notes": "Exact transaction reference and exact amount are treated as a strong match.",
            },
        )

    more_books = [
        {
            "title": "دیوان غالب",
            "slug": "diwan-e-ghalib",
            "author": "مرزا غالب",
            "category": "poetry",
            "description": "Complete collection of Mirza Ghalib's Urdu poetry with detailed annotations and commentary.",
            "status": "Published",
            "base_language": "ur",
            "is_paid": 1,
            "default_price": 1200,
            "currency": "PKR",
            "total_pages": 320,
            "sort_order": 2,
            "featured": 1,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 10,
        },
        {
            "title": "باغ و بہار",
            "slug": "bagh-o-bahar",
            "author": "میر امن دہلوی",
            "category": "stories",
            "description": "A classic Urdu story collection, considered the foundation of modern Urdu prose.",
            "status": "Published",
            "base_language": "ur",
            "is_paid": 0,
            "default_price": 0,
            "currency": "PKR",
            "total_pages": 280,
            "sort_order": 3,
            "featured": 0,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 15,
        },
        {
            "title": "علم الکمپیوٹر",
            "slug": "ilm-computer",
            "author": "ڈاکٹر طاہر حسین",
            "category": "technical",
            "description": "Comprehensive Urdu guide to computer science fundamentals, programming, and modern computing.",
            "status": "Published",
            "base_language": "ur",
            "is_paid": 1,
            "default_price": 800,
            "currency": "PKR",
            "total_pages": 450,
            "sort_order": 4,
            "featured": 0,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 12,
        },
        {
            "title": "تاریخ پاکستان",
            "slug": "tareekh-pakistan",
            "author": "پروفیسر محمد رفیق",
            "category": "history",
            "description": "A detailed historical account of Pakistan from 1947 to present day, covering political, social and cultural developments.",
            "status": "Published",
            "base_language": "ur",
            "is_paid": 0,
            "default_price": 0,
            "currency": "PKR",
            "total_pages": 600,
            "sort_order": 5,
            "featured": 0,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 10,
        },
        {
            "title": "Programming in Python",
            "slug": "python-programming",
            "author": "Dr. Ahmed Khan",
            "category": "educational",
            "description": "Learn Python programming from basics to advanced topics with practical exercises and real-world projects.",
            "status": "Published",
            "base_language": "en",
            "is_paid": 1,
            "default_price": 2000,
            "currency": "PKR",
            "total_pages": 520,
            "sort_order": 6,
            "featured": 1,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 20,
        },
        {
            "title": "The Art of Reading",
            "slug": "art-of-reading",
            "author": "Sarah Williams",
            "category": "educational",
            "description": "A transformative guide to effective reading habits, comprehension techniques, and lifelong learning.",
            "status": "Published",
            "base_language": "en",
            "is_paid": 0,
            "default_price": 0,
            "currency": "PKR",
            "total_pages": 190,
            "sort_order": 7,
            "featured": 0,
            "allow_preview": 1,
            "preview_start_page": 1,
            "preview_end_page": 15,
        },
    ]
    for book_data in more_books:
        slug = book_data["slug"]
        b = upsert("Digital Book", slug, values=book_data)

        lang = book_data["base_language"]
        translation = upsert(
            "Book Translation",
            filters={"book": b.name, "language": lang},
            values={
                "book": b.name,
                "language": lang,
                "title": book_data["title"],
                "direction": "RTL" if lang == "ur" else "LTR",
                "font_family": "Noto Nastaliq Urdu" if lang == "ur" else "Inter",
                "package_version": "1.0.0",
                "total_pages": book_data["total_pages"],
                "is_published": 1,
            },
        )

        frappe.get_doc({
            "doctype": "Book Chapter",
            "book": b.name,
            "translation": translation.name,
            "title": "باب اول" if lang == "ur" else "Chapter 1",
            "chapter_type": "Chapter",
            "start_page": 1,
            "end_page": min(50, book_data["total_pages"]),
            "sort_order": 1,
            "is_expandable": 0,
        }).insert(ignore_permissions=True)

    frappe.db.commit()
