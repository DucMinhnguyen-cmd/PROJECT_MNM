import sqlite3, os, time, re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# 1. CẤU HÌNH SQLITE
DB_FILE = r"D:\Program\PROJECT\cellphones.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Làm mới bảng để cập nhật cấu trúc chuẩn
cursor.execute("DROP TABLE IF EXISTS products")
cursor.execute("""
CREATE TABLE products (
    product_url TEXT PRIMARY KEY,
    brand TEXT,
    product_name TEXT,
    category TEXT,
    price INTEGER,
    rating_score REAL,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# 2. HÀM TIỆN ÍCH
def parse_number(text):
    return int(re.sub(r"[^\d]", "", text or "") or 0)

def detect_brand(name):
    """Nhận diện hãng từ tên sản phẩm để tránh lấy chữ 'Điện thoại'"""
    name_l = name.lower()
    brands = ['iPhone', 'Samsung', 'Oppo', 'Xiaomi', 'Vivo', 'Realme', 'Nokia', 'Asus', 'Tecno', 'Huawei', 'iPad', 'Lenovo']
    for b in brands:
        if b.lower() in name_l:
            return 'Apple' if b in ['iPhone', 'iPad'] else b.capitalize()
    return "Khác"

# 3. KHỞI TẠO FIREFOX (Sử dụng đường dẫn binary của bạn)
options = Options()
options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
# Khởi tạo driver trực tiếp để tránh lỗi Timeout mạng của DriverManager
driver = webdriver.Firefox(options=options)

# 4. DANH SÁCH MỤC TIÊU
targets = [
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet"},
    {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone-Cu"},
    {"url": "https://cellphones.com.vn/hang-cu/may-tinh-bang.html", "cat": "Tablet-Cu"}
]

# 5. QUY TRÌNH CÀO DỮ LIỆU
try:
    for target in targets:
        print(f"\n🚀 Đang cào danh mục: {target['cat']}")
        driver.get(target['url'])
        time.sleep(4)

        # Nhấn "Xem thêm" 40 lần để bung ~1000 sản phẩm
        for i in range(60):
            try:
                # Cuộn xuống để nút hiện ra
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
            except: break

        # CUỘN TRANG TỪ TỪ ĐỂ NẠP DỮ LIỆU (Tránh mất Rating/Giá)
        print("  - Đang nạp dữ liệu đánh giá...")
        for s in range(0, 20):
            driver.execute_script(f"window.scrollTo(0, {s * 1500});")
            time.sleep(0.3)

# Lấy danh sách thẻ sản phẩm (Dựa trên ảnh image_53acac.jpg)
        items = driver.find_elements(By.CSS_SELECTOR, "div.product-info")
        print(f"  - Tìm thấy {len(items)} thẻ. Đang bóc tách...")

        for p in items:
            try:
                # 1. LẤY TÊN SẢN PHẨM (Phải lấy được cái này đầu tiên)
                # Dùng Selector rộng hơn để đảm bảo lấy được h3
                try:
                    name_el = p.find_element(By.TAG_NAME, "h3")
                    product_name = name_el.text.strip()
                except:
                    # Nếu không tìm thấy h3, thử lấy class cụ thể
                    product_name = p.find_element(By.CSS_SELECTOR, ".product__name").text.strip()

                # 2. LẤY LINK
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")
                
                # 3. LẤY GIÁ TIỀN (Sửa Selector cho giá đỏ hiện thị)
                try:
                    # CellphoneS thường dùng class 'product__price--show' hoặc 'special-price'
                    price_text = p.find_element(By.CSS_SELECTOR, "p.product__price--show").text
                    price = parse_number(price_text)
                except:
                    price = 0

                # 4. LẤY SỐ SAO (Dựa trên ảnh image_dfdc2b.jpg của bạn)
                try:
                    # Dùng Javascript để lấy text ẩn nếu cần
                    rating_el = p.find_element(By.CLASS_NAME, "product__box-rating")
                    rating_raw = driver.execute_script("return arguments[0].textContent;", rating_el)
                    # Dùng regex để bắt số (ví dụ '4.9' hoặc '5') từ chuỗi
                    rating_score = float(re.search(r"\d+(\.\d+)?", rating_raw).group())
                except:
                    rating_score = 0.0

                # 5. NHẬN DIỆN THƯƠNG HIỆU (Chỉ chạy khi đã có product_name)
                brand = detect_brand(product_name)

                # KIỂM TRA NẾU CÓ TÊN MỚI LƯU (Tránh lưu dòng trắng)
                if product_name:
                    cursor.execute("""
                        INSERT OR IGNORE INTO products (product_url, brand, product_name, category, price, rating_score)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (link, brand, product_name, target['cat'], price, rating_score))
                
            except Exception as e:
                # In lỗi ra để kiểm tra nếu cần
                # print(f"Lỗi thẻ: {e}")
                continue
        
        conn.commit()
        print(f"  ✔ Đã lưu xong sản phẩm của {target['cat']}")

finally:
    driver.quit()

# 6. THỐNG KÊ KẾT QUẢ
print("\n" + "="*50)
print(pd.read_sql_query("SELECT brand, COUNT(*) as SL, ROUND(AVG(rating_score), 2) as 'Sao_TB' FROM products GROUP BY brand HAVING SL > 5 ORDER BY SL DESC", conn))
conn.close()