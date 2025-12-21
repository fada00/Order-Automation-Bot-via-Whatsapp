import json
import threading
import time
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, MetaData, Table, select, join, text
from sqlalchemy.orm import sessionmaker
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
import api
# Veri tabanı bağlantısı
engine = create_engine("postgresql://doadmin:AVNS_Z0QICT2kB9XMCABIcm2@db-postgresql-fra1-78106-do-user-18505233-0.i.db.ondigitalocean.com:25060/defaultdb?sslmode=require")  # PostgreSQL bilgilerinizi ekleyin
metadata = MetaData()

# Flask uygulaması
app = Flask(__name__)
socketio = SocketIO(app) 
Session = sessionmaker(bind=engine)

last_known_order_id = None

@app.route('/')
def index():
    return render_template("home.html",orders=fetch_orders())
def fetch_orders():
    # SQL sorgusunu text() ile sarıyoruz
    #WHERE 
    #o.created_at >= DATE_ADD(CURDATE(), INTERVAL 4 HOUR) 
    #AND o.created_at < DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 4 HOUR)
    
    sql_query = text("""
    SELECT 
    o.id AS order_id,
    c.full_name AS customer_name,
    c.phone_number AS customer_phone,
    o.address AS customer_address,
    o.created_at AS order_date,
    o.total_price AS order_total,
    o.status AS order_status,
    o.payment_method AS payment,
    p.name AS product_name,
    od.quantity AS product_quantity,
    STRING_AGG(po.name, ', ') AS option_names,
    od.id AS detail_id
FROM 
    orders o
JOIN 
    customers c ON o.customer_id = c.id
JOIN 
    order_details od ON o.id = od.order_id
JOIN 
    products p ON od.product_id = p.id
LEFT JOIN 
    order_options oo ON od.id = oo.order_detail_id
LEFT JOIN 
    product_options po ON oo.option_id = po.id
GROUP BY 
    o.id, c.id, p.id, od.id
ORDER BY 
    o.created_at DESC;
    """)

    # SQL sorgusunu çalıştır ve sonuçları al
    session = Session()
    results = session.execute(sql_query).fetchall()  # Sonuçları bir liste olarak alıyoruz
    session.close()

    # Veriyi formatlama
    orders = {}
    for row in results:
        order_id = row[0]  # order_id
        customer_name = row[1]  # customer_name
        customer_phone = row[2]  # customer_phone
        customer_address = row[3]  # customer_address
        order_date = row[4]  # order_date
        order_total = row[5]  # order_total
        order_status = row[6]  # order_status
        payment = row[7]  # payment method
        product_name = row[8]  # product_name
        product_quantity = row[9]  # product_quantity
        option_names = row[10]  # option_names (virgülle ayrılmış liste)
        detail_id = row[11]  # detail_id

        if isinstance(order_total, Decimal):
            order_total = float(order_total)
        if isinstance(order_date, datetime):
            order_date = order_date.strftime('%Y-%m-%d %H:%M:%S')


        # Ürün bilgisini oluştur
        option_info = f" [{option_names}]" if option_names else ""
        full_item = f"{product_name}{option_info}"


        # Sipariş ID'sine göre siparişleri gruplayalım
        if order_id not in orders:
            orders[order_id] = {
            "id": order_id,
            "customer_name": customer_name,
            "phone": customer_phone,
            "address": customer_address,
            "date": order_date,
            "total": order_total,
            "status": order_status,
            "payment": payment,
            "items_dict": {},
            "itemss": []
        }

        if full_item in orders[order_id]["items_dict"]:
            orders[order_id]["items_dict"][full_item] += product_quantity
        else:
            orders[order_id]["items_dict"][full_item] = product_quantity

    for order in orders.values():
        order["itemss"] = [f"{item} x {qty}" for item, qty in order.pop("items_dict").items()]

        # Ürünleri siparişin içine ekliyoruz
        orders[order_id]["itemss"].append(full_item)
    # Template'e gönder
    return orders

def start_check_for_new_orders():
    """Fonksiyonu background thread olarak başlatır"""
    threading.Thread(target=check_for_new_orders, daemon=True).start()


def check_for_new_orders():
    """Yeni siparişleri periyodik olarak kontrol eder ve istemcilere iletir"""
    global last_known_order_id

    while True:
        orders = fetch_orders()
        if not orders:
            time.sleep(5)
            continue

        current_max_order_id = max(orders.keys())  # En son sipariş ID'sini al
        print("Son sipariş ID'si:", current_max_order_id, "Önceki sipariş ID'si:", last_known_order_id)

        if last_known_order_id is None:
            last_known_order_id = current_max_order_id

        elif current_max_order_id > last_known_order_id:
            print("Yeni sipariş geldi!")
            last_known_order_id = current_max_order_id  # Güncelleme
             # `datetime` objelerini string formatına çevir
            for order_id, order in orders.items():

                print("Yeni sipariş ID:", last_known_order_id)

            socketio.emit("new_order", {"orders": orders})  # Yeni sipariş olduğunda istemciye gönder
            socketio.emit("update_orders", {"orders": orders})  # Siparişleri güncelle
        else:
            print("Yeni sipariş yok!")  # Eğer yeni sipariş yoksa loglama yap

        time.sleep(10)  # 10 saniyede bir kontrol et

@app.route('/get-orders', methods=['GET'])
def get_orders():
    """İstemciden gelen istek üzerine siparişleri döndürür"""
    orders = fetch_orders()
    return jsonify(orders)

@app.route('/update-order-status', methods=['POST'])
def update_order_status():
    data = request.get_json()
    order_id = data.get('order_id')
    new_status = data.get('status')

    if not order_id or not new_status:
        return jsonify({"success": False, "message": "Eksik veri gönderildi."}), 400

    try:
        # SQLAlchemy oturumunu başlat
        session = Session()

        # SQL sorgusunu tanımla ve çalıştır
        query = text("""
            UPDATE orders
            SET status = :status
            WHERE id = :order_id
        """)
        session.execute(query, {"status": new_status, "order_id": order_id})
        session.commit()  # Değişiklikleri kaydet

        # Oturumu kapat
        session.close()

        return jsonify({"success": True, "message": "Sipariş durumu güncellendi."})
    except Exception as e:
        session.rollback()
        print("Hata:", e)
        return jsonify({"success": False, "message": "Veritabanı hatası."}), 500
    finally:
        session.close()
    
@app.route('/menus', methods=['GET'])
def menus_page():
    return render_template('menu.html')

@app.route('/menus/get-initial-data', methods=['GET'])
def get_initial_data():
    try:
        session = Session()
        categories = session.execute(text("SELECT DISTINCT category FROM products")).fetchall()
        options = session.execute(text("SELECT id, name, price FROM product_options")).fetchall()

        return jsonify({
            "categories": [c[0] for c in categories],
            "options": [{"id":o[0], "name": o[1], "price": o[2]} for o in options]
        })
    except Exception as e:
        session.rollback()
        print("Hata:", e)
        return jsonify({"success": False, "message": "Başlangıç verileri alınamadı."}), 500
    finally:
        session.close()

@app.route('/menus/save-product', methods=['POST'])
def save_product():
    try:
        data = request.get_json()
        product_data = data.get('product')
        options_data = data.get('options')


        session = Session()

        # Ürün ekleme
        product_query = text("""
            INSERT INTO products (name, price, category)
            VALUES (:name, :price, :category) RETURNING id
        """)

        result = session.execute(product_query, product_data)
        product_id = result.fetchone()[0]

        option_ids = []

        # Opsiyonları ekleme
        for option in options_data:
            if option.get("existing"):
                option_id= int(option['id'])
                option_ids.append(option_id)

            else:
                new_option_query = text("""
                    INSERT INTO product_options (name, price)
                    VALUES (:name, :price) RETURNING id
                """)
                new_option_result = session.execute(new_option_query,{"name": option['name'], "price": option['price']})
                new_option_id = new_option_result.fetchone()[0]
                option_ids.append(new_option_id)
                    
        if option_ids!=[]:          
            update_product_query = text("""
            UPDATE products
            SET option_ids = ARRAY[:option_ids]::integer[]
            WHERE id = :product_id
            """)
        else:
            update_product_query = text("""
            UPDATE products
            SET option_ids = NULL
            WHERE id = :product_id
            """)
        session.execute(update_product_query, {"option_ids": option_ids, "product_id": product_id})

        session.execute(update_product_query, {"option_ids": option_ids, "product_id": product_id})

        session.commit()

        return jsonify({"success": True, "message": "Ürün başarıyla kaydedildi."})
    except Exception as e:
        session.rollback()
        print("Hata:", e)
        return jsonify({"success": False, "message": "Ürün kaydedilemedi."}), 500
    
    finally: 
        session.close()
### menü tabı için

@app.route('/menus/get-products', methods=['GET'])
def get_products():
    try:
        session = Session()
        products = session.execute(text("SELECT id, name, price,category FROM products")).fetchall()
        menu_categories = session.execute(text("SELECT DISTINCT category FROM menus")).fetchall() 
        session.close() 
        grouped_products = {}
        for p in products:
            if p.category not in grouped_products:
                grouped_products[p.category] = []
            grouped_products[p.category].append({"id": p.id, "name": p.name, "price": p.price})
        return jsonify({"products": grouped_products,
                        "menu_categories": [c[0] for c in menu_categories]})
    
    except Exception as e:
        print("Hata:", e)
        return jsonify({"success": False, "message": "Ürünler yüklenemedi."}), 500


@app.route('/save-menu', methods=['POST'])
def save_menu():
    import ast

    data = request.get_json()
    products = data.get('products')
    category = data.get('menu_categories') 
    menu_name = data.get('name')
    menu_description = data.get('description')
    menu_price = data.get('price')
    


    products_jsonb = [json.dumps(product) for product in products]
    try:
        session = Session()
        menu_query = text("""
            INSERT INTO menus (name, description, price, category, products)
            VALUES (:name, :description, :price, :category, ARRAY[:products]::jsonb[]) RETURNING id
        """)
        result = session.execute(menu_query, {**data, "products": products_jsonb})
        menu_id = result.fetchone()[0]

        session.commit()
        return jsonify({"success": True, "message": "Menü başarıyla kaydedildi."})
   
    except Exception as e:
        session.rollback()
        print("Hata:", e)
        return jsonify({"success": False, "message": "Menü kaydedilemedi."}), 500
    
    finally:
        session.close()

#ürün güncelleme tabı için 

@app.route('/get-items/<item_type>', methods=['GET'])
def get_items(item_type):
    session = Session()
    if item_type == "products":
        items = session.execute(text("SELECT id, name, price FROM products")).fetchall()
    elif item_type == "menus":
        items = session.execute(text("SELECT id, name, price FROM menus")).fetchall()
    else:
        return jsonify({"success": False, "message": "Geçersiz tür"}), 400

    session.close()
    return jsonify({"items": [{"id": item.id, "name": item.name, "price": item.price} for item in items]})

@app.route('/update-item/<item_type>', methods=['POST'])
def update_item(item_type):
    data = request.json
    session = Session()
    try:
        if item_type == "products":
            session.execute(text("UPDATE products SET name = :name, price = :price WHERE id = :id"), 
                        {"name": data['name'], "price": data['price'], "id": data['id']})
        elif item_type == "menus":
            session.execute(text("UPDATE menus SET name = :name, price = :price WHERE id = :id"), 
                        {"name": data['name'], "price": data['price'], "id": data['id']})
        else:
            return jsonify({"success": False, "message": "Geçersiz tür"}), 400
        
        session.commit()
        return jsonify({"success": True})
    
    except Exception as e:
         session.rollback()
         print("Hata:", e)
         return jsonify({"success": False, "message": "Ürün güncellenemedi."}), 500
    
    finally:
        session.close()

@app.route('/delete-item/<item_type>/<int:item_id>', methods=['DELETE'])
def delete_item(item_type, item_id):
    session = Session()
    if item_type == "products":
        session.execute(text("DELETE FROM products WHERE id = :id"), {"id": item_id})
    elif item_type == "menus":
        session.execute(text("DELETE FROM menus WHERE id = :id"), {"id": item_id})
    else:
        return jsonify({"success": False, "message": "Geçersiz tür"}), 400

    session.commit()
    session.close()
    return jsonify({"success": True})

@app.route('/update-product', methods=['POST'])
def update_product():
    data = request.json
    session = Session()
    try:
        # Ürünü güncelle
        session.execute(
            text("UPDATE products SET name = :name, price = :price WHERE id = :id"),
            {"name": data['name'], "price": data['price'], "id": data['id']}
        )
        session.commit()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        print("Hata:", e)
        return jsonify({"success": False, "message": "Ürün güncellenemedi."}), 500
    finally:
        session.close()

# kupon tabı 

# Kuponları listeleme
@app.route("/get_coupons", methods=["GET"])
def get_coupons():
    try:
        session = Session()
        coupons = session.execute(text("SELECT  * FROM coupons")).fetchall()
        session.close()
        
        return jsonify({"coupons": [{"code": c.code,"min_price":c.min_price, "discount": c.discount, "max_usage_limit": c.max_usage_limit,
                                      "current_usage": c.current_usage} for c in coupons]})
    except Exception as e:
        print("Hata:", e)
        return jsonify({"success": False, "message": "Başlangıç verileri alınamadı."}), 500

# Kupon ekleme
@app.route("/add_coupon", methods=["POST"])
def add_coupon():
    data = data.get("coupons")
    code = data["code"]

    # Eksik veri kontrolü
    if not data.get("code") or data.get("discount") is None or data.get("max_usage_limit") is None:
        return jsonify({"message": "Eksik veri gönderildi!"}), 400

    # Aynı kodda kupon olup olmadığını kontrol et
    
    if code["existing"]:
        return jsonify({"message": "Bu kupon kodu zaten mevcut!"}), 400

    save_coupon = text("""
        INSERT INTO coupons (code, discount, min_price, max_usage_limit, current_usage)
        VALUES (:code, :discount, :min_price :max_usage_limit, :current_usage)
    """)
    Session.execute(save_coupon, {"code": data["code"], "discount": data["discount"],"min_price":["min_price"],
                                  "max_usage_limit": data["max_usage_limit"], "current_usage": data["current_usage"]})

# Kupon silme
@app.route("/delete_coupon/<string:code>", methods=["DELETE"])
def delete_coupon(code):
    coupon = request.json["coupons"]
    if coupon:
       delete_coupon = text("DELETE FROM coupons WHERE code = :code")

    return jsonify({"message": "Kupon başarıyla silindi!"})

@app.route('/webhook', methods=['GET','POST'])
def webhook_app():
    return api.webhook(request.method)

if __name__ == '__main__':
    start_check_for_new_orders()
    socketio.run(app, debug=True,port=8000)
    
