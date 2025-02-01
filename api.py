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
ACCESS_TOKEN = "EAAYjJkjWxhcBOZBOiQipzCPcmc6GpkkSLy16eFJFBjlXsEfB735zwYVE8SkqkK32jh1EZBRgP9iPvXygcVGnh69hN9I4ksQ5wJCJ58q0Nv3VskLPS8B4lHYkFGViimkfK4rS2OglSZC3izpeK5xa7GRTZCOjVeTEyCeZBqH9ORFDjmwjl9kBzcir6sZAuVEG69ToDAXgW818AYMJ63UBzhU5GLGrKbBjKgKLZBhZBiWRYccZD"
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
# 2) Veritabanı İşlemleri (Müşteri, Sipariş, Ürün, Opsiyon vb.)
# (create_customer, update_customer_info, create_or_get_active_order, finalize_order_in_db,
#  add_product_to_order, add_option_to_order_detail, get_product_options, get_all_menus, get_all_products, vb.)
# --------------------------------------------------------------------
# Örneğin:
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
    cur.execute("SELECT id, name, price FROM product_options WHERE product_id = %s", (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# Menü seçilirse, en sonda siparişin fiyatı menü fiyatıyla override edilsin:
def override_order_price_to_menu(order_id, menu_price):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET total_price = %s WHERE id = %s", (menu_price, order_id))
    conn.commit()
    cur.close()
    conn.close()

# Eğer sipariş 'draft' durumundaysa modifiye edilebilsin, aksi halde düzenleme yapılamasın:
def is_order_modifiable(order_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    # Sadece 'draft' durumundaki sipariş düzenlenebilir.
    if row:
        return row[0] == 'draft'
    return False

# Diğer veritabanı fonksiyonlarınız (create_customer, update_customer_info, create_or_get_active_order, finalize_order_in_db, get_all_menus, get_all_products, vb.) mevcut kabul ediliyor.

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
# 4) Müşteri Bilgisi & Adres Akışı
# (ask_update_or_continue, ask_name, ask_reference, ask_address, ask_address_confirmation, ask_new_address)
# --------------------------------------------------------------------
def ask_update_or_continue(phone_number, customer):
    full_name = customer["full_name"]
    ref = customer.get("reference", "") or ""
    msg = f"Kayıtlı bilgileriniz:\nİsim: {full_name}\nReferans: {ref}\n\nGüncellemek ister misiniz?"
    send_whatsapp_buttons(
        phone_number,
        msg,
        [
            {"type": "reply", "reply": {"id": "UPDATE_INFO_YES", "title": "Evet"}},
            {"type": "reply", "reply": {"id": "UPDATE_INFO_NO", "title": "Hayır"}}
        ]
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "UPDATE_OR_CONTINUE")

def ask_name(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adınızı-soyadınızı giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NAME")

def ask_reference(phone_number):
    send_whatsapp_text(phone_number, "Varsa bir referans kodu girin. Yoksa 'yok' yazabilirsiniz.")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_REFERENCE")

def ask_address(phone_number):
    send_whatsapp_text(phone_number, "Lütfen adresinizi yazın:")
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
    menus = get_all_menus()  # Mevcut menüler
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
        row_id = f"category_{cat_val}"
        sections[0]["rows"].append({"id": row_id, "title": cat_val, "description": f"{cat_val} kategorisindeki ürünler."})
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
        title = p['name']
        desc = f"Fiyat: {p['price']}₺"
        sections[0]["rows"].append({"id": row_id, "title": title, "description": desc})
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
        row_title = opt["name"]
        row_desc = f"+{opt['price']}₺"
        sections[0]["rows"].append({"id": row_id, "title": row_title, "description": row_desc})
    send_whatsapp_list(
        to_phone_number=phone_number,
        header_text="Opsiyon Seçimi",
        body_text="Lütfen bu ürün için bir opsiyon seçin.",
        button_text="Opsiyonlar",
        sections=sections
    )
    # State 'CONFIGURING_PRODUCT' bekleniyor (opsiyon seçimi için)

# --------------------------------------------------------------------
# 6) Sipariş Finalizasyonu
# --------------------------------------------------------------------
def finalize_order(phone_number):
    st = get_user_state(phone_number)
    if not st:
        return
    customer = find_customer_by_phone(phone_number)  # Mevcut müşteri sorgusu
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
    finalize_order_in_db(order_id)  # Sipariş onaylama işlemi
    send_whatsapp_text(phone_number, "Siparişiniz onaylandı! Teşekkürler.\nYeni sipariş için istediğiniz zaman yazabilirsiniz.")
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
    elif selected_id == "choose_products":
        send_categories(phone_number)
    elif selected_id == "UPDATE_INFO_YES":
        set_user_state(phone_number, order_id, "UPDATING_NAME")
        send_whatsapp_text(phone_number, "Lütfen yeni isminizi-soyisminizi yazın:")
    elif selected_id == "UPDATE_INFO_NO":
        set_user_state(phone_number, order_id, "ASK_MENU_OR_PRODUCT")
        send_whatsapp_text(phone_number, "Bilgiler güncellenmeden devam ediliyor.")
        ask_menu_or_product(phone_number)
    elif selected_id == "ADDRESS_SAME":
        finalize_order_internally(phone_number)
    elif selected_id == "ADDRESS_NEW":
        ask_new_address(phone_number)
    elif selected_id == "more_options_yes":
        # Eğer kullanıcı mevcut ürün için ek opsiyon eklemek istiyorsa:
        if st["step"] == "ASK_MORE_OPTIONS_FOR_PRODUCT":
            detail_id = st.get("last_detail_id")
            if not is_order_modifiable(order_id):
                send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                return
            # Ürünün opsiyon listesini tekrar gönderiyoruz.
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
        # Opsiyon eklemesi tamamlandıktan sonra, kullanıcıya başka ürün ekleyip eklemeyeceği sorulur.
        send_whatsapp_buttons(
            phone_number,
            "Opsiyon eklendi. Başka ürün eklemek ister misiniz?",
            [
                {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
            ]
        )
        set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
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
            for item in menu_products:
                prod_id = int(item.get("id"))
                amount = int(item.get("amount", 1))
                if not is_order_modifiable(order_id):
                    send_whatsapp_text(phone_number, "Mevcut sipariş düzenlenemez.")
                    return
                last_detail_id = add_product_to_order(order_id, prod_id, amount)
                # Her bir ürün için opsiyon akışı
                product_options = get_product_options(prod_id)
                if product_options:
                    send_options_list(phone_number, last_detail_id, product_options)
                    set_user_state(phone_number, order_id, "ASK_MORE_OPTIONS_FOR_PRODUCT", last_detail_id=last_detail_id)
                # Eğer opsiyon yoksa, otomatik geçebiliriz.
            # Menü seçilirse, en sonda siparişin toplam fiyatı menü fiyatı olarak ayarlanır.
            override_order_price_to_menu(order_id, menu.get("price", 0))
            send_whatsapp_buttons(
                phone_number,
                "Menü eklendi. Başka ürün eklemek ister misiniz?",
                [
                    {"type": "reply", "reply": {"id": "ask_another_yes", "title": "Evet"}},
                    {"type": "reply", "reply": {"id": "ask_another_no", "title": "Hayır"}}
                ]
            )
            set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")
        else:
            send_whatsapp_text(phone_number, "Menü bulunamadı.")
    elif selected_id.startswith("option_"):
        # Seçim formatı: "option_{order_detail_id}_{option_id}"
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
    else:
        send_whatsapp_text(phone_number,
                           "Siparişiniz onaylandı! Teşekkürler.\nYeni sipariş için istediğiniz zaman yazabilirsiniz.")
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
        try:
            entry = incoming_data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' in value:
                message = value['messages'][0]
                from_phone_number = message['from']

                customer_data = find_customer_by_phone(from_phone_number)  # Mevcut müşteri sorgusu
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
                                    {"type": "reply", "reply": {"id": "UPDATE_INFO_NO", "title": "Hayır, devam et"}}
                                ]
                            )
                        else:
                            order_id = create_or_get_active_order(customer_data["id"])  # Yeni sipariş 'draft' olarak oluşturulmalı.
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
                                set_user_state(from_phone_number, state["order_id"], "ASK_MENU_OR_PRODUCT")
                                send_whatsapp_text(from_phone_number, "Bilgileriniz kaydedildi. Lütfen seçim yapın.")
                                ask_menu_or_product(from_phone_number)
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
                                set_user_state(from_phone_number, state["order_id"], "ASK_MENU_OR_PRODUCT")
                                send_whatsapp_text(from_phone_number, "Bilgiler güncellendi. Lütfen seçim yapın.")
                                ask_menu_or_product(from_phone_number)
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
