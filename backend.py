import os
import io
import base64
import json
import qrcode
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from jinja2 import Template
from weasyprint import HTML
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)
CORS(app)

# ─── Supabase Setup ────────────────────────────────────────────────────────────
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    if supabase:
        print("✅ Supabase connected")
    else:
        print("⚠️  Supabase not configured (set SUPABASE_URL and SUPABASE_KEY)")
except Exception as e:
    supabase = None
    print(f"⚠️  Supabase init failed: {e}")


# ─── Helper Functions ──────────────────────────────────────────────────────────

def generate_qr_base64(data):
    qr = qrcode.QRCode(box_size=10, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

def to_bangla_num(n):
    return str(n).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))

def to_roman(num):
    val  = [1000,900,500,400,100,90,50,40,10,9,5,4,1]
    syms = ['m','cm','d','cd','c','xc','l','xl','x','ix','v','iv','i']
    result = ''
    for i in range(len(val)):
        while num >= val[i]:
            result += syms[i]
            num -= val[i]
    return result

def format_keyword(index, keyword, style):
    prefixes = {
        "numbers":        f"{index}.",
        "bangla_numbers": f"{to_bangla_num(index)}.",
        "letters":        f"{chr(96 + index)}.",
        "upper_letters":  f"{chr(64 + index)}.",
        "bullets":        "•",
        "arrows":         "→",
        "roman":          f"{to_roman(index)}.",
        "dash":           "—",
        "none":           "",
    }
    prefix = prefixes.get(style, f"{index}.")
    return f"{prefix} {keyword}".strip()

def parse_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "off", "no")
    return default

def get_default_setting(key, fallback=""):
    if not supabase:
        return fallback
    try:
        res = supabase.table("settings").select("value").eq("key", key).maybe_single().execute()
        return res.data["value"] if res.data else fallback
    except Exception:
        return fallback


# ─── HTML Template ─────────────────────────────────────────────────────────────

html_template_str = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <title>Ebook Template</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Crimson+Pro:wght@400;600;700&family=Noto+Serif+Bengali:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @page { size: A4; margin: 0; }
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }

        :root {
            --primary-color: #1a1a2e; --accent-color: #e94560; --premium-gold: #d4af37;
            --secondary-dark: #16213e; --paper-white: #fffef9; --cream: #faf8f3;
            --text-primary: #1a1a1a; --text-secondary: #4a4a4a; --text-muted: #707070; --text-light: #ffffff;
            --font-display: 'Cormorant Garamond', serif; --font-serif: 'Crimson Pro', serif;
            --font-bengali: 'Noto Serif Bengali', serif; --font-sans: 'Inter', sans-serif;
            --title-xl: 72px; --title-lg: 48px; --title-md: 36px; --title-sm: 24px;
            --body-lg: 16px; --body-md: 14px; --body-sm: 12px; --caption: 11px; --micro: 9px;
            --space-1: 6px; --space-2: 12px; --space-3: 18px; --space-4: 24px; --space-5: 36px; --space-6: 48px;
            --safe-margin: 15mm;
        }

        body { font-family: var(--font-bengali); width: 210mm; background: #2d3142; }
        .page { width: 210mm; height: 297mm; background: var(--paper-white); position: relative; overflow: hidden; page-break-after: always; }

        /* ── FRONT COVER ── */
        .front-cover {
            background: linear-gradient(165deg, var(--paper-white) 0%, var(--cream) 100%);
            display: flex; flex-direction: column; justify-content: space-between;
            border: 3mm solid var(--primary-color);
            outline: 2px solid var(--premium-gold); outline-offset: -10px;
        }
        .cover-header { padding: var(--space-5) var(--space-4) 0; text-align: center; }
        .publisher-badge { display: inline-block; background: var(--primary-color); color: var(--text-light); padding: 6px var(--space-3); font-family: var(--font-sans); font-size: var(--micro); font-weight: 700; letter-spacing: 3px; text-transform: uppercase; border-radius: 2px; }
        .genre-tag { display: block; margin-top: var(--space-2); font-family: var(--font-sans); font-size: var(--caption); color: var(--accent-color); font-weight: 600; letter-spacing: 2px; text-transform: uppercase; }
        .cover-main { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; width: 100%; }
        .decorative-icon { width: 60px; height: auto; margin-bottom: var(--space-3); opacity: 0.7; display: block; margin-left: auto; margin-right: auto; }
        .book-title-en { font-family: var(--font-display); font-size: var(--title-xl); font-weight: 700; line-height: 0.85; color: var(--primary-color); letter-spacing: -1px; text-transform: uppercase; margin: 0; }
        .book-title-bn { font-family: var(--font-bengali); font-size: var(--title-md); font-weight: 700; color: var(--accent-color); margin-top: var(--space-3); display: inline-block; padding: 0 var(--space-4); position: relative; }
        .book-title-bn::before, .book-title-bn::after { content: ''; position: absolute; top: 50%; width: 35px; height: 2px; background: var(--accent-color); }
        .book-title-bn::before { right: 100%; margin-right: 12px; } .book-title-bn::after { left: 100%; margin-left: 12px; }
        .subtitle { font-family: var(--font-serif); font-size: var(--body-md); color: var(--text-secondary); font-style: italic; margin-top: var(--space-2); max-width: 380px; }
        .author-block { margin-top: var(--space-5); }
        .author-label { font-family: var(--font-sans); font-size: var(--caption); color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600; display: block; margin-bottom: 6px; }
        .author-name { font-family: var(--font-display); font-size: var(--title-sm); font-weight: 600; color: var(--text-primary); }
        .cover-footer { padding: 0 var(--space-4) var(--space-5); text-align: center; }
        .translator-info { padding-top: var(--space-3); border-top: 2px solid rgba(212,175,55,0.2); }
        .translator-label { font-family: var(--font-sans); font-size: var(--micro); color: var(--accent-color); text-transform: uppercase; letter-spacing: 2.5px; font-weight: 700; display: block; margin-bottom: 6px; }
        .translator-name { font-family: var(--font-bengali); font-size: var(--body-lg); font-weight: 700; color: var(--primary-color); }

        /* ── COPYRIGHT PAGE ── */
        .copyright-page { padding: var(--safe-margin); display: flex; flex-direction: column; font-family: var(--font-sans); font-size: var(--body-sm); line-height: 1.6; color: var(--text-secondary); }
        .copyright-header { text-align: center; padding-bottom: var(--space-3); border-bottom: 1px solid rgba(0,0,0,0.1); margin-bottom: var(--space-3); }
        .copyright-title { font-family: var(--font-display); font-size: var(--title-sm); color: var(--primary-color); font-weight: 600; }
        .layout-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
        .layout-table td { vertical-align: top; padding-bottom: var(--space-4); }
        .col-left { padding-right: 15px; } .col-right { padding-left: 15px; }
        .copyright-section h3 { font-family: var(--font-sans); font-size: var(--caption); font-weight: 700; color: var(--primary-color); text-transform: uppercase; margin-bottom: 6px; }
        .isbn-block { background: var(--cream); padding: var(--space-2); border-left: 3px solid var(--accent-color); margin-top: 5px; }
        .copyright-footer { text-align: center; padding-top: var(--space-3); border-top: 1px solid rgba(0,0,0,0.1); margin-top: var(--space-3); font-size: var(--caption); }

        /* ── INDEX PAGE ── */
        .index-page { padding: var(--safe-margin); display: flex; flex-direction: column; }
        .index-header { text-align: center; margin-bottom: var(--space-5); }
        .index-title { font-family: var(--font-display); font-size: var(--title-lg); font-weight: 700; color: var(--primary-color); text-transform: uppercase; letter-spacing: 3px; }
        .index-subtitle { font-family: var(--font-sans); font-size: var(--body-sm); color: var(--accent-color); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; }
        .toc-table { width: 100%; border-collapse: separate; border-spacing: 0 var(--space-2); }
        .toc-chapter { font-family: var(--font-bengali); font-size: var(--body-md); font-weight: 600; color: var(--text-primary); padding: var(--space-2) 0; position: relative; }
        .toc-chapter::after { content: ''; position: absolute; bottom: 8px; left: 0; right: 20px; height: 1px; background: repeating-linear-gradient(to right, var(--text-muted) 0, var(--text-muted) 3px, transparent 3px, transparent 7px); opacity: 0.3; }
        .toc-page { font-family: var(--font-display); font-size: var(--title-sm); font-weight: 700; color: var(--accent-color); text-align: right; white-space: nowrap; width: 70px; }

        /* ── KEYWORDS PAGE ── */
        .keywords-page { padding: var(--safe-margin); display: flex; flex-direction: column; }
        .keywords-header { text-align: center; margin-bottom: var(--space-5); padding-bottom: var(--space-3); border-bottom: 2px solid var(--premium-gold); }
        .keywords-page-title { font-family: var(--font-display); font-size: var(--title-lg); font-weight: 700; color: var(--primary-color); text-transform: uppercase; letter-spacing: 3px; }
        .keywords-page-subtitle { font-family: var(--font-sans); font-size: var(--body-sm); color: var(--accent-color); text-transform: uppercase; letter-spacing: 2px; font-weight: 600; display: block; margin-top: 6px; }
        .keywords-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3) var(--space-5); }
        .keyword-item { font-family: var(--font-bengali); font-size: var(--body-md); color: var(--text-primary); padding: var(--space-2) var(--space-3); background: var(--cream); border-left: 3px solid var(--accent-color); border-radius: 0 4px 4px 0; line-height: 1.5; }

        /* ── BACK COVER ── */
        .back-cover { display: flex; flex-direction: column; background: linear-gradient(165deg, var(--cream) 0%, var(--paper-white) 100%); }
        .bio-section { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: var(--space-6) var(--space-5); text-align: center; width: 100%; }
        .author-photo { width: 140px; height: 140px; border-radius: 50%; object-fit: cover; border: 4px solid var(--premium-gold); box-shadow: 0 4px 20px rgba(0,0,0,0.15); margin-bottom: var(--space-4); display: block; margin-left: auto; margin-right: auto; }
        .bio-name { font-family: var(--font-display); font-size: var(--title-sm); font-weight: 700; color: var(--primary-color); margin-bottom: 6px; text-transform: uppercase; }
        .bio-title-tag { font-family: var(--font-sans); font-size: var(--caption); color: var(--accent-color); text-transform: uppercase; letter-spacing: 2.5px; font-weight: 700; margin-bottom: var(--space-3); display: block; }
        .bio-description { font-family: var(--font-bengali); font-size: var(--body-md); line-height: 1.7; color: var(--text-secondary); max-width: 420px; margin: 0 auto; }
        .cta-section { background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-dark) 100%); padding: var(--space-5); display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); position: relative; }
        .cta-section::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, var(--accent-color) 0%, var(--premium-gold) 50%, var(--accent-color) 100%); }
        .cta-content { flex: 1; max-width: 65%; }
        .cta-headline { font-family: var(--font-display); font-size: var(--title-sm); font-weight: 700; color: var(--text-light); margin-bottom: var(--space-2); }
        .cta-text { font-family: var(--font-bengali); font-size: var(--body-md); color: rgba(255,255,255,0.85); line-height: 1.6; }
        .qr-container { background: white; padding: 10px; border-radius: 8px; width: 100px; height: 100px; display: flex; align-items: center; justify-content: center; border: 2px solid var(--premium-gold); }
        .qr-container img { width: 100%; height: 100%; border-radius: 4px; }
    </style>
</head>
<body>

    {% if show_front_cover %}
    <div class="page front-cover">
        <div class="cover-header">
            <div class="publisher-badge">{{ publisher_badge }}</div>
            <span class="genre-tag">{{ genre_tag }}</span>
        </div>
        <div class="cover-main">
            <svg class="decorative-icon" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                <path d="M50 10 L60 40 L90 40 L65 60 L75 90 L50 70 L25 90 L35 60 L10 40 L40 40 Z" fill="none" stroke="#d4af37" stroke-width="2"/>
            </svg>
            <h1 class="book-title-en">{{ book_title_en }}</h1>
            <div class="book-title-bn">{{ book_title_bn }}</div>
            <p class="subtitle">{{ subtitle }}</p>
            <div class="author-block">
                <span class="author-label">{{ author_label }}</span>
                <div class="author-name">{{ author_name }}</div>
            </div>
        </div>
        <div class="cover-footer">
            <div class="translator-info">
                <span class="translator-label">{{ translator_label }}</span>
                <div class="translator-name">{{ translator_name }}</div>
            </div>
        </div>
    </div>
    {% endif %}

    {% if show_copyright_page %}
    <div class="page copyright-page">
        <div class="copyright-header">
            <h2 class="copyright-title">{{ cp_title }}</h2>
            <div class="copyright-subtitle">{{ cp_subtitle }}</div>
        </div>
        <table class="layout-table">
            <tr>
                <td class="col-left">
                    <div class="copyright-section">
                        <h3>Original Work</h3>
                        <p><strong>Author:</strong> {{ cp_original_author }}</p>
                        <p><strong>Published:</strong> {{ cp_pub_year }}</p>
                        <p><strong>Language:</strong> {{ cp_lang }}</p>
                    </div>
                </td>
                <td class="col-right">
                    <div class="copyright-section">
                        <h3>This Edition</h3>
                        <p><strong>Translator:</strong> {{ cp_translator }}</p>
                        <p><strong>Publisher:</strong> {{ cp_publisher }}</p>
                        <p><strong>Edition:</strong> {{ cp_edition }}</p>
                    </div>
                </td>
            </tr>
            <tr>
                <td colspan="2">
                    <div class="copyright-section">
                        <h3>ISBN Information</h3>
                        <div class="isbn-block">
                            <p>{{ cp_isbn_13 }}</p>
                            <p>{{ cp_isbn_10 }}</p>
                        </div>
                    </div>
                </td>
            </tr>
            <tr>
                <td colspan="2">
                    <div class="copyright-section">
                        <h3>Copyright Notice</h3>
                        <p>{{ cp_copyright_text }}</p>
                    </div>
                </td>
            </tr>
            <tr>
                <td class="col-left">
                    <div class="copyright-section">
                        <h3>Contact</h3>
                        <p><strong>Web:</strong> {{ cp_contact_web }}</p>
                    </div>
                </td>
                <td class="col-right">
                    <div class="copyright-section">
                        <h3 style="visibility:hidden">Email</h3>
                        <p><strong>Email:</strong> {{ cp_contact_email }}</p>
                    </div>
                </td>
            </tr>
        </table>
        <div class="copyright-footer">
            <p>Designed &amp; Published in Bangladesh</p>
        </div>
    </div>
    {% endif %}

    {% if show_index_page %}
    <div class="page index-page">
        <div class="index-header">
            <h2 class="index-title">{{ index_title }}</h2>
            <span class="index-subtitle">{{ index_subtitle }}</span>
        </div>
        <table class="toc-table">
            {% for item in toc_list %}
            <tr>
                <td class="toc-chapter">{{ item.title }}</td>
                <td class="toc-page">{{ item.page }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endif %}

    {% if show_keywords_page and keywords_list %}
    <div class="page keywords-page">
        <div class="keywords-header">
            <h2 class="keywords-page-title">{{ keywords_page_title }}</h2>
            <span class="keywords-page-subtitle">{{ keywords_page_subtitle }}</span>
        </div>
        <div class="keywords-grid">
            {% for kw in keywords_list %}
            <div class="keyword-item">{{ kw }}</div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {% if show_back_cover %}
    <div class="page back-cover">
        <div class="bio-section">
            {% if bio_img_url %}
            <img src="{{ bio_img_url }}" alt="Translator" class="author-photo">
            {% endif %}
            <h3 class="bio-name">{{ bio_name }}</h3>
            <span class="bio-title-tag">{{ bio_title_tag }}</span>
            <p class="bio-description">{{ bio_description }}</p>
        </div>
        <div class="cta-section">
            <div class="cta-content">
                <h3 class="cta-headline">{{ cta_headline }}</h3>
                <p class="cta-text">{{ cta_text }}</p>
            </div>
            <div class="qr-container">
                <img src="{{ qr_code }}" alt="QR">
            </div>
        </div>
    </div>
    {% endif %}

</body>
</html>
"""


# ─── PDF Generation Endpoint ───────────────────────────────────────────────────

@app.route('/api/generate', methods=['POST'])
def generate_book():
    try:
        data = request.form

        # ── Section Visibility Toggles ──
        show_front_cover    = parse_bool(data.get("show_front_cover",    "true"))
        show_copyright_page = parse_bool(data.get("show_copyright_page", "true"))
        show_index_page     = parse_bool(data.get("show_index_page",     "true"))
        show_keywords_page  = parse_bool(data.get("show_keywords_page",  "true"))
        show_back_cover     = parse_bool(data.get("show_back_cover",     "true"))

        # ── Footer/QR Link (falls back to Supabase saved default) ──
        saved_link = get_default_setting("default_group_link", "https://facebook.com/groups/hidden-shelf")
        group_link = data.get("group_link", "") or saved_link

        # ── Keywords ──
        keyword_style   = data.get("keyword_numbering_style", "numbers")
        raw_keywords    = data.get("keywords", "[]")
        try:
            keyword_list_raw = json.loads(raw_keywords) if isinstance(raw_keywords, str) else raw_keywords
        except Exception:
            keyword_list_raw = []

        formatted_keywords = [
            format_keyword(i + 1, kw, keyword_style)
            for i, kw in enumerate(keyword_list_raw) if str(kw).strip()
        ]

        # ── Book Config ──
        book_config = {
            # Toggles
            "show_front_cover":    show_front_cover,
            "show_copyright_page": show_copyright_page,
            "show_index_page":     show_index_page,
            "show_keywords_page":  show_keywords_page,
            "show_back_cover":     show_back_cover,

            # Keywords
            "keywords_list":          formatted_keywords,
            "keywords_page_title":    data.get("keywords_page_title",    "Keywords"),
            "keywords_page_subtitle": data.get("keywords_page_subtitle", "মূল শব্দসমূহ"),

            # Front Cover
            "publisher_badge":  data.get("publisher_badge",  "THE HIDDEN SHELF CLASSICS"),
            "genre_tag":        data.get("genre_tag",        "Political Philosophy"),
            "book_title_en":    data.get("book_title_en",    "THE<br>PRINCE"),
            "book_title_bn":    data.get("book_title_bn",    "দ্য প্রিন্স"),
            "subtitle":         data.get("subtitle",         "A Timeless Manual on Power, Politics, and Leadership"),
            "author_label":     data.get("author_label",     "Original Masterpiece By"),
            "author_name":      data.get("author_name",      "Niccolò Machiavelli"),
            "translator_label": data.get("translator_label", "Bengali Translation & Analysis By"),
            "translator_name":  data.get("translator_name",  "Touhidul Islam"),

            # Copyright Page
            "cp_title":           data.get("cp_title",           "THE PRINCE"),
            "cp_subtitle":        data.get("cp_subtitle",        "দ্য প্রিন্স"),
            "cp_original_author": data.get("cp_original_author", "Niccolò Machiavelli"),
            "cp_pub_year":        data.get("cp_pub_year",        "1532 (Posthumous)"),
            "cp_lang":            data.get("cp_lang",            "Italian"),
            "cp_translator":      data.get("cp_translator",      "Touhidul Islam"),
            "cp_publisher":       data.get("cp_publisher",       "The Hidden Shelf"),
            "cp_edition":         data.get("cp_edition",         "February 2026"),
            "cp_isbn_13":         data.get("cp_isbn_13",         "ISBN-13: 978-0-123456-78-9"),
            "cp_isbn_10":         data.get("cp_isbn_10",         "ISBN-10: 0-123456-78-X"),
            "cp_copyright_text":  data.get("cp_copyright_text",  "© 2026 The Hidden Shelf. All rights reserved."),
            "cp_contact_web":     data.get("cp_contact_web",     "thehiddenshelf.com"),
            "cp_contact_email":   data.get("cp_contact_email",   "books@thehiddenshelf.com"),

            # Index / TOC
            "index_title":    data.get("index_title",    "Index"),
            "index_subtitle": data.get("index_subtitle", "Strategic Breakdown"),

            # Back Cover
            "bio_name":        data.get("bio_name",        "Touhidul Islam"),
            "bio_title_tag":   data.get("bio_title_tag",   "FOUNDER, THE HIDDEN SHELF"),
            "bio_description": data.get("bio_description", "A strategic thinker and content strategist analyzing complex geopolitical and historical events."),
            "cta_headline":    data.get("cta_headline",    "Join the Discussion"),
            "cta_text":        data.get("cta_text",        "Join our exclusive strategic community to discuss this book in depth."),
            "group_link":      group_link,
        }

        # ── Author Image ──
        if 'author_image' in request.files:
            image_file = request.files['author_image']
            encoded = base64.b64encode(image_file.read()).decode()
            book_config['bio_img_url'] = f"data:image/png;base64,{encoded}"
        else:
            book_config['bio_img_url'] = "https://i.pravatar.cc/300"

        book_config['qr_code'] = generate_qr_base64(group_link)

        # ── Chapter PDFs ──
        chapter_count = int(data.get("chapter_count", 0))
        toc_data = []
        uploaded_pdfs = []
        current_page_counter = sum([
            1 if show_front_cover else 0,
            1 if show_copyright_page else 0,
            1 if show_index_page else 0,
            1 if (show_keywords_page and formatted_keywords) else 0,
        ])

        for i in range(chapter_count):
            file_key  = f"chapter_{i}"
            title_key = f"chapter_{i}_title"
            if file_key in request.files:
                pdf_file   = request.files[file_key]
                pdf_reader = PdfReader(pdf_file)
                num_pages  = len(pdf_reader.pages)
                title      = data.get(title_key, f"Chapter {i + 1}")
                toc_data.append({"title": title, "page": to_bangla_num(current_page_counter)})
                uploaded_pdfs.append({"reader": pdf_reader, "title": title})
                current_page_counter += num_pages

        book_config['toc_list'] = toc_data

        # ── Render HTML → PDF ──
        rendered_html = Template(html_template_str).render(**book_config)
        template_pdf_bytes = io.BytesIO()
        HTML(string=rendered_html).write_pdf(template_pdf_bytes)
        template_reader = PdfReader(template_pdf_bytes)

        # ── Merge: front pages + chapters + back cover ──
        merger = PdfWriter()
        merger.add_metadata({
            "/Title":    f"{book_config['book_title_en'].replace('<br>', ' ')} - {book_config['book_title_bn']}",
            "/Author":   book_config['author_name'],
            "/Subject":  book_config['subtitle'],
            "/Producer": "The Hidden Shelf Publishing Engine",
            "/Creator":  "Python Automated Script",
            "/Keywords": f"{book_config['genre_tag']}, {book_config['author_name']}, {book_config['translator_name']}",
        })

        total_template_pages = len(template_reader.pages)
        front_page_count = total_template_pages - (1 if show_back_cover else 0)

        for i in range(front_page_count):
            merger.add_page(template_reader.pages[i])

        for item in uploaded_pdfs:
            merger.add_outline_item(title=item["title"], page_number=len(merger.pages))
            for page in item["reader"].pages:
                merger.add_page(page)

        if show_back_cover and total_template_pages > 0:
            merger.add_page(template_reader.pages[-1])

        output_stream = io.BytesIO()
        merger.write(output_stream)
        output_stream.seek(0)

        return send_file(
            output_stream,
            as_attachment=True,
            download_name="Full_Customized_Book.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─── Projects CRUD ─────────────────────────────────────────────────────────────

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Save a new project to Supabase."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        body   = request.get_json(force=True)
        name   = body.get("name", "Untitled Project")
        config = body.get("config", {})
        res    = supabase.table("projects").insert({"name": name, "config": config}).execute()
        return jsonify({"success": True, "project": res.data[0]}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all projects, newest first."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        res = supabase.table("projects").select("id, name, created_at, updated_at") \
                      .order("created_at", desc=True).execute()
        return jsonify({"projects": res.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a single project by ID (full config)."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        res = supabase.table("projects").select("*").eq("id", project_id).maybe_single().execute()
        if not res.data:
            return jsonify({"error": "Project not found"}), 404
        return jsonify({"project": res.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    """Update an existing project's name and/or config."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        body        = request.get_json(force=True)
        update_data = {}
        if "name"   in body: update_data["name"]   = body["name"]
        if "config" in body: update_data["config"] = body["config"]

        res = supabase.table("projects").update(update_data).eq("id", project_id).execute()
        if not res.data:
            return jsonify({"error": "Project not found"}), 404
        return jsonify({"success": True, "project": res.data[0]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        supabase.table("projects").delete().eq("id", project_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Settings (Default Footer Link etc.) ──────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all persisted settings."""
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        res      = supabase.table("settings").select("key, value").execute()
        settings = {row["key"]: row["value"] for row in res.data}
        return jsonify({"settings": settings}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    """
    Upsert one or more settings.
    Body example: { "default_group_link": "https://facebook.com/groups/xyz" }
    """
    if not supabase:
        return jsonify({"error": "Supabase not configured"}), 503
    try:
        body = request.get_json(force=True)
        rows = [{"key": k, "value": v} for k, v in body.items()]
        supabase.table("settings").upsert(rows, on_conflict="key").execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Health Check ──────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "supabase": supabase is not None}), 200


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
