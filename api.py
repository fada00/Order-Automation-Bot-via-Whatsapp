import json
from datetime import datetime, timedelta  # Zaman aşımı için ekledik
from decimal import Decimal

import psycopg2
import requests
from flask import Flask, request, jsonify
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# --------------------------------------------------------------------
# WhatsApp Cloud API Ayarları
# --------------------------------------------------------------------
WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"
VERIFY_TOKEN = "maydonozwp"
ACCESS_TOKEN = "EAAYjJkjWxhcBO7LYII4UeGqU9bf4cbh4PAQ5vtSxePlV9GHONag9LYWzLsoBiFtQetGqXqcKBLWRFduqMlF7pSZAizpQ2ZA2TY0BNRLCIWmhgNJpxGCZCaRQHCoiMbOTevCezancU3sZAjloZBuAxdchSoFZC0OlJTp0vR5VBZBjYwlwrj21ZAZA5LZAlH3RZC1Dv5KqjK8RPqpSPdMcgOualWm7eystbpzby7wOojR3VS5v4MZD"
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


def add_address_to_customer(customer_id, new_address):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT address FROM customers WHERE id = %s", (customer_id,))
    row = cur.fetchone()
    addresses = []
    if row and row.get("address"):
        try:
            addresses = json.loads(row["address"])
            if not isinstance(addresses, list):
                addresses = []
        except Exception:
            addresses = []
    addresses.append(new_address)
    cur.execute("UPDATE customers SET address = %s WHERE id = %s", (json.dumps(addresses), customer_id))
    conn.commit()
    cur.close()
    conn.close()


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


def cancel_order_in_db(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'iptal' WHERE id = %s", (order_id,))
    conn.commit()
    cur.close()
    conn.close()


def create_customer(full_name, phone_number, address="[]", reference=None):
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


def update_order_address(order_id, address):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET address = %s WHERE id = %s", (address, order_id))
    conn.commit()
    cur.close()
    conn.close()


def update_customer_info(customer_id, address=None):
    if address is None:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE customers SET address = %s WHERE id = %s", (address, customer_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_customer_address(customer_id, index):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT address FROM customers WHERE id = %s", (customer_id,))
    row = cur.fetchone()
    addresses = []
    if row and row.get("address"):
        try:
            addresses = json.loads(row["address"])
        except:
            addresses = []
    if index < len(addresses):
        del addresses[index]
        cur = conn.cursor()
        cur.execute("UPDATE customers SET address = %s WHERE id = %s", (json.dumps(addresses), customer_id))
        conn.commit()
    cur.close()
    conn.close()


# Yeni yardımcı fonksiyonlar: aktif siparişleri getirme, belirli siparişi getirme
def get_active_orders_for_customer(customer_id):
    """
    Müşterinin teslim edilmemiş ve iptal edilmemiş siparişlerini döndürür.
    Örneğin; status değeri 'draft', 'hazırlanıyor', 'yolda' gibi olabilir.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM orders 
        WHERE customer_id = %s AND status NOT IN ('teslim edildi', 'iptal','draft')
        ORDER BY created_at DESC
    """, (customer_id,))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return orders


def get_order_by_id(order_id):
    """
    Verilen sipariş ID'sine ait sipariş bilgisini döndürür.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    cur.close()
    conn.close()
    return order


def list_active_orders(phone_number, customer_id):
    """
    Müşterinin aktif siparişlerini listeler.
    - Eğer sipariş durumu 'draft' ise iptal edilebilir (cancel_order_x şeklinde id atanır).
    - Diğer durumlar için sadece bilgi gösterilir (view_order_x şeklinde).
    Son bölümde “Yeni Sipariş Oluştur” seçeneği de eklenir.
    """
    orders = get_active_orders_for_customer(customer_id)
    if not orders:
        send_whatsapp_text(phone_number, "Aktif siparişiniz bulunmamaktadır. Yeni sipariş oluşturabilirsiniz.")
        ask_menu_or_product(phone_number)
        return

    cancelable = []
    non_cancelable = []
    for order in orders:
        order_info = f"Sipariş No: {order['id']}"
        if order['status'] == 'hazırlanıyor':
            cancelable.append({
                "id": f"cancel_order_{order['id']}",
                "title": order_info,
                "description": f"Durum: {order['status']} - Toplam: {order['total_price']}₺"
            })
        else:
            non_cancelable.append({
                "id": f"view_order_{order['id']}",
                "title": order_info,
                "description": f"Durum: {order['status']} - Toplam: {order['total_price']}₺"
            })

    sections = []
    if cancelable:
        sections.append({"title": "İptal Edilebilir", "rows": cancelable})
    if non_cancelable:
        sections.append({"title": "İptal Edilemeyen", "rows": non_cancelable})
    # Yeni sipariş oluşturma seçeneğini ekleyelim
    new_order_row = {"id": "new_order", "title": "Yeni Sipariş Oluştur", "description": ""}
    sections.append({"title": "Yeni Sipariş", "rows": [new_order_row]})

    send_whatsapp_list(
        phone_number,
        header_text="Ana Menü",
        body_text="Tekrar hoşgeldin!",
        button_text="Seçiniz",
        sections=sections
    )
    # Sipariş listesi gösterildiğini belirten state ayarlanıyor
    set_user_state(phone_number, None, "ORDER_LISTED")


def finalize_order_in_db(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = 'hazırlanıyor' WHERE id = %s", (order_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_product_by_id(product_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, price FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    return product


def get_options_for_order_detail(order_detail_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT po.name, po.price 
        FROM order_options oo
        JOIN product_options po ON oo.option_id = po.id
        WHERE oo.order_detail_id = %s
    """, (order_detail_id,))
    options = cur.fetchall()
    cur.close()
    conn.close()
    return options


def update_order_total(current_order_id, total_price):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET total_price = total_price + %s WHERE id = %s", (total_price, current_order_id))
    conn.commit()
    cur.close()
    conn.close()
    return True  # Başarıyla güncellendi


def add_product_to_order(order_id, product_id, quantity=1, skip_total_update=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT price FROM products WHERE id = %s", (product_id,))
    p_row = cur.fetchone()
    if not p_row:
        cur.close()
        conn.close()
        raise ValueError("Ürün bulunamadı!")
    product_price = float(p_row[0])
    price_to_insert = 0 if skip_total_update else product_price
    cur.execute("""
        INSERT INTO order_details (order_id, product_id, quantity, price)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (order_id, product_id, quantity, price_to_insert))
    detail_id = cur.fetchone()[0]
    if not skip_total_update:
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


def show_active_order(phone_number, order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT status, total_price, address FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    cur.close()
    conn.close()
    if order:
        message = (f"Aktif siparişiniz:\n"
                   f"Durum: {order['status']}\n"
                   f"Toplam: {order['total_price']}₺\n"
                   f"Adres: {order.get('address', 'Belirtilmemiş')}")
        if is_order_modifiable(order_id):
            send_whatsapp_buttons(
                phone_number,
                message,
                [
                    {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "İptal Et"}}
                ]
            )
        else:
            send_whatsapp_text(phone_number, message + "\nSiparişiniz iptal edilemez durumda.")
    else:
        send_whatsapp_text(phone_number, "Aktif sipariş bulunamadı.")


# --- Kupon işlemleri ---
# Kupon hesaplaması; DB güncellemesi sonrasında onay aşamasında yapılacak.
def calculate_coupon_discount(order_id, coupon_code):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM coupons WHERE code = %s", (coupon_code,))
    coupon = cur.fetchone()
    if not coupon:
        cur.close()
        conn.close()
        return None, "Kupon kodu geçersiz.", None, None
    cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    if not order:
        cur.close()
        conn.close()
        return None, "Sipariş bulunamadı.", None, None
    original_total = float(order["total_price"])
    discount = float(coupon["discount"])
    if 0 < discount < 1:
        discount_amount = original_total * discount
        new_total = original_total - discount_amount
    else:
        discount_amount = discount if original_total >= discount else original_total
        new_total = original_total - discount_amount
    cur.close()
    conn.close()
    return original_total, discount_amount, new_total, coupon


# Sipariş detaylarını listelemek için yeni yardımcı fonksiyon
def get_order_details(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT od.*, p.name 
        FROM order_details od 
        JOIN products p ON od.product_id = p.id 
        WHERE od.order_id = %s
    """, (order_id,))
    details = cur.fetchall()
    cur.close()
    conn.close()
    return details


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
    # 5 dakikadan eski state’ler sıfırlansın:
    if row:
        updated_at = row.get("updated_at")
        if updated_at and (datetime.utcnow() - updated_at) > timedelta(minutes=5):
            clear_user_state(phone_number)
            return None
    return row


def convert_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def set_user_state(phone_number, order_id, step, last_detail_id=None, menu_products_queue=None):
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
              json.dumps(menu_products_queue, default=convert_decimal) if menu_products_queue else None,
              phone_number))
    else:
        cur.execute("""
            INSERT INTO user_states 
            (phone_number, order_id, step, last_detail_id, menu_products_queue, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """, (phone_number, order_id, step, last_detail_id,
              json.dumps(menu_products_queue, default=convert_decimal) if menu_products_queue else None))
    conn.commit()
    cur.close()
    conn.close()


def create_new_order(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()
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
    full_name = customer['full_name']
    reference = customer.get('reference', '')
    try:
        addresses = json.loads(customer.get('address', '[]'))
        if not isinstance(addresses, list):
            addresses = []
    except Exception:
        addresses = []

    display_addresses = addresses[-3:]
    start_index = len(addresses) - len(display_addresses)

    msg = f"Kayıtlı bilgileriniz:\nİsim: {full_name}\nReferans: {reference}\n"
    msg += "Adresleriniz:\n" + "\n".join(
        f"{start_index + idx + 1}. {addr}" for idx, addr in enumerate(display_addresses))
    msg += "\n\nLütfen kullanmak istediğiniz adresi seçin ya da silmek istediğiniz adresi seçin. Yeni adres eklemek için de 'Yeni Adres Ekle' seçeneğini kullanın."

    select_rows = []
    delete_rows = []
    for idx, addr in enumerate(display_addresses):
        actual_index = start_index + idx
        select_rows.append({
            "id": f"select_address_{actual_index}",
            "title": addr,
            "description": "Kullan"
        })
        delete_rows.append({
            "id": f"delete_address_{actual_index}",
            "title": addr,
            "description": "Sil"
        })
    new_address_row = {"id": "add_new_address", "title": "Yeni Adres Ekle", "description": ""}

    sections = [
        {"title": "Adres Seçimi", "rows": select_rows},
        {"title": "Adres Silme", "rows": delete_rows},
        {"title": "Yeni", "rows": [new_address_row]}
    ]

    send_whatsapp_list(
        phone_number,
        header_text="Adres İşlemleri",
        body_text=msg,
        button_text="Seçiniz",
        sections=sections
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ADDRESS_SELECTION")


def ask_name(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adınızı-soyadınızı giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"] if st else None, "ASK_NAME")


def ask_reference(phone_number):
    send_whatsapp_text(phone_number, "Varsa referans kodunuzu girin. Yoksa 'yok' yazabilirsiniz.")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_REFERENCE")


def ask_address(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adresinizi giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_ADDRESS")


def update_customer_reference(customer_id, reference):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE customers SET reference = %s WHERE id = %s", (reference, customer_id))
    conn.commit()
    cur.close()
    conn.close()


def ask_address_confirmation(phone_number, current_address):
    """Unused"""
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


# Kupon kodu sorusuna geçiş; sipariş özetini onaylama aşamasına hazırlık yapılacak.
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
        sections[0]["rows"].append(
            {"id": f"category_{cat_val}", "title": cat_val, "description": f"{cat_val} kategorisindeki ürünler."})
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


def send_order_summary(phone_number, mode="new_product"):
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]
    details = get_order_details(order_id)
    summary = "Sipariş Özeti:\n"
    subtotal = 0.0

    for idx, item in enumerate(details, start=1):
        # Ürün fiyatını doğrudan products tablosundan çekiyoruz.
        product = get_product_by_id(item["product_id"])
        base_price = float(product["price"]) if product and product.get("price") is not None else 0.0
        quantity = item.get("quantity", 1)

        # Seçilmiş opsiyonlar varsa, fiyatlarını ekliyoruz.
        options = get_options_for_order_detail(item["id"])
        options_text = ""
        options_sum = 0.0
        if options:
            for opt in options:
                opt_price = float(opt["price"])
                options_text += f"   * {opt['name']} (+{opt_price}₺)\n"
                options_sum += opt_price

        line_total = (base_price + options_sum) * quantity
        subtotal += line_total

        summary += f"{idx}. {product['name']} - {base_price}₺ x {quantity} = {line_total}₺\n"
        if options_text:
            summary += options_text

    summary += f"\nAra Toplam: {subtotal}₺\n"
    try:
        d = json.loads(st.get("menu_products_queue", {})).get('discount_amount', 0.0)
    except:
        d = 0.0
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
    order_total_row = cur.fetchone()
    cur.close()
    conn.close()
    order_total = float(order_total_row[0]) if order_total_row and order_total_row[0] is not None else subtotal - d

    discount = (subtotal - order_total) + d
    if discount < 0:
        discount = 0.0

    summary += f"İndirim: {discount}₺\n\n"

    if mode == "new_product":
        summary += f"\nToplam Tutar: {subtotal - discount}₺\n"
        summary += "\nYeni bir ürün eklemek ister misiniz?"
        send_whatsapp_buttons(
            phone_number,
            summary,
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Siparişi Onayla"}}
            ]
        )
        set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
    elif mode == "confirm":
        summary += f"Ödenecek Tutar: {subtotal-discount}₺\n"
        send_whatsapp_buttons(
            phone_number,
            summary,
            [
                {"type": "reply", "reply": {"id": "CONFIRM_ORDER", "title": "Onayla"}},
                {"type": "reply", "reply": {"id": "CANCEL_ORDER", "title": "İptal Et"}}
            ]
        )


# --------------------------------------------------------------------
# 6) Sipariş Finalizasyonu (Onaylama aşaması)
# --------------------------------------------------------------------
def finalize_order_internally(phone_number):
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]
    # Menü siparişlerinde ek hesaplama yapılmış olabilir.
    if st.get("menu_products_queue") and st["step"] == "PROCESSING_MENU_OPTIONS":
        menu_info = json.loads(st["menu_products_queue"])
        override_order_price_to_menu(order_id, menu_info["menu_base_price"], menu_info["order_details"])
    finalize_order_in_db(order_id)
    send_whatsapp_text(phone_number,
                       "Siparişiniz onaylandı! Teşekkürler.\nYeni sipariş için istediğiniz zaman yazabilirsiniz.")
    clear_user_state(phone_number)


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
    elif selected_id == "CANCEL_ORDER":
        if is_order_modifiable(order_id):
            cancel_order_in_db(order_id)
            send_whatsapp_text(phone_number, "Siparişiniz iptal edildi.")
        else:
            send_whatsapp_text(phone_number, "Sipariş iptal edilemez durumda.")
        clear_user_state(phone_number)
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
        # send_whatsapp_buttons(
        #     phone_number,
        #     "Opsiyon eklendi. Başka ürün eklemek ister misiniz?",
        #     [
        #         {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
        #         {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
        #     ]
        # )
        send_order_summary(phone_number)
        set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
    elif selected_id == "ask_another_yes":
        ask_menu_or_product(phone_number)
    elif selected_id == "ask_another_no":
        ask_coupon_code(phone_number)
    elif selected_id == "ORDER_STATUS_YES":
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT status, total_price FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        cur.close()
        conn.close()
        if order:
            send_whatsapp_text(phone_number,
                               f"Aktif siparişiniz:\nDurum: {order['status']}\nToplam: {order['total_price']}₺")
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
    # Yeni eklenen onaylama butonları:
    elif selected_id == "CONFIRM_ORDER":
        # Kullanıcının sipariş özetini onayladığını kabul ediyoruz
        st = get_user_state(phone_number)
        order_id = st["order_id"]
        coupon_data = None
        try:
            if st.get("menu_products_queue"):
                coupon_data = json.loads(st["menu_products_queue"])
        except Exception as e:
            coupon_data = None
        if coupon_data and coupon_data.get("coupon_code"):
            new_total = coupon_data.get("new_total")
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (new_total, order_id))
            conn.commit()
            cur.close()
            conn.close()
            coupon_code = coupon_data.get("coupon_code")
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE coupons SET current_usage = current_usage + 1 WHERE code = %s", (coupon_code,))
            conn.commit()
            cur.close()
            conn.close()
        finalize_order_in_db(order_id)
        send_whatsapp_text(phone_number, "Siparişiniz onaylandı! Teşekkürler.")
        clear_user_state(phone_number)
    elif selected_id == "CANCEL_ORDER":
        send_whatsapp_text(phone_number, "Sipariş iptal edildi.")
        clear_user_state(phone_number)
    elif selected_id == "new_order":
        customer = find_customer_by_phone(phone_number)
        if customer:
            customer = find_customer_by_phone(phone_number)
            ask_update_or_continue(phone_number,customer)
        else:
            send_whatsapp_text(phone_number, "Müşteri kaydı bulunamadı.")
        return
    else:
        send_whatsapp_text(phone_number, "Bilinmeyen buton seçimi.")


def handle_list_reply(phone_number, selected_id):
    st = get_user_state(phone_number)
    if not st:
        return

    if selected_id.startswith("cancel_order_"):
        order_id = int(selected_id[len("cancel_order_"):])
        order = get_order_by_id(order_id)
        if order and order['status'] == 'hazırlanıyor':
            cancel_order_in_db(order_id)
            send_whatsapp_text(phone_number, f"Siparişiniz (No: {order_id}) iptal edildi.")
            send_whatsapp_buttons(
                phone_number,
                "Yeni sipariş oluşturmak ister misiniz?",
                [
                    {"type": "reply", "reply": {"id": "new_order", "title": "Yeni Sipariş"}},
                    # {"type": "reply", "reply": {"id": "continue_order", "title": "Devam Et"}}
                ]
            )
            set_user_state(phone_number, None, "ORDER_LISTED")
        else:
            send_whatsapp_text(phone_number, "Bu sipariş iptal edilemez durumda.")
        return

    elif selected_id.startswith("view_order_"):
        order_id = int(selected_id[len("view_order_"):])
        order = get_order_by_id(order_id)
        if order:
            msg = (
                f"Sipariş No: {order['id']}\n"
                f"Durum: {order['status']}\n"
                f"Toplam: {order['total_price']}₺\n"
                f"Adres: {order.get('address', 'Belirtilmemiş')}"
            )
            send_whatsapp_text(phone_number, msg)
            send_whatsapp_buttons(
                phone_number,
                "Yeni sipariş oluşturmak ister misiniz?",
                [
                    {"type": "reply", "reply": {"id": "new_order", "title": "Yeni Sipariş"}},
                    # {"type": "reply", "reply": {"id": "continue_order", "title": "Devam Et"}}
                ]
            )
            set_user_state(phone_number, None, "ORDER_LISTED")
        else:
            send_whatsapp_text(phone_number, "Sipariş bulunamadı.")
        return

    elif selected_id == "new_order":
        customer = find_customer_by_phone(phone_number)
        if customer:
            customer = find_customer_by_phone(phone_number)
            ask_update_or_continue(phone_number,customer)
        else:
            send_whatsapp_text(phone_number, "Müşteri kaydı bulunamadı.")
        return

    elif selected_id == "continue_order":
        send_whatsapp_text(phone_number, "Mevcut siparişinize devam edebilirsiniz.")
        clear_user_state(phone_number)
        return

    if selected_id.startswith("category_"):
        category = selected_id[len("category_"):]
        send_products_and_menus_by_category(phone_number, category)
    elif selected_id.startswith("product_"):
        order_id = st["order_id"]
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
        menu_id = int(selected_id[len("menu_"):])
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM menus WHERE id = %s", (menu_id,))
        menu = cur.fetchone()
        cur.close()
        conn.close()
        if menu:
            order_id = st["order_id"]
            try:
                menu_products = menu['products'][0]
            except Exception as e:
                send_whatsapp_text(phone_number, "Menü ürünleri okunamadı.")
                return
            menu_queue = []
            update_order_total(order_id, menu.get("price", 0))
            for item in menu_products:
                prod_id = int(item.get("id"))
                amount = int(item.get("amount", 1))
                for i in range(amount):
                    if not is_order_modifiable(order_id):
                        send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                        return
                    detail_id = add_product_to_order(order_id, prod_id, 1, skip_total_update=True)
                    menu_queue.append({"order_detail_id": detail_id, "product_id": prod_id})
            state_data = {"order_details": menu_queue, "menu_base_price": menu.get("price", 0)}
            set_user_state(phone_number, order_id, "PROCESSING_MENU_OPTIONS", menu_products_queue=state_data)
            process_next_menu_product(phone_number)
        else:
            send_whatsapp_text(phone_number, "Menü bulunamadı.")
    elif selected_id.startswith("option_"):
        order_id = st["order_id"]
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
        # send_whatsapp_buttons(
        #     phone_number,
        #     "Opsiyon eklenmedi. Başka ürün eklemek ister misiniz?",
        #     [
        #         {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
        #         {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
        #     ]
        # )
        # set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")

        send_order_summary(phone_number)

    elif selected_id.startswith("select_address_"):
        index = int(selected_id[len("select_address_"):])
        customer = find_customer_by_phone(phone_number)
        try:
            addresses = json.loads(customer.get("address", "[]"))
            if not isinstance(addresses, list):
                addresses = []
        except Exception:
            addresses = []
        if index < len(addresses):
            selected_address = addresses[index]
            order_id = create_new_order(customer.get("id"))
            set_user_state(phone_number, order_id, "ASK_MENU_OR_PRODUCT")
            update_order_address(order_id, selected_address)
            send_whatsapp_text(phone_number, f"Seçtiğiniz adres: {selected_address}\nSiparişinize devam edebilirsiniz.")
            set_user_state(phone_number, order_id, "ASK_MENU_OR_PRODUCT")
            ask_menu_or_product(phone_number)
        else:
            send_whatsapp_text(phone_number, "Geçersiz adres seçimi.")
    elif selected_id.startswith("delete_address_"):
        index = int(selected_id[len("delete_address_"):])
        customer = find_customer_by_phone(phone_number)
        if customer:
            delete_customer_address(customer["id"], index)
            send_whatsapp_text(phone_number,
                               "Adres silindi. Lütfen işleminize devam etmek için tekrar adres seçimi yapınız.")
            customer = find_customer_by_phone(phone_number)
            ask_update_or_continue(phone_number, customer)
        else:
            send_whatsapp_text(phone_number, "Müşteri kaydı bulunamadı.")
    elif selected_id == "add_new_address":
        ask_new_address(phone_number)

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

    next_item = queue.pop(0)
    queue_dict["order_details"] = queue
    set_user_state(
        phone_number,
        st["order_id"],
        "PROCESSING_MENU_OPTIONS",
        last_detail_id=next_item["order_detail_id"],
        menu_products_queue=queue_dict
    )
    product_options = get_product_options(next_item["product_id"])
    product = get_product_by_id(next_item["product_id"])
    product_name = product["name"] if product else "Ürün"

    if product_options:
        sections = [{"title": "Opsiyonlar", "rows": []}]
        for opt in product_options:
            row_id = f"option_{next_item['order_detail_id']}_{opt['id']}"
            sections[0]["rows"].append({
                "id": row_id,
                "title": opt["name"],
                "description": f"+{opt['price']}₺"
            })
        sections[0]["rows"].append({
            "id": f"skip_option_{next_item['order_detail_id']}",
            "title": "Opsiyon istemiyorum",
            "description": "Opsiyon eklemeden devam et"
        })
        send_whatsapp_list(
            to_phone_number=phone_number,
            header_text=f"Opsiyon Seçimi - {product_name}",
            body_text=f"Lütfen {product_name} için bir opsiyon seçin ya da opsiyonu atlamak için seçeneği kullanın.",
            button_text="Opsiyonlar",
            sections=sections
        )
    else:
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

                # Eğer state yoksa önce aktif (hazırlanıyor / yolda) sipariş kontrolü yapıyoruz
                if not state:
                    if customer_data:
                        list_active_orders(from_phone_number, customer_data["id"])
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
                            new_customer_id = create_customer(full_name, from_phone_number, reference=None)
                            order_id = create_new_order(new_customer_id)
                            set_user_state(from_phone_number, order_id, "ASK_REFERENCE")
                            ask_reference(from_phone_number)
                        elif current_step == "ASK_REFERENCE":
                            ref = text_body.strip()
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                if ref.lower() != "yok":
                                    update_customer_reference(c_data["id"], ref)
                                set_user_state(from_phone_number, state["order_id"], "ASK_ADDRESS")
                                ask_address(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_ADDRESS":
                            addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                add_address_to_customer(c_data["id"], addr)
                                update_order_address(state["order_id"], addr)
                                set_user_state(from_phone_number, state["order_id"], "ASK_MENU_OR_PRODUCT")
                                send_whatsapp_text(from_phone_number, "Bilgileriniz kaydedildi. Lütfen seçim yapın.")
                                ask_menu_or_product(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_NEW_ADDRESS":
                            new_addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                add_address_to_customer(c_data["id"], new_addr)
                                updated_customer = find_customer_by_phone(from_phone_number)
                                ask_update_or_continue(from_phone_number, updated_customer)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")
                        elif current_step == "ASK_COUPON":
                            coupon_code = text_body.strip()
                            order_id = state["order_id"]
                            if coupon_code.lower() == "yok":
                                conn = get_db_connection()
                                cur = conn.cursor(cursor_factory=RealDictCursor)
                                cur.execute("SELECT total_price FROM orders WHERE id = %s", (order_id,))
                                order = cur.fetchone()
                                cur.close()
                                conn.close()
                                original_total = order["total_price"] if order else 0
                                coupon_data = {"coupon_code": None, "original_total": int(original_total),
                                               "discount_amount": 0, "new_total": int(original_total)}
                                set_user_state(from_phone_number, order_id, "CONFIRM_ORDER",
                                               menu_products_queue=json.dumps(coupon_data, default=convert_decimal))
                                send_order_summary(from_phone_number, mode="confirm")
                            else:
                                original_total, discount_amount, new_total, coupon_obj = calculate_coupon_discount(
                                    order_id, coupon_code)
                                if original_total is None:
                                    send_whatsapp_text(from_phone_number, discount_amount)  # Hata mesajı
                                else:
                                    coupon_data = {"coupon_code": coupon_code, "original_total": int(original_total),
                                                   "discount_amount": int(discount_amount), "new_total": int(new_total)}
                                    set_user_state(from_phone_number, order_id, "CONFIRM_ORDER",
                                                   menu_products_queue=json.dumps(coupon_data, default=convert_decimal))
                                    send_order_summary(from_phone_number, mode="confirm")
                        else:
                            if text_body.lower() in ["menu", "menü", "başla", "1"]:
                                ask_menu_or_product(from_phone_number)
                            elif text_body.lower() in ["tamam", "bitir", "bitti", "2"]:
                                ask_coupon_code(from_phone_number)
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
