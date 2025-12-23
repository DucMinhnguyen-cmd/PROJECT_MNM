import sqlite3, time, re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

# ---------------------------------------------------------
# 1. CẤU HÌNH DATABASE
# ---------------------------------------------------------
DB_FILE = r"D:\Program\PROJECT\cellphones.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS products")
cursor.execute("""
CREATE TABLE products (
    product_url TEXT PRIMARY KEY,
    brand TEXT,
    product_name TEXT,
    category TEXT,
    product_type TEXT,
    price INTEGER,
    ram TEXT,
    screen TEXT,
    chip TEXT,
    review_count INTEGER,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# ---------------------------------------------------------
# 2. KHỞI TẠO TRÌNH DUYỆT
# ---------------------------------------------------------
options = Options()
options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
driver = webdriver.Firefox(options=options)

def detect_brand(name):
    name_l = name.lower()
    brands = ['iPhone', 'Samsung', 'Oppo', 'Xiaomi', 'Vivo', 'Realme', 'Nokia', 'Asus', 'Tecno', 'Huawei', 'Apple', 'Garmin', 'Sony', 'JBL', 'Marshall', 'Lenovo', 'Sennheiser']
    for b in brands:
        if b.lower() in name_l: return 'Apple' if b == 'iphone' else b.capitalize()
    return "Khác"

# ---------------------------------------------------------
# 3. DANH SÁCH MỤC TIÊU (Giữ nguyên theo yêu cầu của bạn)
# ---------------------------------------------------------
targets = [
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone", "type": "Mới"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet", "type": "Mới"},
    {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop", "type": "Mới"},
    {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch", "type": "Mới"},
    {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe", "type": "Phụ kiện"},
    {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone", "type": "Cũ"},
    {"url": "https://cellphones.com.vn/hang-cu/laptop.html", "cat": "Laptop", "type": "Cũ"}
]

try:
    for target in targets:
        print(f"\n🚀 Đang quét: {target['cat']} ({target['type']})")
        driver.get(target['url'])
        time.sleep(4)

        # Bung danh sách sản phẩm (Nhấn Xem thêm)
        for _ in range(10): 
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
            except: break

        items = driver.find_elements(By.CLASS_NAME, "product-info-container")
        links_to_crawl = []
        for p in items:
            try:
                name = p.find_element(By.TAG_NAME, "h3").text.strip()
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")
                price_text = p.find_element(By.CLASS_NAME, "product__price--show").text
                price = int(re.sub(r"[^\d]", "", price_text))
                links_to_crawl.append({"name": name, "link": link, "price": price})
            except: continue

        # ---------------------------------------------------------
        # 4. DEEP CRAWLING (Lấy Chip, RAM, Cấu hình & Review Count)
        # ---------------------------------------------------------
        for idx, item in enumerate(links_to_crawl):
            try:
                driver.get(item['link'])
                time.sleep(3)

                ram, screen, chip, reviews = "N/A", "N/A", "N/A", 0
                
                # A. Lấy Chipset, RAM, Màn hình từ bảng technical-content
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table.technical-content tr")
                    for row in rows:
                        txt = row.text.lower()
                        val = row.find_elements(By.TAG_NAME, "td")[-1].text.strip()
                        if "ram" in txt or "dung lượng ram" in txt: ram = val
                        elif "màn hình" in txt: screen = val
                        elif "chip" in txt or "cpu" in txt: chip = val
                except: pass
                
                # B. Lấy số lượng đánh giá (Tối ưu để không bị ra số 0)
                try:
                    driver.execute_script("window.scrollTo(0, 1000);")
                    time.sleep(1.5)
                    rev_el = driver.find_element(By.CSS_SELECTOR, "p.boxReview-score__count")
                    reviews = int(re.sub(r"[^\d]", "", rev_el.text))
                except: 
                    reviews = 0

                # C. Lưu vào Database
                cursor.execute("""
                    INSERT OR IGNORE INTO products 
                    (product_url, brand, product_name, category, product_type, price, ram, screen, chip, review_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['link'], detect_brand(item['name']), item['name'], target['cat'], target['type'], item['price'], ram, screen, chip, reviews))
                conn.commit()
                print(f"   [{idx+1}] Lưu: {item['name'][:20]}... | Review: {reviews}")

            except Exception as e:
                continue

finally:
    driver.quit()
    print("\n" + "="*40)
    print("BÁO CÁO PHÂN TÍCH")
    print("="*40)
    df = pd.read_sql_query("SELECT brand, COUNT(*) as SL, SUM(review_count) as Tong_Review FROM products GROUP BY brand ORDER BY SL DESC", conn)
    print(df)
    conn.close()