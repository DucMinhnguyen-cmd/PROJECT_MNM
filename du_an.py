import sqlite3, os, time, re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

# -------------------------------
# 1. CẤU HÌNH SQLITE
# -------------------------------
DB_FILE = r"D:\Program\lo\ma_nguon_mo\sqlite\cellphones_do_an.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Tạo bảng với các cột phục vụ phân tích đồ án
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_url TEXT PRIMARY KEY,
    brand TEXT,
    product_name TEXT,
    category TEXT,          -- Smartphone / Tablet
    product_type TEXT,      -- Mới / Cũ
    price INTEGER,
    rating_count INTEGER,   -- Số lượt đánh giá để biết độ HOT
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# -------------------------------
# 2. HÀM TIỆN ÍCH
# -------------------------------
def parse_number(text):
    return int(re.sub(r"[^\d]", "", text or "") or 0)

def detect_brand(name):
    # Tự động lấy hãng từ từ đầu tiên của tên sản phẩm
    first_word = name.split()[0]
    mapping = {"iPhone": "Apple", "iPad": "Apple"}
    return mapping.get(first_word, first_word)

# -------------------------------
# 3. CẤU HÌNH FIREFOX
# -------------------------------
firefox_options = Options()
# Gán đường dẫn file exe của bạn
firefox_options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"

# Khởi tạo Driver thông qua Service
service = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=firefox_options)

# -------------------------------
# 4. DANH SÁCH MỤC TIÊU CÀO
# -------------------------------
targets = [
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone", "type": "Mới"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet", "type": "Mới"},
    {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/hang-cu/may-tinh-bang.html", "cat": "Tablet", "type": "Cũ"}
]

# -------------------------------
# 5. QUY TRÌNH CÀO DỮ LIỆU
# -------------------------------
try:
    total_saved = 0
    for target in targets:
        print(f"\n🚀 Đang cào: {target['cat']} ({target['type']})")
        driver.get(target['url'])
        time.sleep(5) # Chờ trang load ban đầu

        # Nhấn "Xem thêm" 15 lần để bung hết sản phẩm (mỗi lần ~20-30 máy)
        for i in range(15):
            try:
                # Tìm nút Xem thêm của CellphoneS
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
            except:
                break # Hết nút thì dừng

        # Lấy tất cả card sản phẩm đã bung ra
        items = driver.find_elements(By.CSS_SELECTOR, "div.product-info")
        
        for item in items:
            try:
                name = item.find_element(By.CSS_SELECTOR, "div.product__name h3").text.strip()
                link = item.find_element(By.TAG_NAME, "a").get_attribute("href")
                price = parse_number(item.find_element(By.CSS_SELECTOR, "p.product__price--show").text)
                
                # Lấy Rating Count (Số lượt đánh giá)
                try:
                    rating_raw = item.find_element(By.CSS_SELECTOR, "div.product__rating").text
                    # Trích xuất số cuối cùng trong ngoặc đơn (số đánh giá)
                    rating_count = int(re.findall(r"\d+", rating_raw)[-1])
                except:
                    rating_count = 0

                brand = detect_brand(name)

                cursor.execute("""
                    INSERT OR IGNORE INTO products (product_url, brand, product_name, category, product_type, price, rating_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (link, brand, name, target['cat'], target['type'], price, rating_count))
                total_saved += 1
            except:
                continue
        
        conn.commit()
        print(f"✔ Đã lưu xong danh mục {target['cat']}")

finally:
    driver.quit()
    print(f"\n✅ HOÀN THÀNH: Tổng cộng đã lưu {total_saved} sản phẩm.")

# -------------------------------
# 6. TRUY VẤN PHÂN TÍCH ĐỒ ÁN
# -------------------------------
def run_query(sql):
    return pd.read_sql_query(sql, conn)

print("\n" + "="*40)
print("BÁO CÁO PHÂN TÍCH NHÃN HIỆU")
print("="*40)

# 1. Top hãng bán chạy (Dựa trên tổng đánh giá)
print("\n🔥 Top 5 hãng Bán chạy nhất (Tương tác cao nhất):")
print(run_query("""
    SELECT brand, SUM(rating_count) as total_feedback
    FROM products
    GROUP BY brand
    ORDER BY total_feedback DESC LIMIT 5;
"""))

# 2. Hãng có dấu hiệu tụt dốc (Nhiều model nhưng ít người mua/đánh giá)
print("\n📉 Top 5 hãng có dấu hiệu Tụt dốc (Chỉ số hiệu quả thấp):")
print(run_query("""
    SELECT brand, COUNT(*) as total_models, 
           ROUND(CAST(SUM(rating_count) AS FLOAT) / COUNT(*), 2) as efficiency_score
    FROM products
    GROUP BY brand
    HAVING total_models > 5
    ORDER BY efficiency_score ASC LIMIT 5;
"""))

conn.close()