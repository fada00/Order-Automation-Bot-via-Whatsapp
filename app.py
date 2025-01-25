import json
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from flask import Flask, render_template, jsonify, request
from sqlalchemy import create_engine, MetaData, Table, select, join,text
from sqlalchemy.orm import sessionmaker

# Veri tabanı bağlantısı
engine = create_engine("postgresql://doadmin:AVNS_5cVVGMm4MB4bAZjijsd@db-postgresql-fra1-87481-do-user-18505233-0.h.db.ondigitalocean.com:25060/defaultdb?sslmode=require")  # PostgreSQL bilgilerinizi ekleyin
metadata = MetaData()

# Flask uygulaması
app = Flask(__name__)
Session = sessionmaker(bind=engine)

@app.route("/test")
def test():
    return jsonify({"status": "working"})

@app.route("/static-test")
def static_test():
    return url_for("static", filename="home.js")

@app.route('/')
def index():
    # SQL sorgusunu text() ile sarıyoruz
    #WHERE 
    #o.created_at >= DATE_ADD(CURDATE(), INTERVAL 4 HOUR) 
    #AND o.created_at < DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 4 HOUR)
    
    sql_query = text("""
    SELECT 
        o.id AS order_id,
        c.full_name AS customer_name,
        c.phone_number AS customer_phone,
        c.address AS customer_address,
        o.created_at AS order_date,
        o.total_price AS order_total,
        o.status AS order_status,
        p.name AS product_name,
        od.quantity AS product_quantity,
        po.name AS option_name,
        COUNT(po.id) AS option_quantity
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
        o.id, c.id, p.id, od.id, po.id
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
        order_id = row[0]  # order_id: Tuple'dan sırasıyla erişiyoruz
        customer_name = row[1]  # customer_name
        customer_phone = row[2]  # customer_phone
        customer_address = row[3]  # customer_address
        order_date = row[4]  # order_date
        order_total = row[5]  # order_total
        order_status = row[6]  # order_status
        product_name = row[7]  # product_name
        product_quantity = row[8]  # product_quantity
        option_name = row[9]  # option_name
        option_quantity = row[10]  # option_quantity

        # Ürün ve opsiyon bilgilerini birleştiriyoruz
        product_info = f"{product_name} x {product_quantity}"
        option_info = f"[{option_name} x {option_quantity}]" if option_name else ""
        full_item = f"{product_info} {option_info}"

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
                "itemss": []
            }
        

        # Ürünleri siparişin içine ekliyoruz
        orders[order_id]["itemss"].append(full_item)

    print(orders)
    # Template'e gönder
    return render_template("home.html", orders=orders)

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
        print("Hata:", e)
        return jsonify({"success": False, "message": "Veritabanı hatası."}), 500
    
@app.route('/menus', methods=['GET'])
def menus_page():
    return render_template('menu.html')

@app.route('/menus/get-initial-data', methods=['GET'])
def get_initial_data():
    try:
        session = Session()
        categories = session.execute(text("SELECT DISTINCT category FROM products")).fetchall()
        options = session.execute(text("SELECT id, name, price FROM product_options")).fetchall()
        session.close()

        return jsonify({
            "categories": [c[0] for c in categories],
            "options": [{"id":o[0], "name": o[1], "price": o[2]} for o in options]
        })
    except Exception as e:
        print("Hata:", e)
        return jsonify({"success": False, "message": "Başlangıç verileri alınamadı."}), 500


@app.route('/menus/save-product', methods=['POST'])
def save_product():
    try:
        data = request.get_json()
        product_data = data.get('product')
        options_data = data.get('options')

        print("Ürün verisi:", data)

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
                    
        update_product_query = text("""
            UPDATE products
            SET option_ids = ARRAY[:option_ids]::integer[]
            WHERE id = :product_id
            """)
        session.execute(update_product_query, {"option_ids": option_ids, "product_id": product_id})

        session.commit()
        session.close()

        return jsonify({"success": True, "message": "Ürün başarıyla kaydedildi."})
    except Exception as e:
        print("Hata:", e)
        return jsonify({"success": False, "message": "Ürün kaydedilemedi."}), 500
    
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
        session.close()
        return jsonify({"success": True, "message": "Menü başarıyla kaydedildi."})
    except Exception as e:
        print("Hata:", e)
        return jsonify({"success": False, "message": "Menü kaydedilemedi."}), 500
    

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

if __name__ == '__main__':
    app.run(debug=True,port=8000)
    