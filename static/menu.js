function updateStatus(button) {
    // Tüm kardeş butonların class'ını sıfırla
    const siblings = button.parentElement.children;
    for (const sibling of siblings) {
        sibling.classList.remove("active");
    }
    // Tıklanan butona 'active' class'ı ekle
    button.classList.add("active");
}


// Başlangıç verilerini yükle
window.onload = async function() {
    try {
        const response = await fetch('/menus/get-initial-data');
        const data = await response.json();

        console.log("Veriler yüklendi:", data); // Gelen veriyi kontrol edin
        const categorySelect = document.getElementById('productCategory');

        if (data.categories.length > 0) {
            data.categories.forEach(category => {
                const option = document.createElement('option');
                option.value = category; // Option value
                option.textContent = category; // Option text
                categorySelect.appendChild(option); // Dropdown'a ekle
            });
        } else {
            console.error("Hiç kategori bulunamadı!");
        }
        if (data.options.length > 0) {
            window.existingOptions = data.options; // Gelen opsiyonları kaydedin
        } else {
            console.error("Hiç opsiyon bulunamadı!");
            window.existingOptions = []; // Boş bir opsiyon listesi atayın
        }
    } catch (error) {
        console.error("Kategori yükleme hatası:", error);
    }
};

// Kategorileri doldur
function populateCategories(categories) {
    const categorySelect = document.getElementById('productCategory');
    data.categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category; // Option değerini ayarlayın
        option.textContent = category; // Görünen metni ayarlayın
        categorySelect.appendChild(option); // Dropdown'a ekleyin
    });
}

// Opsiyon ekleme
function addOption() {
    const container = document.getElementById('optionsContainer');
    if (!container) {
        console.error("optionsContainer bulunamadı!");
        return;
    }
    const optionDiv = document.createElement('div');
    optionDiv.classList.add('option-container');

    const selectHTML = `
        <select onchange="handleOptionChange(this)">
            <option value="">Yeni opsiyon eklemek için yazın...</option>
            ${window.existingOptions.map(option => `
                <option value="${option.id}" data-name="${option.name}" data-price="${option.price}">
                    ${option.name} (${option.price} ₺)
                </option>`).join('')}
        </select>
    `;
    const inputHTML = `
        <input type="text" placeholder="Yeni opsiyon adı" id="newOptionName">
        <input type="number" placeholder="Yeni opsiyon fiyatı" id="newOptionPrice">
        <button type="button" onclick="removeOption(this)">Sil</button>
    `;
    optionDiv.innerHTML = `${selectHTML} veya ${inputHTML}`;
    container.appendChild(optionDiv);
}

window.addOption = addOption;

// Opsiyon silme
function removeOption(button) {
    button.parentElement.remove();
}

// Opsiyon değişimi
function handleOptionChange(select) {
    const optionDiv = select.parentElement;
    const nameInput = optionDiv.querySelector('input[type="text"]');
    const priceInput = optionDiv.querySelector('input[type="number"]');

    // Eğer dropdown'da bir değer seçilmişse
    if (select.value) {
        const selectedOption = select.options[select.selectedIndex];
        nameInput.value = selectedOption.getAttribute('data-name');
        priceInput.value = selectedOption.getAttribute('data-price');
        
        // Seçim yapıldıysa, inputları devre dışı bırak
        nameInput.disabled = true;
        priceInput.disabled = true;
    } else {
        // Seçim yapılmadıysa, inputları aktif yap
        nameInput.value = "";
        priceInput.value = "";
        nameInput.disabled = false;
        priceInput.disabled = false;
    }
}

// Ürün kaydetme
async function saveProduct() {
    const productName = document.getElementById('productName').value;
    const categorySelect = document.getElementById('productCategory');
    const selectedCategory = categorySelect.value || document.getElementById('newCategory').value;
    const productPrice = parseFloat(document.getElementById('productPrice').value);

    const options = Array.from(document.querySelectorAll('#optionsContainer .option-container')).map(div => {
        const select = div.querySelector('select');
        if (select.value) {
            return {
                existing: true,
                id: select.value
            };
        } else {
            return {
                existing: false,
                name: div.querySelector('input[type="text"]').value,
                price: parseFloat(div.querySelector('input[type="number"]').value)
            };
        }
    });

    if (!productName || !selectedCategory || isNaN(productPrice)) {
        alert('Lütfen tüm alanları doldurun.');
        return;
    }

    try {
        const response = await fetch('/menus/save-product', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product: { name: productName, category: selectedCategory, price: productPrice },
                options
            })
        });

        const result = await response.json();
        if (result.success) {
            alert('Ürün başarıyla kaydedildi!');
            location.reload();
        } else {
            alert('Ürün kaydedilemedi: ' + result.message);
        }
    } catch (error) {
        console.error('Kaydetme sırasında hata:', error);
        alert('Ürün kaydedilirken bir hata oluştu. Lütfen tekrar deneyin.');
    }
}
//menü oluşturma tabı


let selectedProducts = [];

// Ürünleri yükle
function loadProducts() {
    fetch('menus/get-products')
        .then(response => response.json())
        .then(data => {
            const productsContainer = document.getElementById('productsContainer');
            const menuCategory = document.getElementById("menuCategory");
            productsContainer.innerHTML = ''; // Mevcut ürünleri temizle

            data.menu_categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category; // Option value
            option.textContent = category; // Option text
            option.textContent = category; // Option text
            menuCategory.appendChild(option); // Dropdown'a ekle
                });

            Object.keys(data.products).forEach(category => {
                //kategori başlığı
                const categoryDiv = document.createElement('div');
                categoryDiv.classList.add('category-container');

                const categoryTitle = document.createElement('div');
                categoryTitle.classList.add('category-title');
                categoryTitle.textContent = category;
                categoryDiv.appendChild(categoryTitle);

                //ürün grid
                const productsGrid = document.createElement('div');
                productsGrid.classList.add('products-grid');

                data.products[category].forEach(product => {
                    const productDiv = document.createElement('div');
                    productDiv.classList.add('product-item');

                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.value = product.id;
                    checkbox.id = `product-${product.id}`;
                    checkbox.onchange = (e) => toggleAmountInput(e, product.id);

                    const amountInput = document.createElement('input');
                    amountInput.type = 'number';
                    amountInput.placeholder = 'Miktar';
                    amountInput.min = 1;
                    amountInput.value = 1;
                    amountInput.id = `amount-${product.id}`;
                    amountInput.classList.add('amount-input');
                    amountInput.style.display = 'none'; // Varsayılan olarak gizle

                    const label = document.createElement('label');
                    label.htmlFor = `product-${product.id}`;
                    label.textContent = `${product.name} - ${product.price} ₺`;

                    productDiv.appendChild(checkbox);
                    productDiv.appendChild(label);
                    productDiv.appendChild(amountInput);
                    productsGrid.appendChild(productDiv);

            });
            categoryDiv.appendChild(productsGrid);
            productsContainer.appendChild(categoryDiv);
        });
    })
    .catch(err => console.error("Ürünler yüklenirken hata oluştu:", err));
}

// Miktar girişini göster/gizle
function toggleAmountInput(event, productId) {
    const amountInput = document.getElementById(`amount-${productId}`);
    if (event.target.checked) {
        amountInput.style.display = 'inline-block'; // Görünür yap
    } else {
        amountInput.style.display = 'none'; // Gizle
        amountInput.value = ''; // Değeri sıfırla
    }
}


// Ürünleri menüye ekle
function addProductToMenu() {
    const productsContainer = document.getElementById('productsContainer');
    const checkboxes = productsContainer.querySelectorAll('input[type="checkbox"]:checked');

    checkboxes.forEach(checkbox => {
        const productId = checkbox.value;
        const amountInput = document.getElementById(`amount-${productId}`);
        const amount = parseInt(amountInput.value, 10);

        if (!amount || amount <= 0) {
            alert('Lütfen miktar girin!');
            return;
        }

        if (!selectedProducts.includes(productId)) {
            selectedProducts.push({id: productId, amount});

            const productLabel = checkbox.nextSibling.textContent;

            const menuProductDiv = document.createElement('div');
            menuProductDiv.textContent = productLabel;

            const removeButton = document.createElement('button');
            removeButton.textContent = 'Kaldır';
            removeButton.onclick = () => {
                menuProductDiv.remove();
                selectedProducts = selectedProducts.filter(id => id !== productId);
            };

            menuProductDiv.appendChild(removeButton);
            document.getElementById('menuProductsContainer').appendChild(menuProductDiv);
        }
    });
}

// Menüyü kaydet
function saveMenu() {
    const menuName = document.getElementById('menuName').value;
    const categorySelect = document.getElementById('menuCategory');
    const selectedCategory = categorySelect.value || document.getElementById('newMenuCategory').value;
    const menuDescription = document.getElementById('menuDescription').value;
    const menuPrice = parseFloat(document.getElementById('menuPrice').value);

    if (!menuName || !menuPrice || selectedProducts.length === 0) {
        alert('Tüm alanları doldurmanız gerekiyor!');
        return;
    }

    const menuData = {
        name: menuName,
        category: selectedCategory,
        description: menuDescription,
        price: menuPrice,
        products: selectedProducts,
    };

    fetch('/save-menu', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(menuData),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Menü başarıyla kaydedildi!');
                selectedProducts = [];
                document.getElementById('menuProductsContainer').innerHTML = '';
                document.getElementById('newMenuCategory').value = '';
                document.getElementById('menuName').value = '';
                document.getElementById('menuDescription').value = '';
                document.getElementById('menuPrice').value = '';
            } else {
                alert('Menü kaydedilirken bir hata oluştu.');
            }
        })
        .catch(err => console.error("Menü kaydedilirken hata oluştu:", err));
}

function showTab(tabId) {
    console.log("Switching to tab:", tabId);

    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));

    const activeTab = document.getElementById(tabId);
    if (activeTab) {
        activeTab.classList.add('active');
    } else {
        console.error("Tab not found for tabId: " + tabId);
        return;
    }

    if(tabId === 'createMenuTab') {
        loadProducts();
    }

    const buttons = document.querySelectorAll('.tab-bar button');
    buttons.forEach(button => button.classList.remove('active'));

    const targetButton = document.getElementById(tabId + "Button");
    if (targetButton) {
        targetButton.classList.add('active');
    } else {
        console.error("Button not found for tabId: " + tabId);
    }
}

// ürün güncelleme tabı

// Kategorileri yükle
function loadCategories() {
    fetch('/get-items/products') // Kategoriler products tablosundan alınacak
        .then(response => response.json())
        .then(data => {
            const categoryFilter = document.getElementById('categoryFilter');
            const categories = [...new Set(data.items.map(item => item.category))]; // Tekil kategoriler
            categories.forEach(category => {
                if (category) { // Kategori boş değilse ekle
                    const option = document.createElement('option');
                    option.value = category;
                    option.textContent = category;
                    categoryFilter.appendChild(option);
                }
            });
        })
        .catch(err => console.error('Kategoriler yüklenirken hata oluştu:', err));
}

// verileri yükle
function loadData() {
    const selectedOption = document.getElementById('itemSelect').value;
    if (!selectedOption) return;

    fetch(`/get-items/${selectedOption}`)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('dataTableBody');
            tableBody.innerHTML = ''; // Mevcut tabloyu temizle

            data.items.forEach(item => {
                const row = document.createElement('tr');

                const idCell = document.createElement('td');
                idCell.textContent = item.id;

                const nameCell = document.createElement('td');
                nameCell.textContent = item.name;

                const priceCell = document.createElement('td');
                priceCell.textContent = `${item.price} ₺`;

                const actionCell = document.createElement('td');

                const editButton = document.createElement('button');
                editButton.textContent = 'Düzenle';
                editButton.classList.add('edit-button');
                editButton.onclick = () => openEditModal(item);

                const deleteButton = document.createElement('button');
                deleteButton.classList.add("delete-button-price");
                deleteButton.textContent = 'Sil';
                deleteButton.onclick = () => deleteItem(selectedOption, item.id);

                actionCell.appendChild(editButton);
                actionCell.appendChild(deleteButton);

                row.appendChild(idCell);
                row.appendChild(nameCell);
                row.appendChild(priceCell);
                row.appendChild(actionCell);

                tableBody.appendChild(row);
            });
        })
        .catch(err => console.error('Veri yüklenirken hata oluştu:', err));
}

function saveEdit() {
    const id = document.getElementById('editItemId').value;
    const name = document.getElementById('editName').value;
    const price = parseFloat(document.getElementById('editPrice').value);
    const selectedOption = document.getElementById('itemSelect').value;

    fetch(`/update-item/${selectedOption}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, price }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Güncelleme başarılı!');
                closeEditModal();
                loadData();
            } else {
                alert('Güncelleme sırasında hata oluştu.');
            }
        })
        .catch(err => console.error('Güncelleme hatası:', err));
}

function deleteItem(type, id) {
    fetch(`/delete-item/${type}/${id}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Silme işlemi başarılı!');
                loadData();
            } else {
                alert('Silme işlemi sırasında hata oluştu.');
            }
        })
        .catch(err => console.error('Silme hatası:', err));
}

function openEditModal(item) {
    console.log("Gönderilen item:", item);
    const editItemId = document.getElementById('editItemId');
    const editName = document.getElementById('editName');
    const editPrice = document.getElementById('editPrice');

    if (editItemId && editName && editPrice) {
        document.getElementById('editPopup').classList.remove('hidden');

        // Var olan bilgileri doldur
        editItemId.value = item.id; // ID saklanır
        editName.value = item.name;
        editPrice.value = item.price;
    } else {
        console.error("Edit modal öğeleri bulunamadı.");
    }
}

function closeEditPopup() {
    document.getElementById('editPopup').classList.add('hidden');
}

function saveProductChanges() {
    const name = document.getElementById('editName').value.trim();
    const price = parseFloat(document.getElementById('editPrice').value);

    if (!name || isNaN(price)) {
        alert('Tüm alanları doldurmanız gerekiyor!');
        return;
    }

    const updatedProduct = {
        name,
        price,
        id: document.getElementById('editItemId').value,
    };

    fetch(`/update-product`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatedProduct),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Ürün başarıyla güncellendi!');
                closeEditPopup();
                loadData(); // Tabloyu yeniden yükle
            } else {
                alert('Ürün güncellenirken bir hata oluştu.');
            }
        })
        .catch(err => console.error('Ürün güncellenirken hata oluştu:', err));
}


// kupon tabı

document.addEventListener("DOMContentLoaded", function () {
    fetchCoupons();
});

// Kuponları çek ve listele
function fetchCoupons() {
    fetch("/get_coupons")
        .then(response => {
            if (!response.ok) {
                throw new Error("Kuponlar alınırken hata oluştu!");
            }
            return response.json();
        })
        .then(data => {
            const couponTableBody = document.getElementById("couponTableBody");
            couponTableBody.innerHTML = ""; // Önceki içeriği temizle
            
            data.coupons.forEach(coupon => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${coupon.code}</td>
                    <td>${coupon.discount}</td>
                    <td>${coupon.min_price}</td>
                    <td>${coupon.max_usage_limit}</td>
                    <td>${coupon.current_usage}</td>
                    <td>
                        <button class="delete-coupon" onclick="deleteCoupon('${coupon.code}')">Sil</button>
                    </td>
                `;
                couponTableBody.appendChild(row);
            });
        })
        .catch(error => {
            if (error instanceof Error) {
                console.error("Hata:", error.message);
            } else {
                console.error("Hata:", error);
            }
        });
}

// Yeni kupon ekleme fonksiyonu
function addCoupon() {
    const code = document.getElementById("couponCode").value.trim();
    const discount = parseFloat(document.getElementById("couponDiscount").value);
    const minPrice = parseInt(document.getElementById("couponMinPrice").value,5);
    const maxUsage = parseInt(document.getElementById("couponMaxUsage").value, 10);

    if (!code || isNaN(discount) || isNaN(minPrice) || isNaN(maxUsage)) {
        alert("Lütfen geçerli değerler girin!");
        return;
    }
    if (discount <= 0) {
        alert("İndirim oranı 0'dan büyük olmalıdır!");
        return;
    }
    if (minPrice <= 0) {
        alert("Minimum fiyat 0'dan küçük olamaz");
        return;
    }

    const data= {
        code: code,
        discount: discount,
        min_price: minPrice,
        max_usage_limit: maxUsage,
        current_usage: 0
    }

    fetch("/add_coupon", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify( data)
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        if (response.ok) {
            fetchCoupons(); // Kuponları tekrar listele
        }
    })
    .catch(error => console.error("Hata:", error.message));
}

// Kupon silme fonksiyonu
function deleteCoupon(code) {
    if (!confirm("Bu kuponu silmek istediğinizden emin misiniz?")) {
        return;
    }

    fetch(`/delete_coupon/${code}`, {
        method: "DELETE",
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Kupon silinemedi!");
        }
        return response.json();
    })
    .then(data => {
        alert(data.message);
        if (data.message.includes("başarıyla")) {
            fetchCoupons(); // Güncellenmiş listeyi tekrar getir
        }
    })
    .catch(error => console.error("Hata:", error.message));
}