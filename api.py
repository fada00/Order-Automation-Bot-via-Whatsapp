import json
import requests
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# --------------------------------------------------------------------
# WhatsApp Cloud API Ayarları
# --------------------------------------------------------------------
WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"
VERIFY_TOKEN = "maydonozwp"
ACCESS_TOKEN = "EAAYjJkjWxhcBOxZCvTw8ZAlcVulzM62U48WYySe0XG9aafYRWq9d8pCYhvDukeH1WBkDtHSXrZArEh5fOhUUFLEF16uFfBxrG28rlyMkC5OOCyXOfHeTMA5TvNYWzTeLru4OzRh618t8uxVw4G3ZAGxbT1fOb2sZACZBlGO4vv8cja8MFyK7QIH4ZC8DHpJ7SfzZCZCzJFJWyviCePq0iSsqkdy0feZAEM2vnEFb47ZCbQE8Rql"  # kısaltılmıştır
PHONE_NUMBER_ID = "459475243924742"

# --------------------------------------------------------------------
# PostgreSQL Bağlantı Bilgileri
# --------------------------------------------------------------------
DB_HOST = "db-postgresql-fra1-87481-do-user-18505233-0.h.db.ondigitalocean.com"
DB_NAME = "dbpool"
DB_USER = "doadmin"
DB_PASS = "AVNS_5cVVGMm4MB4bAZjijsd"
DB_PORT = 25061


def get_db_connection():
    """Veritabanı bağlantısı döndürür."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        sslmode="require"
    )
    return conn


# --------------------------------------------------------------------
# 1) Yardımcı Fonksiyonlar: WhatsApp Mesaj Gönderme
# --------------------------------------------------------------------
def send_whatsapp_text(to_phone_number, message_text):
    """Basit text mesaj gönderir."""
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "text": {"body": message_text}
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_text:", r.status_code, r.json())


def send_whatsapp_list(to_phone_number, header_text, body_text, button_text, sections):
    """
    Interaktif liste gönderir (list type).
    sections formatı örneğin:
    [
      {
        "title": "Başlık",
        "rows": [
          {"id": "sec1", "title": "Seçenek 1", "description": "Açıklama 1"},
          ...
        ]
      },
      ...
    ]
    """
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": body_text
            },
            "footer": {
                "text": "Bir seçim yapın."
            },
            "action": {
                "button": button_text,
                "sections": sections
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_list:", r.status_code, r.json())


def send_whatsapp_buttons(to_phone_number, body_text, buttons):
    """
    Interaktif buton mesajı gönderir (button type).
    buttons formatı (WhatsApp Cloud API'ye uygun):
    [
      {
        "type": "reply",
        "reply": {
          "id": "some_id",
          "title": "Buton Başlığı"
        }
      },
      ...
    ]
    """
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_buttons:", r.status_code, r.json())


# --------------------------------------------------------------------
# 2) Yardımcı Fonksiyonlar: Veritabanı İşlemleri (Customers, Orders)
# --------------------------------------------------------------------
def find_customer_by_phone(phone_number):
    """Müşteriyi phone_number ile bul. Bulamazsa None döndür."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM customers WHERE phone_number = %s", (phone_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update_customer_info(customer_id, full_name=None, reference=None, address=None):
    """
    customers tablosunda ilgili alanları günceller (None olmayan değerleri).
    """
    fields = []
    values = []
    if full_name is not None:
        fields.append("full_name = %s")
        values.append(full_name)
    if reference is not None:
        fields.append("reference = %s")
        values.append(reference)
    if address is not None:
        fields.append("address = %s")
        values.append(address)
    if not fields:
        return
    sql_set_part = ", ".join(fields)
    sql = f"UPDATE customers SET {sql_set_part} WHERE id = %s"
    values.append(customer_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, tuple(values))
    conn.commit()
    cur.close()
    conn.close()


def create_customer(full_name, phone_number, address, reference=None):
    """customers tablosuna kayıt ekler."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO customers (full_name, phone_number, address, reference)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (full_name, phone_number, address, reference))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def create_or_get_active_order(customer_id):
    """
    Müşterinin 'hazırlanıyor' veya 'draft' durumundaki son siparişini getirir.
    Yoksa yeni oluşturur.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM orders
        WHERE customer_id = %s AND status IN ('hazırlanıyor','draft')
        ORDER BY created_at DESC
        LIMIT 1
    """, (customer_id,))
    row = cur.fetchone()
    if row:
        order_id = row[0]
    else:
        cur.execute("""
            INSERT INTO orders (customer_id, total_price, status)
            VALUES (%s, 0, 'hazırlanıyor')
            RETURNING id
        """, (customer_id,))
        order_id = cur.fetchone()[0]
        conn.commit()
    cur.close()
    conn.close()
    return order_id


def finalize_order_in_db(order_id):
    """Siparişi 'hazırlanıyor' durumuna çeker (örnek finalize işlemi)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE orders
        SET status = 'hazırlanıyor'
        WHERE id = %s
    """, (order_id,))
    conn.commit()
    cur.close()
    conn.close()


# --------------------------------------------------------------------
# Sipariş Detayları ve Opsiyonlar
# --------------------------------------------------------------------
def add_product_to_order(order_id, product_id, quantity=1):
    """
    Siparişe ürün ekler -> order_details kaydı oluşturur ve orders.total_price güncellenir.
    Dönen değer: order_detail.id
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
    p_row = cur.fetchone()
    if not p_row:
        cur.close()
        conn.close()
        raise ValueError("Ürün bulunamadı!")
    product_price = float(p_row[0])
    cur.execute("""
        INSERT INTO order_details (order_id, product_id, quantity, price)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (order_id, product_id, quantity, product_price))
    detail_id = cur.fetchone()[0]
    total_line_price = product_price * quantity
    cur.execute("""
        UPDATE orders
        SET total_price = total_price + %s
        WHERE id = %s
    """, (total_line_price, order_id))
    conn.commit()
    cur.close()
    conn.close()
    return detail_id


def add_option_to_order_detail(order_detail_id, option_id):
    """
    order_options tablosuna ekler, sipariş fiyatını opsiyon fiyatı kadar artırır.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT price FROM product_options WHERE id = %s", (option_id,))
    opt_row = cur.fetchone()
    if not opt_row:
        cur.close()
        conn.close()
        raise ValueError("Opsiyon bulunamadı!")
    option_price = float(opt_row[0])
    cur.execute("""
        INSERT INTO order_options (order_detail_id, option_id)
        VALUES (%s, %s)
        RETURNING id
    """, (order_detail_id, option_id))
    _new_option_id = cur.fetchone()[0]
    cur.execute("SELECT order_id FROM order_details WHERE id = %s", (order_detail_id,))
    od_row = cur.fetchone()
    if not od_row:
        cur.close()
        conn.close()
        raise ValueError("Order detail bulunamadı!")
    current_order_id = od_row[0]
    cur.execute("""
        UPDATE orders
        SET total_price = total_price + %s
        WHERE id = %s
    """, (option_price, current_order_id))
    conn.commit()
    cur.close()
    conn.close()


def get_product_options(product_id):
    """
    product_options tablosundan, belli bir ürüne ait opsiyonları döndürür.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, name, price
        FROM product_options
        WHERE product_id = %s
    """, (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_products():
    """
    Tüm ürünleri döndürür.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, category, price FROM products ORDER BY category, id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_menus():
    """
    Tüm menüleri döndürür.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM menus ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_menus_by_category(category):
    """
    Belirtilen kategoriye ait menüleri döndürür.
    (Tablonuzda menüler için 'category' kolonu olduğunu varsayıyoruz.)
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM menus WHERE category = %s ORDER BY id", (category,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# --------------------------------------------------------------------
# 3) user_states: Sohbet Adım (State) Yönetimi
# --------------------------------------------------------------------
def get_user_state(phone_number):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_states WHERE phone_number = %s", (phone_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def set_user_state(phone_number, order_id, step, last_detail_id=None, menu_products_queue=None):
    """
    user_states tablosunu günceller veya ekler.
    menu_products_queue: JSON listesi veya None.
    step: string (örneğin "ASK_NAME", "SELECTING_CATEGORY", "CONFIGURING_PRODUCT", vs.)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone_number FROM user_states WHERE phone_number = %s", (phone_number,))
    exists = cur.fetchone()
    if exists:
        cur.execute("""
            UPDATE user_states
            SET order_id = %s,
                step = %s,
                last_detail_id = %s,
                menu_products_queue = %s,
                updated_at = NOW()
            WHERE phone_number = %s
        """, (order_id, step, last_detail_id,
              json.dumps(menu_products_queue) if menu_products_queue else None,
              phone_number))
    else:
        cur.execute("""
            INSERT INTO user_states 
            (phone_number, order_id, step, last_detail_id, menu_products_queue, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """, (phone_number, order_id, step, last_detail_id,
              json.dumps(menu_products_queue) if menu_products_queue else None))
    conn.commit()
    cur.close()
    conn.close()


def clear_user_state(phone_number):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_states WHERE phone_number = %s", (phone_number,))
    conn.commit()
    cur.close()
    conn.close()


# --------------------------------------------------------------------
# 4) Ek Adımlar: Müşteri Bilgisi ve Adres Akışı
# --------------------------------------------------------------------
def ask_update_or_continue(phone_number, customer):
    """
    Müşteri kayıtlı ise: “Kayıtlı bilgileriniz: ... Güncellemek ister misiniz?”
    """
    full_name = customer["full_name"]
    ref = customer.get("reference", "") or ""
    msg = f"Kayıtlı bilgileriniz:\nİsim: {full_name}\nReferans: {ref}\n\nGüncellemek ister misiniz?"
    send_whatsapp_buttons(
        phone_number,
        msg,
        [
            {
                "type": "reply",
                "reply": {
                    "id": "UPDATE_INFO_YES",
                    "title": "Evet"
                }
            },
            {
                "type": "reply",
                "reply": {
                    "id": "UPDATE_INFO_NO",
                    "title": "Hayır"
                }
            }
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "UPDATE_OR_CONTINUE")


def ask_name(phone_number):
    """İsim-soyisim sormak için text mesaj gönderir."""
    send_whatsapp_text(phone_number, "Lütfen adınızı-soyadınızı giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NAME")


def ask_reference(phone_number):
    """Varsa referans kodu alalım."""
    send_whatsapp_text(phone_number, "Varsa bir referans kodu girin. Yoksa 'yok' yazabilirsiniz.")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_REFERENCE")


def ask_address(phone_number):
    """Adres bilgisini sorar."""
    send_whatsapp_text(phone_number, "Lütfen adresinizi yazın:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_ADDRESS")


def ask_address_confirmation(phone_number, current_address):
    """
    Sipariş öncesi; kayıtlı adresi kullanmak isteyip istemediğini sorar.
    """
    body = f"Mevcut kayıtlı adresiniz:\n{current_address}\n\nAynı adresi mi kullanacaksınız?"
    send_whatsapp_buttons(
        phone_number,
        body,
        [
            {
                "type": "reply",
                "reply": {
                    "id": "ADDRESS_SAME",
                    "title": "Aynı"
                }
            },
            {
                "type": "reply",
                "reply": {
                    "id": "ADDRESS_NEW",
                    "title": "Yeni Adres"
                }
            }
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ADDRESS_CONFIRM")


def ask_new_address(phone_number):
    """Yeni adres alır."""
    send_whatsapp_text(phone_number, "Lütfen yeni adresinizi giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NEW_ADDRESS")


# --------------------------------------------------------------------
# 5) Kategori, Ürün ve Menü Seçim Fonksiyonları
# --------------------------------------------------------------------
def send_categories(phone_number):
    """
    Öncelikle mevcut ürün kategorilerini listeleyelim.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM products")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    sections = [{
        "title": "Kategoriler",
        "rows": []
    }]
    for cat in categories:
        cat_val = cat[0]
        row_id = f"category_{cat_val}"
        sections[0]["rows"].append({
            "id": row_id,
            "title": cat_val,
            "description": f"{cat_val} kategorisindeki ürün ve menüler."
        })
    send_whatsapp_list(
        phone_number,
        header_text="Kategori Seçimi",
        body_text="Lütfen bir kategori seçin.",
        button_text="Kategoriler",
        sections=sections
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "SELECTING_CATEGORY")


def send_products_and_menus_by_category(phone_number, category):
    """
    Seçilen kategoriye ait menüleri ve ürünleri listeler.
    """
    menus = get_menus_by_category(category)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price FROM products WHERE category = %s ORDER BY id", (category,))
    products = cur.fetchall()
    cur.close()
    conn.close()
    sections = []
    if menus:
        menu_rows = []
        for m in menus:
            row_id = f"menu_{m['id']}"
            title = m['name']
            desc = f"{m.get('description', '')} (Fiyat: {m.get('price', 0)}₺)"
            menu_rows.append({
                "id": row_id,
                "title": title,
                "description": desc
            })
        sections.append({"title": "Menüler", "rows": menu_rows})
    if products:
        product_rows = []
        for p in products:
            row_id = f"product_{p['id']}"
            title = p['name']
            desc = f"Fiyat: {p['price']}₺"
            product_rows.append({
                "id": row_id,
                "title": title,
                "description": desc
            })
        sections.append({"title": "Ürünler", "rows": product_rows})
    send_whatsapp_list(
        phone_number,
        header_text=f"{category} Kategorisi",
        body_text="Lütfen menü veya ürün seçin.",
        button_text="Seç",
        sections=sections
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "SELECTING_PRODUCT_BY_CATEGORY")


def send_options_list(phone_number, order_detail_id, product_options):
    """
    Seçilen bir ürün için opsiyon listesini gönderir.
    """
    sections = [{
        "title": "Opsiyonlar",
        "rows": []
    }]
    for opt in product_options:
        row_id = f"option_{order_detail_id}_{opt['id']}"
        row_title = opt["name"]
        row_desc = f"+{opt['price']}₺"
        sections[0]["rows"].append({
            "id": row_id,
            "title": row_title,
            "description": row_desc
        })
    send_whatsapp_list(
        to_phone_number=phone_number,
        header_text="Opsiyon Seçimi",
        body_text="Bu ürün için opsiyon seçebilirsiniz (çoklu seçim mümkündür).",
        button_text="Opsiyonlar",
        sections=sections
    )
    # Kullanıcıdan opsiyon seçimine yönelik cevap bekleniyor; state 'CONFIGURING_PRODUCT' olarak kalıyor.


def ask_more_options(phone_number):
    """
    Kullanıcıya, ek opsiyon eklemek isteyip istemediğini sorar.
    """
    send_whatsapp_buttons(
        phone_number,
        "Başka opsiyon eklemek ister misiniz?",
        [
            {
                "type": "reply",
                "reply": {
                    "id": "more_options_yes",
                    "title": "Evet"
                }
            },
            {
                "type": "reply",
                "reply": {
                    "id": "more_options_no",
                    "title": "Hayır"
                }
            }
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_MORE_OPTIONS", last_detail_id=st.get("last_detail_id"), menu_products_queue=st.get("menu_products_queue"))


# --------------------------------------------------------------------
# 6) Finalize (Siparişi Onaylama) Süreci
# --------------------------------------------------------------------
def finalize_order(phone_number):
    """
    Siparişi tamamlamadan önce adres onayı ister.
    """
    st = get_user_state(phone_number)
    if not st:
        return
    customer = find_customer_by_phone(phone_number)
    if not customer:
        send_whatsapp_text(phone_number, "Müşteri kaydı bulunamadı, lütfen tekrar başlayın.")
        clear_user_state(phone_number)
        return
    current_address = customer.get("address", "")
    if not current_address:
        ask_new_address(phone_number)
    else:
        ask_address_confirmation(phone_number, current_address)


def finalize_order_internally(phone_number):
    """
    Adres onaylandıktan sonra siparişi finalize eder.
    """
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]
    finalize_order_in_db(order_id)
    send_whatsapp_text(phone_number,
                       "Siparişinizi onayladık! Teşekkür ederiz.\nYeni bir sipariş için istediğiniz zaman yazabilirsiniz."
                       )
    clear_user_state(phone_number)


# --------------------------------------------------------------------
# 7) handle_button_reply ve handle_list_reply Fonksiyonları
# --------------------------------------------------------------------
def handle_button_reply(phone_number, selected_id):
    """
    button_reply mesajlarını işler:
      * "UPDATE_INFO_YES", "UPDATE_INFO_NO" (müşteri bilgisi güncelleme)
      * "ADDRESS_SAME", "ADDRESS_NEW" (adres onayı)
      * "more_options_yes", "more_options_no"
      * "ORDER_STATUS_YES", "CONTINUE_ORDER", "NEW_ORDER"
      vb.
    """
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]

    if selected_id == "ORDER_STATUS_YES":
        # Aktif sipariş durumunu gönder
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT status, total_price FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        cur.close()
        conn.close()
        if order:
            send_whatsapp_text(phone_number, f"Aktif siparişiniz:\nDurum: {order['status']}\nToplam: {order['total_price']}₺")
        else:
            send_whatsapp_text(phone_number, "Sipariş bulunamadı.")
        send_whatsapp_buttons(
            phone_number,
            "Siparişinize devam etmek ister misiniz?",
            [
                {
                    "type": "reply",
                    "reply": {
                        "id": "CONTINUE_ORDER",
                        "title": "Devam"
                    }
                },
                {
                    "type": "reply",
                    "reply": {
                        "id": "NEW_ORDER",
                        "title": "Yeni Sipariş"
                    }
                }
            ]
        )
        set_user_state(phone_number, order_id, "ORDER_STATUS_CHECKED")

    elif selected_id == "CONTINUE_ORDER":
        send_categories(phone_number)

    elif selected_id == "NEW_ORDER":
        finalize_order_internally(phone_number)

    elif selected_id == "UPDATE_INFO_YES":
        set_user_state(phone_number, order_id, "UPDATING_NAME")
        send_whatsapp_text(phone_number, "Lütfen yeni isminizi-soyisminizi yazın:")

    elif selected_id == "UPDATE_INFO_NO":
        # Mevcut bilgileri kullanarak devam edelim
        set_user_state(phone_number, order_id, "SELECTING_CATEGORY")
        send_whatsapp_text(phone_number, "Bilgiler güncellenmeden devam ediliyor.\nKategori seçin:")
        send_categories(phone_number)

    elif selected_id == "ADDRESS_SAME":
        finalize_order_internally(phone_number)

    elif selected_id == "ADDRESS_NEW":
        ask_new_address(phone_number)

    elif selected_id.startswith("more_options_"):
        if selected_id == "more_options_yes":
            detail_id = st["last_detail_id"]
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT product_id FROM order_details WHERE id = %s", (detail_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                product_id = row[0]
                product_options = get_product_options(product_id)
                if product_options:
                    send_options_list(phone_number, detail_id, product_options)
                else:
                    send_categories(phone_number)
            else:
                send_whatsapp_text(phone_number, "Ürün bulunamadı.")
        else:
            send_categories(phone_number)

    elif selected_id.startswith("ask_another_"):
        if selected_id == "ask_another_yes":
            send_categories(phone_number)
        else:
            finalize_order(phone_number)

    else:
        send_whatsapp_text(phone_number, "Bilinmeyen buton seçimi.")


def handle_list_reply(phone_number, selected_id):
    """
    list_reply mesajlarını işler:
      * "category_{kategoriAdi}" → kategori seçimi
      * "product_{id}" → ürün seçimi
      * "menu_{id}" → menü seçimi (menüdeki ürünler JSON olarak saklanıyor)
      * Diğer durumlarda siparişi onayla gibi işlem yapar.
    """
    st = get_user_state(phone_number)
    if not st or not st["order_id"]:
        return
    order_id = st["order_id"]

    if selected_id.startswith("category_"):
        category = selected_id[len("category_"):]
        send_products_and_menus_by_category(phone_number, category)

    elif selected_id.startswith("product_"):
        product_id = int(selected_id[len("product_"):])
        detail_id = add_product_to_order(order_id, product_id, 1)
        set_user_state(phone_number, order_id, "CONFIGURING_PRODUCT", last_detail_id=detail_id, menu_products_queue=None)
        product_options = get_product_options(product_id)
        if product_options:
            send_options_list(phone_number, detail_id, product_options)
        else:
            send_whatsapp_buttons(
                phone_number,
                "Ürün eklendi. Başka ürün eklemek ister misiniz?",
                [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "ask_another_yes",
                            "title": "Evet"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "ask_another_no",
                            "title": "Hayır"
                        }
                    }
                ]
            )
            set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")

    elif selected_id.startswith("menu_"):
        menu_id = int(selected_id[len("menu_"):])
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM menus WHERE id = %s", (menu_id,))
        menu = cur.fetchone()
        cur.close()
        conn.close()
        if menu:
            try:
                menu_products = json.loads(menu['products'])
            except Exception as e:
                send_whatsapp_text(phone_number, "Menü ürünleri okunamadı.")
                return
            last_detail_id = None
            # Menüdeki her ürün için siparişe ekleme yapalım.
            for item in menu_products:
                prod_id = int(item.get("id"))
                amount = int(item.get("amount", 1))
                last_detail_id = add_product_to_order(order_id, prod_id, amount)
            set_user_state(phone_number, order_id, "CONFIGURING_PRODUCT", last_detail_id=last_detail_id, menu_products_queue=None)
            # Eklenen son ürünün opsiyonları varsa soralım.
            product_options = get_product_options(prod_id)
            if product_options:
                send_options_list(phone_number, last_detail_id, product_options)
            else:
                send_whatsapp_buttons(
                    phone_number,
                    "Menü eklendi. Başka ürün eklemek ister misiniz?",
                    [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "ask_another_yes",
                                "title": "Evet"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "ask_another_no",
                                "title": "Hayır"
                            }
                        }
                    ]
                )
                set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
        else:
            send_whatsapp_text(phone_number, "Menü bulunamadı.")

    else:
        send_whatsapp_text(phone_number,
                           "Siparişinizi onayladık! Teşekkür ederiz.\nYeni bir sipariş için istediğiniz zaman yazabilirsiniz.")
        clear_user_state(phone_number)


# --------------------------------------------------------------------
# 8) Webhook Fonksiyonu
# --------------------------------------------------------------------
def webhook(http_method):
    if http_method == 'GET':
        hub_mode = request.args.get('hub.mode')
        hub_challenge = request.args.get('hub.challenge')
        hub_verify_token = request.args.get('hub.verify_token')
        if hub_mode == 'subscribe' and hub_verify_token == VERIFY_TOKEN:
            return hub_challenge, 200
        else:
            return "Error verifying token", 403

    if http_method == 'POST':
        incoming_data = request.get_json()
        # print(json.dumps(incoming_data, indent=2))  # Debug için

        try:
            entry = incoming_data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' in value:
                message = value['messages'][0]
                from_phone_number = message['from']

                # Müşteri sorgulama
                customer_data = find_customer_by_phone(from_phone_number)
                state = get_user_state(from_phone_number)

                if not state:
                    if customer_data:
                        # Eğer aktif sipariş varsa, önce sipariş durumunu sorma opsiyonu sunalım.
                        conn = get_db_connection()
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        cur.execute("""
                            SELECT * FROM orders
                            WHERE customer_id = %s AND status IN ('hazırlanıyor','draft')
                            ORDER BY created_at DESC
                            LIMIT 1
                        """, (customer_data["id"],))
                        active_order = cur.fetchone()
                        cur.close()
                        conn.close()
                        if active_order:
                            order_id = active_order["id"]
                            set_user_state(from_phone_number, order_id, "ASK_ORDER_STATUS")
                            send_whatsapp_buttons(
                                from_phone_number,
                                "Aktif siparişiniz mevcut. Sipariş durumunu öğrenmek ister misiniz?",
                                [
                                    {
                                        "type": "reply",
                                        "reply": {
                                            "id": "ORDER_STATUS_YES",
                                            "title": "Evet"
                                        }
                                    },
                                    {
                                        "type": "reply",
                                        "reply": {
                                            "id": "UPDATE_INFO_NO",
                                            "title": "Hayır, devam et"
                                        }
                                    }
                                ]
                            )
                        else:
                            order_id = create_or_get_active_order(customer_data["id"])
                            set_user_state(from_phone_number, order_id, "UPDATE_OR_CONTINUE")
                            ask_update_or_continue(from_phone_number, customer_data)
                    else:
                        # Yeni müşteri: önce isim sorulur.
                        set_user_state(from_phone_number, None, "ASK_NAME")
                        ask_name(from_phone_number)
                else:
                    # State mevcut; gelen mesajın tipine göre işlem yapalım.
                    if 'interactive' in message:
                        interactive_type = message['interactive'].get('type')
                        if interactive_type == 'list_reply':
                            selected_id = message['interactive']['list_reply']['id']
                            handle_list_reply(from_phone_number, selected_id)
                        elif interactive_type == 'button_reply':
                            selected_id = message['interactive']['button_reply']['id']
                            handle_button_reply(from_phone_number, selected_id)
                        else:
                            send_whatsapp_text(from_phone_number, "Bu interaktif tür desteklenmiyor.")
                    else:
                        # Text mesaj işlemleri
                        text_body = message.get('text', {}).get('body', '').strip()
                        current_step = state["step"]
                        if current_step == "ASK_NAME":
                            full_name = text_body
                            new_customer_id = create_customer(full_name, from_phone_number, address="", reference=None)
                            order_id = create_or_get_active_order(new_customer_id)
                            set_user_state(from_phone_number, order_id, "ASK_REFERENCE")
                            ask_reference(from_phone_number)
                        elif current_step == "ASK_REFERENCE":
                            ref_text = text_body
                            if ref_text.lower() == "yok":
                                ref_text = ""
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], reference=ref_text)
                                set_user_state(from_phone_number, state["order_id"], "ASK_ADDRESS")
                                ask_address(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_ADDRESS":
                            addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=addr)
                                set_user_state(from_phone_number, state["order_id"], "SELECTING_CATEGORY")
                                send_whatsapp_text(from_phone_number, "Bilgileriniz kaydedildi. Şimdi kategori seçimi yapın.")
                                send_categories(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "UPDATING_NAME":
                            new_name = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], full_name=new_name)
                                set_user_state(from_phone_number, state["order_id"], "UPDATING_REFERENCE")
                                send_whatsapp_text(from_phone_number, "Yeni referans kodu (yoksa 'yok' yazın):")
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "UPDATING_REFERENCE":
                            new_ref = text_body
                            if new_ref.lower() == "yok":
                                new_ref = ""
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], reference=new_ref)
                                set_user_state(from_phone_number, state["order_id"], "SELECTING_CATEGORY")
                                send_whatsapp_text(from_phone_number, "Bilgiler güncellendi. Kategori seçimine geçelim.")
                                send_categories(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_NEW_ADDRESS":
                            new_addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=new_addr)
                                finalize_order_internally(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        else:
                            # Diğer genel metinler: örn. "menu", "tamam" gibi
                            if text_body.lower() in ["menu", "menü", "başla", "1"]:
                                send_categories(from_phone_number)
                            elif text_body.lower() in ["tamam", "bitir", "bitti", "2"]:
                                finalize_order(from_phone_number)
                            else:
                                send_whatsapp_text(
                                    from_phone_number,
                                    "Kategori veya ürün seçmek için 'menu' yazabilir ya da butonları kullanabilirsiniz.\n"
                                    "Siparişi tamamlamak için 'tamam' yazabilirsiniz."
                                )
        except Exception as e:
            print("Hata:", e)
        return jsonify({"status": "ok"}), 200


# --------------------------------------------------------------------
# 9) Uygulamayı Çalıştır
# --------------------------------------------------------------------
if __name__ == '__main__':
    app.run(port=80, debug=True)
