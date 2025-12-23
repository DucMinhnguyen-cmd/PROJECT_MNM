import sqlite3, time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

# 1. CẤU HÌNH DATABASE
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
    price INTEGER,
    ram TEXT,
    screen TEXT,
    chip TEXT,
    review_count INTEGER,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# 2. KHỞI TẠO TRÌNH DUYỆT
options = Options()
options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
driver = webdriver.Firefox(options=options)

def detect_brand(name):
    name_l = name.lower()
    # Mở rộng danh sách hãng cho cả Tai nghe và Đồng hồ
    brands = ['iPhone', 'Samsung', 'Oppo', 'Xiaomi', 'Vivo', 'Realme', 'Nokia', 'Asus', 'Tecno', 'Huawei', 'Apple', 'Garmin', 'Sony', 'JBL', 'Marshall', 'Lenovo']
    for b in brands:
        if b.lower() in name_l: return 'Apple' if b == 'iphone' else b.capitalize()
    return "Khác"

# 3. DANH SÁCH MỤC TIÊU (Đã thêm Đồng hồ & Tai nghe)
targets = [
    {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone"},
    {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet"},
    {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop"},
    {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch"},
    {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe"}
]

try:
    for target in targets:
        print(f"\n🚀 Đang quét danh mục: {target['cat']}")
        driver.get(target['url'])
        time.sleep(4)

        # Bung danh sách sản phẩm
        for i in range(15): 
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
            except: break

        # Lấy danh sách link sơ bộ
        items = driver.find_elements(By.CLASS_NAME, "product-info-container")
        links_to_crawl = []
        for p in items:
            try:
                name = p.find_element(By.TAG_NAME, "h3").text.strip()
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")
                try:
                    price_text = p.find_element(By.CLASS_NAME, "product__price--show").text
                    price = int(re.sub(r"[^\d]", "", price_text))
                except: price = 0
                links_to_crawl.append({"name": name, "link": link, "price": price})
            except: continue

        # Deep Crawling
        for idx, item in enumerate(links_to_crawl):
            try:
                driver.get(item['link'])
                time.sleep(2.5)

                ram, screen, chip, reviews = "N/A", "N/A", "N/A", 0
                
                # A. Lấy thông số kỹ thuật
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table.technical-content tr")
                    for row in rows:
                        txt = row.text.lower()
                        val = row.find_elements(By.TAG_NAME, "td")[-1].text.strip()
                        if "ram" in txt: ram = val
                        elif "màn hình" in txt: screen = val
                        elif "chip" in txt or "cpu" in txt: chip = val
                except: pass
                
                # B. Lấy số lượng đánh giá (Tối ưu hóa khả năng load)
                try:
                    # 1. Cuộn chuột xuống vị trí 1200px (thường là nơi đặt phần đánh giá)
                    driver.execute_script("window.scrollTo(0, 1200);")
                    
                    # 2. Nghỉ 2 giây để chờ dữ liệu đánh giá tải từ Server về trình duyệt
                    time.sleep(2) 

                    # 3. Tìm thẻ chứa số lượt đánh giá
                    review_el = driver.find_element(By.CSS_SELECTOR, "p.boxReview-score__count")
                    review_text = review_el.text.strip()
                    
                    # 4. Trích xuất con số (VD: "54 lượt đánh giá" -> 54)
                    review_count = int(re.sub(r"[^\d]", "", review_text))
                    
                except:
                    # Nếu cuộn xuống và đợi rồi vẫn không có, thì sản phẩm đó thực sự 0 đánh giá
                    review_count = 0

                # C. Lưu Database
                cursor.execute("""
                    INSERT OR IGNORE INTO products (product_url, brand, product_name, category, price, ram, screen, chip, review_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['link'], detect_brand(item['name']), item['name'], target['cat'], item['price'], ram, screen, chip, reviews))
                conn.commit()
                print(f"   [{idx+1}/{len(links_to_crawl)}] Đã lưu: {item['name'][:25]}... | Review: {reviews}")

            except Exception as e:
                continue

finally:
    driver.quit()
    conn.close()
    print("\n" + "="*40)
    print("✅ HOÀN THÀNH CÀO DỮ LIỆU")
    print("="*40)