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
# Lấy đường dẫn của thư mục hiện tại đang chứa file code này
base_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(base_dir, "cellphones_do_an.db")
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
firefox_options.binary_location = r"c:\Program Files\Mozilla Firefox\firefox.exe"

# Khởi tạo Driver thông qua Service
service = Service(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=firefox_options)

# -------------------------------
# 4. DANH SÁCH MỤC TIÊU CÀO
# -------------------------------
targets = [
    # Nhóm Mobile/Tablet
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone", "type": "Mới"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet", "type": "Mới"},
    
    # Nhóm Laptop (Số lượng cực lớn)
    {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop", "type": "Mới"},
    
    # Nhóm Đồng hồ & Tai nghe (Phụ kiện nhiều mẫu mã)
    {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch", "type": "Mới"},
    {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe", "type": "Phụ kiện"},

    # Nhóm Hàng Cũ (Giá rẻ, nhiều dữ liệu)
    {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/hang-cu/laptop.html", "cat": "Laptop", "type": "Cũ"}
]

# -------------------------------
# 5. QUY TRÌNH CÀO DỮ LIỆU
# -------------------------------
try:
    total_saved = 0
    start_time = time.time()
    
    for target in targets:
        print(f"\n🚀 Đang cào danh mục: {target['cat']} ({target['type']})...")
        driver.get(target['url'])
        time.sleep(5) 

        # --- CHIẾN THUẬT CÀO SÂU: Tăng số lần click lên 60 ---
        max_clicks = 120 
        for i in range(max_clicks):
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                # Scroll xuống để tránh bị quảng cáo che
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2) # Nghỉ 2s để load
                
                # In ra tiến độ để đỡ sốt ruột
                if (i+1) % 10 == 0:
                    print(f"  -> Đã click 'Xem thêm' lần thứ {i+1}...")
            except:
                print(f"  -> Đã hết sản phẩm để xem thêm tại lần click {i}.")
                break 

        # Lấy tất cả card sản phẩm
        items = driver.find_elements(By.CSS_SELECTOR, "div.product-info")
        print(f"  -> Tìm thấy {len(items)} sản phẩm trên trang này. Đang lưu...")

        count_in_cat = 0
        for item in items:
            try:
                name = item.find_element(By.CSS_SELECTOR, "div.product__name h3").text.strip()
                link = item.find_element(By.TAG_NAME, "a").get_attribute("href")
                
                # Xử lý giá (có thể rỗng hoặc "Liên hệ")
                try:
                    price_text = item.find_element(By.CSS_SELECTOR, "p.product__price--show").text
                    price = parse_number(price_text)
                except:
                    price = 0
                
                # Xử lý Rating Count
                try:
                    rating_box = item.find_element(By.CSS_SELECTOR, "div.product__rating")
                    if "style" in rating_box.get_attribute("outerHTML") and "display: none" in rating_box.get_attribute("style"):
                         rating_count = 0
                    else:
                        rating_raw = rating_box.text
                        rating_count = int(re.findall(r"\d+", rating_raw)[-1])
                except:
                    rating_count = 0

                brand = detect_brand(name)

                cursor.execute("""
                    INSERT OR IGNORE INTO products (product_url, brand, product_name, category, product_type, price, rating_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (link, brand, name, target['cat'], target['type'], price, rating_count))
                
                if cursor.rowcount > 0: # Chỉ đếm nếu là sản phẩm mới chưa có trong DB
                    count_in_cat += 1
                    total_saved += 1
            except Exception as e:
                continue
        
        conn.commit()
        print(f"✔ Đã lưu mới {count_in_cat} sản phẩm từ danh mục này.")

finally:
    driver.quit()
    print("="*50)
    print(f"✅ HOÀN THÀNH CHIẾN DỊCH! Tổng cộng đã lưu thêm: {total_saved} sản phẩm.")
    print(f"⏱ Thời gian chạy: {int(time.time() - start_time)} giây.")

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