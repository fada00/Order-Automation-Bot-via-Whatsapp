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
