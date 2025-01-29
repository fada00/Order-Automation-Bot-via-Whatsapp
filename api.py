import json
import requests
from flask import request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

# --------------------------------------------------------------------
# WhatsApp Cloud API Ayarları
# --------------------------------------------------------------------
WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"
VERIFY_TOKEN = "maydonozwp"
ACCESS_TOKEN = "EAAYjJkjWxhcBOwyFGeCimMMWxBEAAZB6ymukoIMvRvGWkskDRIhTARyK5Muqd4pGTqBPqIYbNyelK3eU4RFMMBneDwgeWlZCiNRpdDjqqk1PK9zexQpsKbW4VRKaBZB4AJpT4juGTZBSFHBbf8kaKPonBDP5WhFQjQbNQkYZCgZAQDB8LZCqBat59ytijDQyDQl2jlV4JzBdhHgM7YBdzfZBRWiXLVGUiafmL7hCq3x33KUZD"  # kısaltılmıştır
PHONE_NUMBER_ID = "459475243924742"

# --------------------------------------------------------------------
# PostgreSQL Bağlantı Bilgileri
# --------------------------------------------------------------------
DB_HOST = "db-postgresql-fra1-87481-do-user-18505233-0.h.db.ondigitalocean.com"
DB_NAME = "dbpool"
DB_USER = "doadmin"
DB_PASS = "AVNS_5cVVGMm4MB4bAZjijsd"
DB_PORT = 25060


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
    sections formatı:
    [
      {
        "title": "Başlık",
        "rows": [
          {"id": "...", "title": "...", "description": "..."},
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
        return  # hiçbir şey güncellenmeyecek

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
    Müşterinin 'pending' veya 'draft' durumundaki son siparişini getirir.
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
    """Siparişi 'hazırlanıyor' durumuna çeker (örnek)."""
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
    Siparişe ürün ekler -> order_details kaydı ve total_price güncelle.
    Dönen değer: order_detail.id
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Ürün fiyatı
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

    # order toplam fiyat güncelle
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
    order_options tablosuna ekle, siparişi güncelle (fiyat artışı).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Opsiyon fiyatı
    cur.execute("SELECT price FROM product_options WHERE id = %s", (option_id,))
    opt_row = cur.fetchone()
    if not opt_row:
        cur.close()
        conn.close()
        raise ValueError("Opsiyon bulunamadı!")
    option_price = float(opt_row[0])

    # order_options kaydı ekle
    cur.execute("""
        INSERT INTO order_options (order_detail_id, option_id)
        VALUES (%s, %s)
        RETURNING id
    """, (order_detail_id, option_id))
    _new_option_id = cur.fetchone()[0]

    # order_id bul -> orders.total_price += option_price
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


def get_all_menus():
    """Tüm menüler (menus tablosu)."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM menus ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_products():
    """
    Tüm ürünler (products tablosu). Kategori bazlı da listeleyebilirsiniz.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, category, price FROM products ORDER BY category, id")
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


def set_user_state(phone_number, order_id, step,
                   last_detail_id=None, menu_products_queue=None):
    """
    user_states tablosunu günceller veya ekler.
    menu_products_queue: JSON listesi veya None.
    step: string (ör: "SELECTING_PRODUCT", "CONFIGURING_PRODUCT", "ASK_MORE_OPTIONS", "ASK_ADDRESS", ...)
    """
    import json
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
    Müşteri kayıtlı ise: “Kayıtlı isminiz: X. Referans: Y. Güncellemek ister misiniz?”
    """
    full_name = customer["full_name"]
    ref = customer.get("reference", "")
    if ref is None:
        ref = ""

    msg = f"Kayıtlı bilgileriniz:\nİsim: {full_name}\nReferans: {ref}\n\n" \
          "Güncellemek istiyor musunuz?"
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
    # step -> UPDATE_OR_CONTINUE
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "UPDATE_OR_CONTINUE")


def ask_name(phone_number):
    """
    İsim-soyisim sormak için text mesaj bekliyoruz.
    """
    send_whatsapp_text(phone_number, "Lütfen adınızı-soyadınızı giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NAME")


def ask_reference(phone_number):
    """
    Kullanıcıdan varsa referans kodu alalım
    """
    send_whatsapp_text(phone_number, "Varsa bir referans kodu girin. Yoksa 'yok' yazabilirsiniz.")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_REFERENCE")


def ask_address(phone_number):
    """
    Kullanıcıdan adres alalım
    """
    send_whatsapp_text(phone_number, "Lütfen adresinizi yazın:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_ADDRESS")


def ask_address_confirmation(phone_number, current_address):
    """
    Siparişi onaylamadan önce adresi sorar: kayıtlı mı kullanalım, yeni mi girecek?
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


# --------------------------------------------------------------------
# 5) Menü ve Ürün Seçim Fonksiyonları (Değişmeden Kaldı)
# --------------------------------------------------------------------

def handle_menu_queue_next_product(phone_number):
    """
    Menüdeki ürünleri sırayla ekleyip opsiyonlarını sorar.
    """
    state = get_user_state(phone_number)
    if not state:
        return

    queue_data = state.get("menu_products_queue")
    if not queue_data or not queue_data.get("remaining"):
        # Kuyruk boş -> menüdeki tüm ürünler işlendi
        send_whatsapp_buttons(
            phone_number,
            "Menüdeki tüm ürünleri ekledik. Başka ürün veya menü eklemek ister misiniz?",
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
        set_user_state(phone_number, state["order_id"], "ASK_ANOTHER_PRODUCT")
    else:
        product_id = queue_data["remaining"][0]
        detail_id = add_product_to_order(state["order_id"], product_id, 1)
        queue_data["remaining"].pop(0)

        set_user_state(phone_number, state["order_id"], "CONFIGURING_PRODUCT",
                       last_detail_id=detail_id, menu_products_queue=queue_data)
        product_options = get_product_options(product_id)
        if product_options:
            send_options_list(phone_number, detail_id, product_options)
        else:
            handle_menu_queue_next_product(phone_number)


def send_options_list(phone_number, order_detail_id, product_options):
    """
    Bir ürün (order_detail) için opsiyonları list şeklinde gönderir.
    """
    sections = [
        {
            "title": "Opsiyonlar",
            "rows": []
        }
    ]
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
        body_text="Bu ürün için bir opsiyon ekleyebilirsiniz (çoklu seçim).",
        button_text="Opsiyonlar",
        sections=sections
    )
    # step -> CONFIGURING_PRODUCT


def ask_more_options(phone_number):
    """
    Kullanıcıya "Daha opsiyon eklemek ister misiniz?" diye buton sorar.
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
    state = get_user_state(phone_number)
    set_user_state(phone_number, state["order_id"], "ASK_MORE_OPTIONS",
                   last_detail_id=state.get("last_detail_id"),
                   menu_products_queue=state.get("menu_products_queue"))


def send_menu_and_products(phone_number):
    """
    Menüler ve ürünler tek bir list içerisinde gönderilir.
    """
    all_menus = get_all_menus()
    all_products = get_all_products()

    sections = []
    # Menüler
    if all_menus:
        menu_rows = []
        for m in all_menus:
            row_id = f"menu_{m['id']}"
            title = m['name']
            desc = f"{m['description']} (Fiyat: {m['price']})"
            menu_rows.append({
                "id": row_id,
                "title": title,
                "description": desc
            })
        if menu_rows:
            sections.append({"title": "Menüler", "rows": menu_rows})

    # Ürünleri kategorilere göre gruplayalım
    cat_dict = {}
    for p in all_products:
        cat = p["category"]
        if cat not in cat_dict:
            cat_dict[cat] = []
        cat_dict[cat].append(p)

    for cat_name, plist in cat_dict.items():
        rows = []
        for prd in plist:
            row_id = f"product_{prd['id']}"
            row_title = prd["name"]
            row_desc = f"Fiyat: {prd['price']}₺"
            rows.append({"id": row_id, "title": row_title, "description": row_desc})
        sections.append({"title": cat_name, "rows": rows})

    send_whatsapp_list(
        phone_number,
        "Menü ve Ürünler",
        "Lütfen menü veya ürün seçin.",
        "Seç",
        sections
    )
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "SELECTING_PRODUCT")


# --------------------------------------------------------------------
# 6) Finalize (Siparişi Onaylama) Süreci
# --------------------------------------------------------------------
def finalize_order(phone_number):
    """
    Siparişi tamamlamadan önce adres onayı isteyelim.
    """
    st = get_user_state(phone_number)
    if not st:
        return

    # Müşterinin mevcut adresi
    customer = find_customer_by_phone(phone_number)
    if not customer:
        # Olağan dışı durum, normalde bir kaydı olması lazım
        send_whatsapp_text(phone_number, "Müşteri kaydı bulunamadı, lütfen tekrar başlayın.")
        clear_user_state(phone_number)
        return

    current_address = customer.get("address", "")
    if not current_address:
        # Adres yoksa direkt soralım
        ask_new_address(phone_number)
    else:
        # Adres var, onay soralım
        ask_address_confirmation(phone_number, current_address)


def finalize_order_internally(phone_number):
    """
    Adres onayı da yapıldıktan sonra siparişi finalize ediyoruz.
    """
    st = get_user_state(phone_number)
    if not st:
        return
    order_id = st["order_id"]

    # Siparişi DB'de finalize
    finalize_order_in_db(order_id)

    send_whatsapp_text(phone_number,
                       "Siparişinizi onayladık! Teşekkür ederiz.\n"
                       "Yeni bir sipariş için istediğiniz zaman yazabilirsiniz."
                       )
    clear_user_state(phone_number)


def ask_new_address(phone_number):
    """
    Kullanıcıdan yeni adres ister.
    """
    send_whatsapp_text(phone_number, "Lütfen yeni adresinizi giriniz:")
    st = get_user_state(phone_number)
    set_user_state(phone_number, st["order_id"], "ASK_NEW_ADDRESS")


# --------------------------------------------------------------------
# 7) Webhook ve Handle Fonksiyonları
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
        # print(json.dumps(incoming_data, indent=2))  # Debug

        try:
            entry = incoming_data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' in value:
                message = value['messages'][0]
                from_phone_number = message['from']

                # Müşteri var mı?
                customer_data = find_customer_by_phone(from_phone_number)
                state = get_user_state(from_phone_number)

                # Eğer state yoksa yeni başlıyoruz
                if not state:
                    if customer_data:
                        order_id = create_or_get_active_order(customer_data["id"])
                        set_user_state(from_phone_number, order_id, "UPDATE_OR_CONTINUE")
                        ask_update_or_continue(from_phone_number, customer_data)
                    else:
                        set_user_state(from_phone_number, None, "ASK_NAME")
                        ask_name(from_phone_number)
                else:
                    # Zaten bir state var, bakalım interaktif mi yoksa text mi geldi
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
                        # Text mesaj
                        text_body = message.get('text', {}).get('body', '').strip()
                        current_step = state["step"]
                        if current_step == "ASK_NAME":
                            # Bu metni isim olarak alalım
                            full_name = text_body
                            # DBde müşteri kaydı oluştur
                            new_customer_id = create_customer(full_name, from_phone_number, address="", reference=None)
                            # Sipariş başlatalım
                            order_id = create_or_get_active_order(new_customer_id)
                            set_user_state(from_phone_number, order_id, "ASK_REFERENCE")
                            ask_reference(from_phone_number)

                        elif current_step == "ASK_REFERENCE":
                            ref_text = text_body
                            if ref_text.lower() == "yok":
                                ref_text = ""
                            # customer_id bulalım
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], reference=ref_text)
                                set_user_state(from_phone_number, c_data["id"], "ASK_ADDRESS")
                                ask_address(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")

                        elif current_step == "ASK_ADDRESS":
                            addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=addr)
                                # Artık menüye geçebiliriz
                                # order_id zaten state içinde var
                                st = get_user_state(from_phone_number)
                                order_id = st["order_id"]  # create_or_get_active_order(c_data["id"]) vs.
                                set_user_state(from_phone_number, order_id, "SELECTING_PRODUCT")
                                send_whatsapp_text(from_phone_number,
                                                   "Teşekkürler! Bilgileriniz kaydedildi.\nŞimdi menüyü gösteriyorum...")
                                send_menu_and_products(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")

                        elif current_step == "UPDATING_NAME":
                            # Kullanıcı yeni ismini yazdı
                            new_name = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], full_name=new_name)
                                # Sonraki adım: referans
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
                                # Ardından menüye geçiyoruz
                                # sipariş de var
                                set_user_state(from_phone_number, state["order_id"], "SELECTING_PRODUCT")
                                send_whatsapp_text(from_phone_number, "Bilgileriniz güncellendi!\nMenüye geçelim.")
                                send_menu_and_products(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")

                        elif current_step == "ASK_NEW_ADDRESS":
                            # Yeni adresi aldık
                            new_addr = text_body
                            c_data = find_customer_by_phone(from_phone_number)
                            if c_data:
                                update_customer_info(c_data["id"], address=new_addr)
                                # Şimdi finalize
                                finalize_order_internally(from_phone_number)
                            else:
                                send_whatsapp_text(from_phone_number, "Müşteri kaydı hatası!")

                        else:
                            # Diğer text'ler
                            if text_body.lower() in ["menu", "menü", "başla", "1"]:
                                send_menu_and_products(from_phone_number)
                            elif text_body.lower() in ["tamam", "bitir", "bitti", "2"]:
                                finalize_order(from_phone_number)
                            else:
                                send_whatsapp_text(
                                    from_phone_number,
                                    "Menü veya ürün seçmek için 'menu' yazabilir ya da butonları kullanabilirsiniz.\n"
                                    "Siparişi tamamlamak için 'tamam' yazabilirsiniz."
                                )
        except Exception as e:
            print("Hata:", e)

        return jsonify({"status": "ok"}), 200


# --------------------------------------------------------------------
# 8) handle_button_reply ve handle_list_reply
# --------------------------------------------------------------------

def handle_button_reply(phone_number, selected_id):
    """
    button_reply ->
      * "UPDATE_INFO_YES", "UPDATE_INFO_NO" (müşteri bilgisi güncellemek?)
      * "ADDRESS_SAME", "ADDRESS_NEW" (adres onayı)
      * "more_options_yes", "more_options_no"
      * "ask_another_yes", "ask_another_no"
      vb.
    """
    st = get_user_state(phone_number)
    if not st:
        return

    # Mevcut sipariş id
    order_id = st["order_id"]

    if selected_id == "UPDATE_INFO_YES":
        # step -> UPDATING_NAME
        set_user_state(phone_number, order_id, "UPDATING_NAME")
        send_whatsapp_text(phone_number, "Lütfen yeni isminizi-soyisminizi yazın:")

    elif selected_id == "UPDATE_INFO_NO":
        # Müşteri bilgilerini değiştirmiyoruz => menü aşamasına geç
        set_user_state(phone_number, order_id, "SELECTING_PRODUCT")
        send_whatsapp_text(phone_number, "Bilgiler güncellenmeden devam ediliyor.\nMenüyü gösteriyorum...")
        send_menu_and_products(phone_number)

    elif selected_id == "ADDRESS_SAME":
        # Adres aynı kalsın -> finalize
        finalize_order_internally(phone_number)

    elif selected_id == "ADDRESS_NEW":
        # Yeni adres sor
        ask_new_address(phone_number)

    elif selected_id.startswith("more_options_"):
        # "more_options_yes" veya "more_options_no"
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
                    handle_menu_queue_next_product(phone_number)
            else:
                send_whatsapp_text(phone_number, "Ürün bulunamadı.")
        else:
            # "more_options_no"
            handle_menu_queue_next_product(phone_number)

    elif selected_id.startswith("ask_another_"):
        if selected_id == "ask_another_yes":
            send_menu_and_products(phone_number)
        else:
            # finalize
            finalize_order(phone_number)

    else:
        send_whatsapp_text(phone_number, "Bilinmeyen buton seçimi.")


def handle_list_reply(phone_number, selected_id):
    """
    list_reply -> "menu_{id}" veya "product_{id}" veya "option_{detailId}_{optionId}" vb.
    """
    st = get_user_state(phone_number)
    if not st or not st["order_id"]:
        return
    order_id = st["order_id"]

    if selected_id.startswith("menu_"):
        menu_id = int(selected_id.replace("menu_", ""))
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM menus WHERE id = %s", (menu_id,))
        menu_data = cur.fetchone()
        cur.close()
        conn.close()
        if menu_data and menu_data["products"]:
            products_in_menu = menu_data["products"]
            queue_info = {"remaining": products_in_menu}
            set_user_state(phone_number, order_id, "MENU_NEXT_PRODUCT",
                           menu_products_queue=queue_info)
            send_whatsapp_text(phone_number, f"'{menu_data['name']}' menüsü seçildi. Ürünler ekleniyor...")
            handle_menu_queue_next_product(phone_number)
        else:
            send_whatsapp_text(phone_number, "Menü boş veya bulunamadı.")
            send_menu_and_products(phone_number)

    elif selected_id.startswith("product_"):
        product_id = int(selected_id.replace("product_", ""))
        detail_id = add_product_to_order(order_id, product_id, 1)
        product_options = get_product_options(product_id)
        if product_options:
            set_user_state(phone_number, order_id, "CONFIGURING_PRODUCT", last_detail_id=detail_id)
            send_options_list(phone_number, detail_id, product_options)
        else:
            send_whatsapp_buttons(
                phone_number,
                "Bu ürünü ekledik. Başka ürün eklemek ister misiniz?",
                [
                    {
                        "type": "reply",
                        "reply": {"id": "ask_another_yes", "title": "Evet"}
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "ask_another_no", "title": "Hayır"}
                    }
                ]
            )
            set_user_state(phone_number, order_id, "ASK_ANOTHER_PRODUCT")

    elif selected_id.startswith("option_"):
        parts = selected_id.split("_")
        detail_id = int(parts[1])
        option_id = int(parts[2])
        add_option_to_order_detail(detail_id, option_id)
        ask_more_options(phone_number)
    else:
        send_whatsapp_text(phone_number, "Bilinmeyen seçim!")
        send_menu_and_products(phone_number)