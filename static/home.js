function updateStatus(button) {
    // Tüm kardeş butonların class'ını sıfırla
    const siblings = button.parentElement.children;
    for (const sibling of siblings) {
        sibling.classList.remove("active");
    }
    // Tıklanan butona 'active' class'ı ekle
    button.classList.add("active");


function updateOrderStatus(orderId, newStatus) {
    fetch('/update-order-status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
         body: JSON.stringify({ order_id: orderId, status: newStatus }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {

            location.reload(); // Sayfayı yenileyerek yeni durumları göstermek için
        } else {
            alert('Güncelleme sırasında bir hata oluştu.');
        }
    })
    .catch(error => console.error('Error:', error));   
}

// WebSocket (SocketIO) bağlantısını aç
const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

// Zil sesi dosyası (static klasöründe 'notification.mp3' olmalı)
const notificationSound = new Audio('/static/ding_gooog.mp3');

// Yeni sipariş geldiğinde sesi çal
socket.on("new_order", function(data) {
    console.log("Yeni sipariş alındı!", data);
    notificationSound.play(); // Zil sesini çal
    updateOrderList(data.orders); // Sipariş listesini güncelle
});

// Sipariş listesini güncelleyen fonksiyon
function updateOrderList(orders) {
    const ordersContainer = document.getElementById("ordersContainer"); // Siparişlerin bulunduğu div
    ordersContainer.innerHTML = ""; // Mevcut siparişleri temizle

    Object.values(orders).forEach(order => {
        let orderHtml = `
            <div class="order">
                <h3>Sipariş #${order.id} - ${order.customer_name}</h3>
                <p><strong>Telefon:</strong> ${order.phone}</p>
                <p><strong>Adres:</strong> ${order.address}</p>
                <p><strong>Tarih:</strong> ${order.date}</p>
                <p><strong>Toplam:</strong> ${order.total} TL</p>
                <p><strong>Durum:</strong> ${order.status}</p>
                <p><strong>Ödeme:</strong> ${order.payment}</p>
                <p><strong>Ürünler:</strong></p>
                <ul>${order.itemss.map(item => `<li>${item}</li>`).join('')}</ul>
            </div>
        `;
        ordersContainer.innerHTML += orderHtml;
    });
}

// Sayfa yüklendiğinde mevcut siparişleri getir
fetch('/get-orders')
    .then(response => response.json())
    .then(data => updateOrderList(data))
    .catch(error => console.error("Siparişleri getirirken hata oluştu:", error));

// Sipariş durumunu güncelleme fonksiyonu
function updateOrderStatus(orderId, newStatus) {
    fetch('/update-order-status', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
         body: JSON.stringify({ order_id: orderId, status: newStatus }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload(); // Sayfayı yenileyerek yeni durumları göstermek için
        } else {
            alert('Güncelleme sırasında bir hata oluştu.');
        }
    })
    .catch(error => console.error('Error:', error));   
}