import sqlite3, time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

# 1. CẤU HÌNH DATABASE (Xóa Rating, Thêm RAM, Chip, Screen)
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
    brands = ['iPhone', 'Samsung', 'Oppo', 'Xiaomi', 'Vivo', 'Realme', 'Nokia', 'Asus', 'Tecno', 'Huawei']
    for b in brands:
        if b.lower() in name_l: return 'Apple' if b == 'iphone' else b.capitalize()
    return "Khác"

targets = [{"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone"}]

try:
    for target in targets:
        print(f"🚀 Đang quét danh mục: {target['cat']}")
        driver.get(target['url'])
        time.sleep(5)

        # BUNG HẾT SẢN PHẨM (Nhấn xem thêm)
        for i in range(15): # Để test thử 15 lần trước cho nhanh
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
            except: break

        # LẤY DANH SÁCH LINK VÀ GIÁ (Giai đoạn 1)
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

        print(f"✅ Thu thập được {len(links_to_crawl)} link. Bắt đầu cào sâu chi tiết...")

        # CÀO CHI TIẾT TỪNG LINK (Giai đoạn 2 - Deep Crawling)
        for item in links_to_crawl:
            try:
                driver.get(item['link'])
                time.sleep(3) # Đợi load bảng thông số

                ram, screen, chip, reviews = "N/A", "N/A", "N/A", 0
                
                # 1. Lấy RAM, Chip, Màn hình từ bảng technical-content
                rows = driver.find_elements(By.CSS_SELECTOR, "table.technical-content tr")
                for row in rows:
                    txt = row.text.lower()
                    val = row.find_elements(By.TAG_NAME, "td")[-1].text.strip()
                    if "dung lượng ram" in txt: ram = val
                    elif "kích thước màn hình" in txt: screen = val
                    elif "chipset" in txt: chip = val
                
                # 2. Lấy số lượng đánh giá (thay cho số lượng bán)
                try:
                    rev_text = driver.find_element(By.CLASS_NAME, "boxReview-score-total").text
                    reviews = int(re.sub(r"[^\d]", "", rev_text))
                except: reviews = 0

                # 3. LƯU VÀO DATABASE NGAY LẬP TỨC
                cursor.execute("""
                    INSERT OR IGNORE INTO products (product_url, brand, product_name, category, price, ram, screen, chip, review_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['link'], detect_brand(item['name']), item['name'], target['cat'], item['price'], ram, screen, chip, reviews))
                conn.commit() # Lưu ngay sau mỗi sản phẩm để tránh bảng rỗng
                print(f"   ✔ Đã lưu: {item['name'][:25]}...")

            except Exception as e:
                print(f"   ❌ Lỗi tại {item['name']}: {e}")
                continue

finally:
    driver.quit()
    conn.close()
    print("\n--- HOÀN THÀNH ---")