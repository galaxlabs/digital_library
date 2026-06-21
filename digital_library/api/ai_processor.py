from __future__ import annotations

import json
import logging

import frappe
from frappe import _

logger = logging.getLogger("digital_library.ai_processor")

SUBMISSION_STATES = {
    "Uploaded": "Pending",
    "Pending": "Processing",
    "Processing": "Splitting Pages",
    "Splitting Pages": "Encrypting",
    "Encrypting": "Storing Pages",
    "Storing Pages": "Finalizing",
    "Finalizing": "Completed",
}


@frappe.whitelist(allow_guest=True)
def get_next_job():
    submission = frappe.get_all(
        "AI Book Submission",
        filters={"status": "Uploaded"},
        fields=["name", "title", "file_path", "file_url", "file_format"],
        limit=1,
        order_by="creation asc",
    )
    if not submission:
        frappe.local.response["http_status_code"] = 204
        return None
    s = submission[0]
    frappe.db.set_value("AI Book Submission", s.name, "status", "Pending")
    return {
        "submission_name": s.name,
        "title": s.title,
        "file_path": s.file_path,
        "file_url": s.file_url,
        "file_format": s.file_format or "TXT",
    }


@frappe.whitelist(allow_guest=True)
def update_status():
    body = frappe.local.request.get_json() or {}
    submission = body.get("submission")
    status = body.get("status")
    log = body.get("log")
    if not submission or not status:
        frappe.throw(_("submission and status are required"))
    doc = frappe.get_doc("AI Book Submission", submission)
    doc.status = status
    if log:
        doc.processing_log = (doc.processing_log or "") + f"\n{log}"
    doc.save(ignore_permissions=True)
    return {"ok": True, "status": doc.status}


@frappe.whitelist(allow_guest=True)
def store_pages():
    body = frappe.local.request.get_json() or {}
    submission = body.get("submission")
    pages_json = body.get("pages")
    category = body.get("category")
    confidence = body.get("confidence")
    page_count = body.get("page_count")

    if not submission or not pages_json:
        frappe.throw(_("submission and pages are required"))

    pages = json.loads(pages_json) if isinstance(pages_json, str) else pages_json
    sub_doc = frappe.get_doc("AI Book Submission", submission)

    sub_doc.db_set("ai_confidence_score", confidence)
    sub_doc.db_set("suggested_category", category)
    sub_doc.db_set("total_page_count", page_count or len(pages))
    sub_doc.db_set("status", "Storing Pages")

    book = sub_doc.book
    if not book:
        frappe.throw(_("AI Book Submission has no book reference"))

    translation = frappe.get_all(
        "Book Translation",
        filters={"book": book, "is_published": 1},
        limit=1,
        order_by="creation asc",
    )

    translation_name = translation[0].name if translation else None

    frappe.db.delete("Book Page", {"book": book, "translation": translation_name})

    for i, page in enumerate(pages, start=1):
        p = frappe.new_doc("Book Page")
        p.book = book
        if translation_name:
            p.translation = translation_name
        p.page_number = page.get("page_number", i)
        p.page_type = page.get("page_type", "Text")
        p.chapter = page.get("chapter")
        p.section_title = page.get("section_title")
        p.content_text = page.get("content")
        p.search_index = page.get("search_tokens")
        p.encrypted_file = page.get("encrypted_file")
        p.content_hash = page.get("content_hash")
        p.insert(ignore_permissions=True)

    frappe.db.commit()
    sub_doc.db_set("status", "Storing Pages (complete)")
    return {"ok": True, "pages_created": len(pages)}


@frappe.whitelist(allow_guest=True)
def finalize_book():
    body = frappe.local.request.get_json() or {}
    submission = body.get("submission")
    if not submission:
        frappe.throw(_("submission is required"))

    sub_doc = frappe.get_doc("AI Book Submission", submission)
    book = sub_doc.book

    book_doc = frappe.get_doc("Digital Book", book)

    category = sub_doc.suggested_category
    if category and not book_doc.category:
        book_doc.category = category

    page_count = frappe.db.count("Book Page", {"book": book})
    if page_count:
        book_doc.total_pages = page_count

    book_doc.status = "Published"
    book_doc.save(ignore_permissions=True)

    sub_doc.db_set("status", "Completed")
    sub_doc.db_set("published_book", book)
    sub_doc.db_set("published_on", frappe.utils.now())

    return {
        "ok": True,
        "book": book,
        "slug": book_doc.slug,
        "total_pages": page_count,
    }
