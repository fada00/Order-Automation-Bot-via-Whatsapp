import requests

API_URL = "https://graph.facebook.com/v21.0/459475243924742/messages"

PHONE_NUMBER = "905539538384"

data = {
    "messaging_product": "whatsapp",
    "to": PHONE_NUMBER,
    "type": "interactive",
    "interactive": {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Menümüz"
        },
        "body": {
            "text": "Lütfen sipariş vermek istediğiniz ürünü seçin:"
        },
        "footer": {
            "text": "Herhangi bir sorunuz varsa bize yazabilirsiniz!"
        },
        "action": {
            "button": "Ürünler",
            "sections": [
                {
                    "title": "Ana Yemekler",
                    "rows": [
                        {
                            "id": "pizza_margherita",
                            "title": "Pizza Margherita",
                            "description": "Domates sosu, mozzarella ve fesleğen. Fiyat: 50₺"
                        },
                        {
                            "id": "cheeseburger",
                            "title": "Cheeseburger",
                            "description": "Burger peyniri ve özel soslar. Fiyat: 40₺"
                        }
                    ]
                },
                {
                    "title": "İçecekler",
                    "rows": [
                        {
                            "id": "limonata",
                            "title": "Limonata",
                            "description": "Taze limon ile hazırlanmıştır. Fiyat: 15₺"
                        }
                    ]
                }
            ]
        }
    }
}

headers = {
    "Authorization": f"Bearer EAAYjJkjWxhcBO5xZB6cZCZAeO8bjDryHhR0AXRhQcocRkC7r9CZC016QydKu3ZB67t9oDkZCSommZBxeRKxrZAJ4JE5d9svQ4xvOZAMYsJM3kbCMa240EKDzhBSenUI0EWQ0m9c1tFB23h0cIuMmMVnIalgo0qUveUDEdzRsZBuVPjmQPsfC7dwiye7FfpiUxtFH4ZBZCxrR9MZCBj38n5jmJuWfroaBMNCIHdFz2PbYr7D4rEz0ZD",
    "Content-Type": "application/json"
}

response = requests.post(API_URL, headers=headers, json=data)

print("Status Code:", response.status_code)
print("Response:", response.json())
