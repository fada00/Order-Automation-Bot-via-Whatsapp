import json
from decimal import Decimal

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
ACCESS_TOKEN = "EAAYjJkjWxhcBOzoO43m8PMzfwIvwZCXpQerNwroJBg9f2k9LQmUi2Om4ljWca1mizWTwfBRZB1rRlFK093vyZCbTXK7c1CefrLjhmkBn1EwxiieF6toBZAGpNLMha4UFD0k9CZB5sROmbnC9vXJhnkzPQYKN8XZCBWu5VVoL9IeCVLEXOAMGkbXEcfSHdMMMLlh2EmWhqSPDdP4I2L05xqC57mIltM0QWVRDLm20cim5cZD"
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
# 1) WhatsApp Mesaj Gönderme Fonksiyonları
# --------------------------------------------------------------------
def send_whatsapp_text(to_phone_number, message_text):
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "text": {"body": message_text}
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_text:", r.status_code, r.json())

def send_whatsapp_list(to_phone_number, header_text, body_text, button_text, sections):
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "footer": {"text": "Bir seçim yapın."},
            "action": {"button": button_text, "sections": sections}
        }
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_list:", r.status_code, r.json())

def send_whatsapp_buttons(to_phone_number, body_text, buttons):
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": buttons}
        }
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    url = f"{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages"
    r = requests.post(url, headers=headers, json=data)
    print("send_whatsapp_buttons:", r.status_code, r.json())

# --------------------------------------------------------------------
# 2) Veritabanı İşlemleri (Müşteri, Sipariş, Ürün, Opsiyon, Kupon)
# --------------------------------------------------------------------
def find_customer_by_phone(phone_number):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM customers WHERE phone_number = %s", (phone_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def create_customer(full_name, phone_number, address, reference=None):
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

def update_customer_info(customer_id, address=None):
    if address is None:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE customers SET address = %s WHERE id = %s", (address, customer_id))
    conn.commit()
    cur.close()
    conn.close()

def create_or_get_active_order(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM orders
        WHERE customer_id = %s AND status = 'draft'
        ORDER BY created_at DESC
        LIMIT 1
    """, (customer_id,))
    row = cur.fetchone()
    if row:
        order_id = row[0]
    else:
        cur.execute("""
            INSERT INTO orders (customer_id, total_price, status)
            VALUES (%s, 0, 'draft')
            RETURNING id
        """, (customer_id,))
        order_id = cur.fetchone()[0]
        conn.commit()
    cur.close()
    conn.close()
    return order_id

def finalize_order_in_db(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'hazırlanıyor' WHERE id = %s", (order_id,))
    conn.commit()
    cur.close()
    conn.close()

def add_product_to_order(order_id, product_id, quantity=1):
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
    cur.execute("UPDATE orders SET total_price = total_price + %s WHERE id = %s", (total_line_price, order_id))
    conn.commit()
    cur.close()
    conn.close()
    return detail_id

def add_option_to_order_detail(order_detail_id, option_id):
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
    cur.execute("UPDATE orders SET total_price = total_price + %s WHERE id = %s", (option_price, current_order_id))
    conn.commit()
    cur.close()
    conn.close()

def get_product_options(product_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT option_ids FROM products WHERE id = %s", (product_id,))
    result = cur.fetchone()

    if not result or not result['option_ids']:
        cur.close()
        conn.close()
        return []

    option_ids = tuple(result['option_ids'])

    cur.execute("SELECT id, name, price FROM product_options WHERE id = ANY(%s)", (option_ids,))
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return rows

def get_all_menus():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM menus ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_all_products():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, category, price FROM products ORDER BY category, id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def override_order_price_to_menu(order_id, menu_base_price, order_detail_ids):
    # Toplam sipariş detaylarının base fiyatını hesaplayalım:
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT SUM(price) FROM order_details WHERE id IN %s"
    cur.execute(query, (tuple(order_detail_ids),))
    base_sum = cur.fetchone()[0] or 0
    cur.close()
    conn.close()
    # Şu an siparişin toplamı:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
    current_total = cur.fetchone()[0]
    cur.close()
    conn.close()
    # Eklenen opsiyon fiyatı:
    extra_options = current_total - base_sum
    final_total = menu_base_price + extra_options
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (final_total, order_id))
    conn.commit()
    cur.close()
    conn.close()

def is_order_modifiable(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0] == 'draft'
    return False

# --- Kupon işlemleri ---
def apply_coupon_to_order(order_id, coupon_code):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM coupons WHERE code = %s", (coupon_code,))
    coupon = cur.fetchone()
    if not coupon:
        cur.close()
        conn.close()
        return None, "Kupon kodu geçersiz."
    if coupon["current_usage"] >= coupon["max_usage_limit"]:
        cur.close()
        conn.close()
        return None, "Bu kupon kullanım sınırına ulaşmış."
    cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    if not order:
        cur.close()
        conn.close()
        return None, "Sipariş bulunamadı."
    total = order["total_price"]
    discount = coupon["discount"]
    if 0 < discount < 1:
        new_total = total * (1 - discount)
    else:
        new_total = total - discount
        if new_total < 0:
            new_total = 0
    cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (new_total, order_id))
    cur.execute("UPDATE coupons SET current_usage = current_usage + 1 WHERE code = %s", (coupon_code,))
    conn.commit()
    cur.close()
    conn.close()
    return new_total, f"Kupon uygulandı. Yeni toplam fiyat: {new_total}₺"

# --------------------------------------------------------------------
# 3) user_states Yönetimi
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
    def convert_decimal(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError

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
              json.dumps(menu_products_queue,default=convert_decimal) if menu_products_queue else None,
              phone_number))
    else:
        cur.execute("""
            INSERT INTO user_states 
            (phone_number, order_id, step, last_detail_id, menu_products_queue, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """, (phone_number, order_id, step, last_detail_id,
              json.dumps(menu_products_queue,default=convert_decimal) if menu_products_queue else None))
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
# 4) Müşteri Bilgisi & Adres Akışı
# --------------------------------------------------------------------
def ask_update_or_continue(phone_number, customer):
    msg = (f"Kayıtlı bilgileriniz:\n"
           f"İsim: {customer['full_name']}\n"
           f"Referans: {customer.get('reference','')}\n"
           f"Adres: {customer.get('address','')}\n\n"
           "Adresinizi güncellemek ister misiniz?")
    send_whatsapp_buttons(
        phone_number,
        msg,
        [
            {"type": "reply", "reply": {"id": "UPDATE_ADDRESS_YES", "title": "Evet"}},
            {"type": "reply", "reply": {"id": "UPDATE_ADDRESS_NO", "title": "Hayır"}}
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "UPDATE_OR_CONTINUE")

def ask_name(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adınızı-soyadınızı giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NAME")

def ask_reference(phone_number):
    send_whatsapp_text(phone_number, "Varsa referans kodunuzu girin. Yoksa 'yok' yazabilirsiniz.")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_REFERENCE")

def ask_address(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adresinizi giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_ADDRESS")

def ask_address_confirmation(phone_number, current_address):
    body = f"Mevcut adresiniz:\n{current_address}\n\nAynı adresi kullanmak ister misiniz?"
    send_whatsapp_buttons(
        phone_number,
        body,
        [
            {"type": "reply", "reply": {"id": "ADDRESS_SAME", "title": "Aynı"}},
            {"type": "reply", "reply": {"id": "ADDRESS_NEW", "title": "Yeni Adres"}}
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ADDRESS_CONFIRM")

def ask_new_address(phone_number):
    send_whatsapp_text(phone_number, "Lütfen yeni adresinizi giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NEW_ADDRESS")

def ask_coupon_code(phone_number):
    send_whatsapp_text(phone_number, "Sipariş onayından önce, lütfen kupon kodunuzu girin (yoksa 'yok' yazın):")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_COUPON")

# --------------------------------------------------------------------
# 5) Menü veya Ürün Seçimi
# --------------------------------------------------------------------
def ask_menu_or_product(phone_number):
    send_whatsapp_buttons(
        phone_number,
        "Siparişinize başlamadan önce; menülerden mi yoksa doğrudan ürünlerden mi seçim yapmak istersiniz?",
        [
            {"type": "reply", "reply": {"id": "choose_menus", "title": "Menüler"}},
            {"type": "reply", "reply": {"id": "choose_products", "title": "Ürünler"}}
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_MENU_OR_PRODUCT")

def send_menus(phone_number):
    menus = get_all_menus()
    if menus:
        sections = [{"title": "Menüler", "rows": []}]
        for m in menus:
            row_id = f"menu_{m['id']}"
            title = m['name']
            desc = f"{m.get('description', '')} (Fiyat: {m.get('price', 0)}₺)"
            sections[0]["rows"].append({"id": row_id, "title": title, "description": desc})
        send_whatsapp_list(
            phone_number,
            header_text="Menü Seçimi",
            body_text="Lütfen bir menü seçin.",
            button_text="Seç",
            sections=sections
        )
        st = get_user_state(phone_number)
        set_user_state(phone_number, st["order_id"], "SELECTING_MENU")
    else:
        send_whatsapp_text(phone_number, "Şu anda menü bulunmamaktadır. Lütfen ürünleri seçiniz.")
        send_categories(phone_number)

def send_categories(phone_number):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM products")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    sections = [{"title": "Kategoriler", "rows": []}]
    for cat in categories:
        cat_val = cat[0]
        sections[0]["rows"].append({"id": f"category_{cat_val}", "title": cat_val, "description": f"{cat_val} kategorisindeki ürünler."})
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
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price FROM products WHERE category = %s ORDER BY id", (category,))
    products = cur.fetchall()
    cur.close()
    conn.close()
    sections = [{"title": f"{category} Ürünleri", "rows": []}]
    for p in products:
        row_id = f"product_{p['id']}"
        sections[0]["rows"].append({"id": row_id, "title": p['name'], "description": f"Fiyat: {p['price']}₺"})
    send_whatsapp_list(
        phone_number,
        header_text=f"{category} Kategorisi",
        body_text="Lütfen bir ürün seçin.",
        button_text="Seç",
        sections=sections
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "SELECTING_PRODUCT_BY_CATEGORY")

# --------------------------------------------------------------------
# Ürün Opsiyonları Sorma
# --------------------------------------------------------------------
def send_options_list(phone_number, order_detail_id, product_options):
    sections = [{"title": "Opsiyonlar", "rows": []}]
    for opt in product_options:
        row_id = f"option_{order_detail_id}_{opt['id']}"
        sections[0]["rows"].append({
            "id": row_id,
            "title": opt["name"],
            "description": f"+{opt['price']}₺"
        })
    sections[0]["rows"].append({
        "id": f"skip_option_{order_detail_id}",
        "title": "Opsiyon istemiyorum",
        "description": "Opsiyon eklemeden devam et"
    })
    send_whatsapp_list(
        to_phone_number=phone_number,
        header_text="Opsiyon Seçimi",
        body_text="Lütfen bu ürün için bir opsiyon seçin ya da opsiyonu atlamak için seçeneği kullanın.",
        button_text="Opsiyonlar",
        sections=sections
    )

# --------------------------------------------------------------------
# 6) Sipariş Finalizasyonu (Kupon kodu dahil)
# --------------------------------------------------------------------
def finalize_order(phone_number):
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
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]
    # Eğer menu_products_queue varsa, final fiyatı hesapla.
    if st.get("menu_products_queue"):
        menu_info = json.loads(st["menu_products_queue"])
        override_order_price_to_menu(order_id, menu_info["menu_base_price"], menu_info["order_details"])
    finalize_order_in_db(order_id)
    send_whatsapp_text(phone_number, "Siparişiniz onaylandı! Teşekkürler.\nYeni sipariş için istediğiniz zaman yazabilirsiniz.")
    clear_user_state(phone_number)

# Final override fonksiyonu: Menü için final fiyat hesaplaması
def override_order_price_to_menu(order_id, menu_base_price, order_detail_ids):
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT SUM(price) FROM order_details WHERE id IN %s"
    cur.execute(query, (tuple(order_detail_ids),))
    base_sum = cur.fetchone()[0] or 0
    cur.close()
    conn.close()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
    current_total = cur.fetchone()[0]
    cur.close()
    conn.close()
    extra_options = current_total - base_sum
    final_total = menu_base_price + extra_options
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (final_total, order_id))
    conn.commit()
    cur.close()
    conn.close()

# --------------------------------------------------------------------
# 7) handle_button_reply ve handle_list_reply Fonksiyonları
# --------------------------------------------------------------------
def handle_button_reply(phone_number, selected_id):
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]

    if selected_id == "choose_menus":
        send_menus(phone_number)
    elif selected_id == "choose_products":
        send_categories(phone_number)
    elif selected_id == "UPDATE_ADDRESS_YES":
        ask_address(phone_number)
    elif selected_id == "UPDATE_ADDRESS_NO":
        ask_menu_or_product(phone_number)
    elif selected_id == "ADDRESS_SAME":
        ask_coupon_code(phone_number)
    elif selected_id == "ADDRESS_NEW":
        ask_new_address(phone_number)
    elif selected_id == "more_options_yes":
        if st["step"] == "ASK_MORE_OPTIONS_FOR_PRODUCT":
            detail_id = st.get("last_detail_id")
            if not is_order_modifiable(order_id):
                send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                return
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
                    send_whatsapp_text(phone_number, "Opsiyon bulunamadı.")
            else:
                send_whatsapp_text(phone_number, "Ürün bulunamadı.")
        else:
            send_whatsapp_text(phone_number, "Geçersiz işlem.")
    elif selected_id == "more_options_no":
        send_whatsapp_buttons(
            phone_number,
            "Opsiyon eklendi. Başka ürün eklemek ister misiniz?",
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
            ]
        )
        set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
    elif selected_id == "ask_another_yes":
        ask_menu_or_product(phone_number)
    elif selected_id == "ask_another_no":
        finalize_order(phone_number)
    elif selected_id == "ORDER_STATUS_YES":
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
                {"type": "reply", "reply": {"id": "CONTINUE_ORDER", "title": "Devam"}},
                {"type": "reply", "reply": {"id": "NEW_ORDER", "title": "Yeni Sipariş"}}
            ]
        )
        set_user_state(phone_number, order_id, "ORDER_STATUS_CHECKED")
    elif selected_id == "CONTINUE_ORDER":
        ask_menu_or_product(phone_number)
    elif selected_id == "NEW_ORDER":
        finalize_order_internally(phone_number)
    else:
        send_whatsapp_text(phone_number, "Bilinmeyen buton seçimi.")

def handle_list_reply(phone_number, selected_id):
    st = get_user_state(phone_number)
    if not st or not st["order_id"]:
        return
    order_id = st["order_id"]

    if selected_id.startswith("category_"):
        category = selected_id[len("category_"):]
        send_products_and_menus_by_category(phone_number, category)
    elif selected_id.startswith("product_"):
        product_id = int(selected_id[len("product_"):])
        if not is_order_modifiable(order_id):
            send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
            return
        detail_id = add_product_to_order(order_id, product_id, 1)
        set_user_state(phone_number, order_id, "CONFIGURING_PRODUCT", last_detail_id=detail_id)
        product_options = get_product_options(product_id)
        if product_options:
            send_options_list(phone_number, detail_id, product_options)
        else:
            send_whatsapp_buttons(
                phone_number,
                "Ürün eklendi. Bu ürün için opsiyon bulunmamaktadır. Başka ürün eklemek ister misiniz?",
                [
                    {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                    {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
                ]
            )
            set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
    elif selected_id.startswith("menu_"):
        # --- Menü Seçimi: Menü içeriğini parse edip, her ürün için amount sayısı kadar
        # ayrı order_detail ekleyip, her birine opsiyon sorma işlemi yapılacak.
        menu_id = int(selected_id[len("menu_"):])
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM menus WHERE id = %s", (menu_id,))
        menu = cur.fetchone()
        cur.close()
        conn.close()
        if menu:
            try:
                # Menüdeki ürünler JSON formatında saklanıyor.
                menu_products = menu['products'][0]
            except Exception as e:
                send_whatsapp_text(phone_number, "Menü ürünleri okunamadı.")
                return
            # Oluşturacağımız queue: her bir eleman bir sözlük; örn. {"order_detail_id": ..., "product_id": ...}
            menu_queue = []
            for item in menu_products:
                prod_id = int(item.get("id"))
                amount = int(item.get("amount", 1))
                # Her bir ürün için amount kadar ayrı ayrı ekleme yapalım.
                for i in range(amount):
                    if not is_order_modifiable(order_id):
                        send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                        return
                    detail_id = add_product_to_order(order_id, prod_id, 1)
                    menu_queue.append({"order_detail_id": detail_id, "product_id": prod_id})
            # Kaydetmek istediğimiz menü bilgilerini state'e ekliyoruz.
            state_data = {"order_details": menu_queue, "menu_base_price": menu.get("price", 0)}
            set_user_state(phone_number, order_id, "PROCESSING_MENU_OPTIONS", menu_products_queue=state_data)
            # Queue'deki ilk ürün için opsiyonları soruyoruz.
            process_next_menu_product(phone_number)
        else:
            send_whatsapp_text(phone_number, "Menü bulunamadı.")
    elif selected_id.startswith("option_"):
        parts = selected_id.split('_')
        if len(parts) == 3:
            detail_id = int(parts[1])
            option_id = int(parts[2])
            if not is_order_modifiable(order_id):
                send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                return
            add_option_to_order_detail(detail_id, option_id)
            send_whatsapp_buttons(
                phone_number,
                "Opsiyon eklendi. Bu ürün için başka opsiyon eklemek ister misiniz?",
                [
                    {"type": "reply", "reply": {"id": "more_options_yes", "title": "Evet"}},
                    {"type": "reply", "reply": {"id": "more_options_no", "title": "Hayır"}}
                ]
            )
            set_user_state(phone_number, order_id, "ASK_MORE_OPTIONS_FOR_PRODUCT", last_detail_id=detail_id)
    elif selected_id.startswith("skip_option_"):
        # Kullanıcı opsiyon eklemek istemediğini belirledi.
        send_whatsapp_buttons(
            phone_number,
            "Opsiyon eklenmedi. Başka ürün eklemek ister misiniz?",
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
            ]
        )
        set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
    else:
        send_whatsapp_text(phone_number,
                           "Siparişiniz onaylandı! Teşekkürler.\nYeni sipariş için istediğiniz zaman yazabilirsiniz.")
        clear_user_state(phone_number)

# --------------------------------------------------------------------
# Yeni Yardımcı Fonksiyon: process_next_menu_product
# --------------------------------------------------------------------
def process_next_menu_product(phone_number):
    st = get_user_state(phone_number)
    if not st or not st.get("menu_products_queue"):
        send_whatsapp_buttons(
            phone_number,
            "Menüdeki tüm ürünler için opsiyon sorgulaması tamamlandı. Başka ürün eklemek ister misiniz?",
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
            ]
        )
        set_user_state(phone_number, st["order_id"], "ASK_ANOTHER_PRODUCT", menu_products_queue=None)
        return
    # Queue, state içinde bir sözlük olarak saklanıyor.
    queue_dict = st["menu_products_queue"]
    queue = queue_dict.get("order_details", [])
    if not queue:
        send_whatsapp_buttons(
            phone_number,
            "Menüdeki tüm ürünler için opsiyon sorgulaması tamamlandı. Başka ürün eklemek ister misiniz?",
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
            ]
        )
        set_user_state(phone_number, st["order_id"], "ASK_ANOTHER_PRODUCT", menu_products_queue=None)
        return
    next_item = queue.pop(0)  # Listenin ilk elemanını alıyoruz.
    # Güncellenmiş queue'yu state'e kaydediyoruz.
    queue_dict["order_details"] = queue
    set_user_state(phone_number, st["order_id"], "PROCESSING_MENU_OPTIONS", last_detail_id=next_item["order_detail_id"], menu_products_queue=queue_dict)
    # İlgili ürün için opsiyonları soruyoruz.
    product_options = get_product_options(next_item["product_id"])
    if product_options:
        # Opsiyon listesine ek olarak "Opsiyon seçmek istemiyorum" seçeneği ekleyelim.
        sections = [{"title": "Opsiyonlar", "rows": []}]
        for opt in product_options:
            row_id = f"option_{next_item['order_detail_id']}_{opt['id']}"
            sections[0]["rows"].append({"id": row_id, "title": opt["name"], "description": f"+{opt['price']}₺"})
        # Ekstra seçenek: opsiyon eklemek istemiyorum.
        sections[0]["rows"].append({
            "id": f"skip_option_{next_item['order_detail_id']}",
            "title": "Opsiyon istemiyorum",
            "description": "Opsiyon eklemeden devam et"
        })
        send_whatsapp_list(
            to_phone_number=phone_number,
            header_text="Opsiyon Seçimi",
            body_text="Lütfen bu ürün için bir opsiyon seçin ya da opsiyon eklemeden devam edin.",
            button_text="Opsiyonlar",
            sections=sections
        )
    else:
        # Eğer bu ürün için opsiyon yoksa, otomatik olarak sıradaki ürüne geç.
        process_next_menu_product(phone_number)

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
        try:
            entry = incoming_data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' in value:
                message = value['messages'][0]
                from_phone_number = message['from']

                customer_data = find_customer_by_phone(from_phone_number)
                state = get_user_state(from_phone_number)

                if not state:
                    if customer_data:
                        conn = get_db_connection()
                        cur = conn.cursor(cursor_factory=RealDictCursor)
                        cur.execute("""
                            SELECT * FROM orders
                            WHERE customer_id = %s AND status = 'draft'
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
                                "Aktif siparişiniz mevcut. Durumunu görmek ister misiniz?",
                                [
                                    {"type": "reply", "reply": {"id": "ORDER_STATUS_YES", "title": "Evet"}},
                                    {"type": "reply", "reply": {"id": "UPDATE_ADDRESS_NO", "title": "Hayır, devam et"}}
                                ]
                            )
                        else:
                            order_id = create_or_get_active_order(customer_data["id"])
                            set_user_state(from_phone_number, order_id, "UPDATE_OR_CONTINUE")
                            ask_update_or_continue(from_phone_number, customer_data)
                    else:
                        set_user_state(from_phone_number, None, "ASK_NAME")
                        ask_name(from_phone_number)
                else:
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
                        text_body = message.get('text', {}).get('body', '').strip()
                        current_step = state["step"]
                        if current_step == "ASK_NAME":
                            full_name = text_body
                            new_customer_id = create_customer(full_name, from_phone_number, address="", reference=None)
                            order_id = create_or_get_active_order(new_customer_id)
                            set_user_state(from_phone_number, order_id, "ASK_REFERENCE")
                            ask_reference(from_phone_number)
                        elif current_step == "ASK_REFERENCE":
                            set_user_state(from_phone_number, state["order_id"], "ASK_ADDRESS")
                            ask_address(from_phone_number)
                        elif current_step == "ASK_ADDRESS":
                            addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=addr)
                                set_user_state(from_phone_number, state["order_id"], "ASK_MENU_OR_PRODUCT")
                                send_whatsapp_text(from_phone_number, "Bilgileriniz kaydedildi. Lütfen seçim yapın.")
                                ask_menu_or_product(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_NEW_ADDRESS":
                            new_addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=new_addr)
                                ask_coupon_code(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_COUPON":
                            coupon_code = text_body.strip()
                            if coupon_code.lower() == "yok":
                                finalize_order_internally(from_phone_number)
                            else:
                                new_total, msg_text = apply_coupon_to_order(state["order_id"], coupon_code)
                                send_whatsapp_text(from_phone_number, msg_text)
                                finalize_order_internally(from_phone_number)
                        else:
                            if text_body.lower() in ["menu", "menü", "başla", "1"]:
                                ask_menu_or_product(from_phone_number)
                            elif text_body.lower() in ["tamam", "bitir", "bitti", "2"]:
                                finalize_order(from_phone_number)
                            else:
                                send_whatsapp_text(
                                    from_phone_number,
                                    "Kategori veya ürün seçmek için 'menu' yazabilir ya da butonları kullanabilirsiniz.\nSiparişi tamamlamak için 'tamam' yazabilirsiniz."
                                )
        except Exception as e:
            print("Hata:", e)
        return jsonify({"status": "ok"}), 200

# --------------------------------------------------------------------
# Uygulamayı Çalıştır
# --------------------------------------------------------------------
if __name__ == '__main__':
    app.run(port=80, debug=True)
