from __future__ import annotations

import frappe
from frappe import _

from digital_library.api.utils import current_user, has_active_entitlement, public_book_row, resolve_book, require_user


@frappe.whitelist(allow_guest=True)
def list_books(category: str | None = None):
    user = current_user()
    filters = {"status": "Published"}
    if category:
        cat_name = frappe.db.get_value("Book Category", {"slug": category}, "name") or category
        filters["category"] = cat_name
    books = frappe.get_all(
        "Digital Book",
        filters=filters,
        fields=["name"],
        order_by="featured desc, sort_order asc, title asc",
    )
    return [
        {
            **public_book_row(row.name),
            "is_unlocked": has_active_entitlement(user, row.name),
        }
        for row in books
    ]
    user = current_user()
    books = frappe.get_all(
        "Digital Book",
        filters={"status": "Published"},
        fields=["name"],
        order_by="featured desc, sort_order asc, title asc",
    )
    return [
        {
            **public_book_row(row.name),
            "is_unlocked": has_active_entitlement(user, row.name),
        }
        for row in books
    ]


@frappe.whitelist(allow_guest=True)
def get_book_detail(book: str):
    name = resolve_book(book)
    user = current_user()
    translations = frappe.get_all(
        "Book Translation",
        filters={"book": name, "is_published": 1},
        fields=[
            "name",
            "language",
            "title",
            "subtitle",
            "translator",
            "direction",
            "font_family",
            "package_hash",
            "package_version",
            "total_pages",
            "release_notes",
        ],
        order_by="language asc",
    )
    return {
        **public_book_row(name),
        "is_unlocked": has_active_entitlement(user, name),
        "translations": translations,
        "toc": get_table_of_contents(name),
    }


@frappe.whitelist(allow_guest=True)
def get_table_of_contents(book: str):
    name = resolve_book(book)
    rows = frappe.get_all(
        "Book Chapter",
        filters={"book": name},
        fields=[
            "name",
            "translation",
            "parent_chapter",
            "title",
            "chapter_type",
            "start_page",
            "end_page",
            "sort_order",
            "is_expandable",
        ],
        order_by="sort_order asc, start_page asc",
    )
    return rows


@frappe.whitelist(allow_guest=True)
def check_entitlement(book: str):
    name = resolve_book(book)
    user = current_user()
    unlocked = has_active_entitlement(user, name)
    doc = frappe.get_cached_doc("Digital Book", name)
    return {
        "book": name,
        "user": user,
        "is_unlocked": unlocked,
        "allow_preview": bool(doc.allow_preview),
        "preview_start_page": doc.preview_start_page,
        "preview_end_page": doc.preview_end_page,
    }


@frappe.whitelist()
def get_admin_book_preview(book: str):
    """Returns all pages with decrypted content for preview.
    Accessible to System Managers, or any authenticated user who owns/free book."""
    name = resolve_book(book)
    user = current_user()

    book_doc = frappe.get_cached_doc("Digital Book", name)
    is_system = "System Manager" in frappe.get_roles()

    if not is_system:
        if user == "Guest":
            frappe.throw(_("Login required"), frappe.PermissionError)
        if book_doc.is_paid and not has_active_entitlement(user, name):
            if book_doc.allow_preview and book_doc.preview_start_page and book_doc.preview_end_page:
                return _preview_response(book_doc, name, book_doc.preview_start_page, book_doc.preview_end_page)
            frappe.throw(_("Purchase required to read this book"), frappe.PermissionError)

    preview_start = 1 if is_system else (book_doc.preview_start_page or 1)
    preview_end = book_doc.total_pages if is_system else (book_doc.preview_end_page or book_doc.total_pages)
    return _preview_response(book_doc, name, preview_start, preview_end)


def _preview_response(book_doc, name: str, page_start: int, page_end: int) -> dict:
    pages = frappe.get_all(
        "Book Page",
        filters={"book": name, "page_number": (">=", page_start), "page_number": ("<=", page_end)},
        fields=["page_number", "page_type", "chapter", "section_title", "encrypted_file"],
        order_by="page_number asc",
    )
    key = None
    trans = frappe.db.get_value("Book Translation", {"book": name, "is_published": 1}, "package_hash")
    if trans:
        key = trans
    for p in pages:
        p.content = _decrypt_for_preview(p.encrypted_file, key) if p.encrypted_file else ""
        del p.encrypted_file
    translations = frappe.get_all(
        "Book Translation",
        filters={"book": name, "is_published": 1},
        fields=["name", "language", "title", "total_pages"],
    )
    return {
        "book": name,
        "title": book_doc.title,
        "author": book_doc.author,
        "total_pages": book_doc.total_pages,
        "translations": translations,
        "pages": pages,
    }


def _decrypt_for_preview(encrypted_content: str, key: str | None) -> str:
    """Try to decrypt page content for admin preview. Return raw if decryption fails."""
    if not encrypted_content:
        return ""
    try:
        from cryptography.fernet import Fernet
        if key:
            f = Fernet(key.encode() if isinstance(key, str) else key)
            return f.decrypt(encrypted_content.encode()).decode()
    except Exception:
        pass
    try:
        import base64
        return base64.b64decode(encrypted_content).decode()
    except Exception:
        pass
    return encrypted_content[:200]


@frappe.whitelist()
def mock_download_package(book: str, translation: str | None = None):
    name = resolve_book(book)
    if not has_active_entitlement(frappe.session.user, name):
        entitlement = check_entitlement(name)
        if not entitlement.get("allow_preview"):
            frappe.throw("Book is locked")
    package = None
    if translation:
        package = frappe.db.get_value(
            "Book Translation",
            {"name": translation, "book": name, "is_published": 1},
            ["name", "package_file", "package_hash", "package_version"],
            as_dict=True,
        )
    return {
        "book": name,
        "translation": package.name if package else translation,
        "download_url": package.package_file if package and package.package_file else None,
        "package_hash": package.package_hash if package else None,
        "package_version": package.package_version if package else "mock-1.0.0",
        "mock": True,
        "message": "DRM package delivery placeholder. Real encrypted files will be added later.",
    }


@frappe.whitelist()
def get_book_pages(book: str, translation: str | None = None, page_from: int = 1, page_to: int | None = None):
    name = resolve_book(book)
    user = require_user()

    if not has_active_entitlement(user, name):
        doc = frappe.get_cached_doc("Digital Book", name)
        if not doc.allow_preview:
            frappe.throw(_("Book is locked. Purchase required."))
        page_from = max(page_from, doc.preview_start_page)
        page_to = min(page_to or doc.preview_end_page, doc.preview_end_page)

    filters: dict = {"book": name}
    if translation:
        filters["translation"] = translation

    pages = frappe.get_all(
        "Book Page",
        filters=filters,
        fields=["page_number", "encrypted_file", "content_text", "search_index", "page_type", "chapter"],
        order_by="page_number asc",
    )

    if page_to:
        pages = [p for p in pages if page_from <= p.page_number <= page_to]
    else:
        pages = [p for p in pages if p.page_number >= page_from]

    return {
        "book": name,
        "pages": pages,
        "total": len(pages),
    }


@frappe.whitelist()
def get_reader_config(book: str):
    name = resolve_book(book)
    user = current_user()
    doc = frappe.get_cached_doc("Digital Book", name)

    translations = frappe.get_all(
        "Book Translation",
        filters={"book": name, "is_published": 1},
        fields=["name", "language", "title", "translator", "direction", "font_family",
                "package_hash", "total_pages"],
        order_by="language asc",
    )

    themes = frappe.get_all(
        "Reader Theme",
        filters={"active": 1},
        fields=["name", "theme_name", "mode", "font_color", "background_color",
                "paper_texture", "default_font_size", "line_height"],
        order_by="theme_name asc",
    )

    return {
        "book": name,
        "title": doc.title,
        "author": doc.author,
        "total_pages": doc.total_pages,
        "is_unlocked": has_active_entitlement(user, name),
        "allow_preview": bool(doc.allow_preview),
        "preview_start_page": doc.preview_start_page,
        "preview_end_page": doc.preview_end_page,
        "translations": translations,
        "themes": themes,
        "default_font_size": 18,
    }


@frappe.whitelist()
def switch_translation(book: str, translation: str):
    name = resolve_book(book)
    if not frappe.db.exists("Book Translation", {"name": translation, "book": name, "is_published": 1}):
        frappe.throw(_("Translation not available"))
    trans = frappe.get_cached_doc("Book Translation", translation)
    return {
        "book": name,
        "translation": translation,
        "title": trans.title,
        "subtitle": trans.subtitle,
        "translator": trans.translator,
        "direction": trans.direction,
        "font_family": trans.font_family,
        "total_pages": trans.total_pages,
    }


@frappe.whitelist()
def search_in_book(book: str, query: str, translation: str | None = None):
    name = resolve_book(book)
    user = require_user()

    if not has_active_entitlement(user, name):
        frappe.throw(_("Purchase required to search in this book"))

    import hashlib
    query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()[:12]

    filters: dict = {"book": name}
    if translation:
        filters["translation"] = translation

    all_pages = frappe.get_all(
        "Book Page",
        filters=filters,
        fields=["page_number", "search_index", "chapter"],
        order_by="page_number asc",
    )

    results = []
    for p in all_pages:
        if p.search_index and query_hash in p.search_index:
            results.append({
                "page_number": p.page_number,
                "chapter": p.chapter,
            })

    return {
        "query": query,
        "results": results[:50],
        "total_matches": len(results),
    }


@frappe.whitelist(allow_guest=True)
def list_publishers_public():
    publishers = frappe.get_all(
        "Publisher Profile",
        filters={"status": "Active"},
        fields=["name", "company_name", "contact_email", "bio", "total_books", "verification_status"],
        order_by="company_name asc",
    )
    return publishers


@frappe.whitelist(allow_guest=True)
def list_books_by_publisher(publisher: str):
    user = current_user()
    books = frappe.get_all(
        "Digital Book",
        filters={"publisher": publisher, "status": "Published"},
        fields=["name"],
        order_by="sort_order asc, title asc",
    )
    return [
        {
            **public_book_row(row.name),
            "is_unlocked": has_active_entitlement(user, row.name),
        }
        for row in books
    ]


@frappe.whitelist(allow_guest=True)
def list_books_by_author(author: str):
    user = current_user()
    books = frappe.get_all(
        "Digital Book",
        filters={"author": author, "status": "Published"},
        fields=["name"],
        order_by="sort_order asc, title asc",
    )
    return [
        {
            **public_book_row(row.name),
            "is_unlocked": has_active_entitlement(user, row.name),
        }
        for row in books
    ]
