import sqlite3, time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

# ---------------------------------------------------------
# 1. CẤU HÌNH DATABASE (Thêm cột 'status' để quản lý tiến độ)
# ---------------------------------------------------------
DB_FILE = r"D:\Program\PROJECT\cellphones.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Tạo bảng (Lưu ý: Không dùng DROP TABLE để giữ dữ liệu cũ)
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_url TEXT PRIMARY KEY,
    brand TEXT,
    product_name TEXT,
    category TEXT,
    price INTEGER,
    ram TEXT,
    screen TEXT,
    chip TEXT,
    review_count INTEGER,
    status INTEGER DEFAULT 0, -- 0: Chưa cào, 1: Đã xong, -1: Lỗi
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
""")
conn.commit()

# ---------------------------------------------------------
# 2. CÁC HÀM HỖ TRỢ
# ---------------------------------------------------------
def init_driver():
    options = Options()
    options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"
    return webdriver.Firefox(options=options)

def detect_brand(name):
    name_l = name.lower()
    brands = ['iPhone', 'Samsung', 'Oppo', 'Xiaomi', 'Vivo', 'Realme', 'Nokia', 'Asus', 'Tecno', 'Huawei', 'Sony', 'JBL', 'Garmin', 'Apple']
    for b in brands:
        if b.lower() in name_l: return 'Apple' if b == 'iphone' else b.capitalize()
    return "Khác"

# ---------------------------------------------------------
# GIAI ĐOẠN 1: THU THẬP LINK (Chỉ chạy khi bạn muốn tìm thêm SP mới)
# ---------------------------------------------------------
def phase_1_gather_links():
    driver = init_driver()
    targets = [
        {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone"},
        {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet"},
        {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch"},
        {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe"},
        {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop"}
    ]
    
    print("\n--- BẮT ĐẦU GIAI ĐOẠN 1: TÌM KIẾM LINK MỚI ---")
    try:
        for target in targets:
            print(f"🚀 Truy cập: {target['cat']}")
            driver.get(target['url'])
            time.sleep(5)

            # Nhấn xem thêm (Tùy chỉnh số lần)
            for i in range(20): 
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                    btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                except: break

            items = driver.find_elements(By.CLASS_NAME, "product-info-container")
            new_count = 0
            for p in items:
                try:
                    name = p.find_element(By.TAG_NAME, "h3").text.strip()
                    link = p.find_element(By.TAG_NAME, "a").get_attribute("href")
                    
                    try:
                        price_text = p.find_element(By.CLASS_NAME, "product__price--show").text
                        price = int(re.sub(r"[^\d]", "", price_text))
                    except: price = 0

                    # Chỉ lưu Link + Tên + Giá. Các thông số khác để NULL. Status = 0
                    cursor.execute("""
                        INSERT OR IGNORE INTO products (product_url, brand, product_name, category, price, status)
                        VALUES (?, ?, ?, ?, ?, 0)
                    """, (link, detect_brand(name), name, target['cat'], price))
                    
                    if cursor.rowcount > 0: new_count += 1
                except: continue
            
            conn.commit()
            print(f"   ✔ Đã tìm thấy {new_count} sản phẩm MỚI trong danh mục này.")
            
    finally:
        driver.quit()

# ---------------------------------------------------------
# GIAI ĐOẠN 2: CÀO SÂU & UPDATE (Chạy tiếp đoạn còn thiếu)
# ---------------------------------------------------------
def phase_2_deep_crawl_resume():
    # Lấy danh sách các sản phẩm có status = 0 (Chưa cào xong)
    cursor.execute("SELECT product_url, product_name FROM products WHERE status = 0")
    pending_items = cursor.fetchall()
    
    if not pending_items:
        print("\n✅ Không còn sản phẩm nào cần cào. Tất cả đã xong!")
        return

    print(f"\n--- BẮT ĐẦU GIAI ĐOẠN 2: CÀO TIẾP {len(pending_items)} SẢN PHẨM ---")
    driver = init_driver()
    
    try:
        for idx, (url, name) in enumerate(pending_items):
            print(f"[{idx+1}/{len(pending_items)}] Đang xử lý: {name[:30]}...")
            try:
                driver.get(url)
                time.sleep(2)

                ram, screen, chip, reviews = "N/A", "N/A", "N/A", 0
                
                # A. Lấy thông số kỹ thuật
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table.technical-content tr")
                    for row in rows:
                        txt = row.text.lower()
                        val = row.find_elements(By.TAG_NAME, "td")[-1].text.strip()
                        if "dung lượng ram" in txt: ram = val
                        elif "kích thước màn hình" in txt: screen = val
                        elif "chipset" in txt or "cpu" in txt: chip = val
                except: pass

                # B. Lấy Review Count
                try:
                    driver.execute_script("window.scrollTo(0, 600);")
                    rev_el = driver.find_element(By.CSS_SELECTOR, "p.boxReview-score__count")
                    reviews = int(re.sub(r"[^\d]", "", rev_el.text))
                except: reviews = 0

                # C. CẬP NHẬT DATABASE (UPDATE thay vì INSERT)
                # Đánh dấu status = 1 (Đã xong)
                cursor.execute("""
                    UPDATE products 
                    SET ram=?, screen=?, chip=?, review_count=?, status=1 
                    WHERE product_url=?
                """, (ram, screen, chip, reviews, url))
                conn.commit()

            except Exception as e:
                print(f"   ❌ Lỗi: {e}. Đánh dấu link này bị lỗi (-1).")
                cursor.execute("UPDATE products SET status=-1 WHERE product_url=?", (url,))
                conn.commit()
                continue

    except KeyboardInterrupt:
        print("\n🛑 Bạn đã dừng chương trình. Lần sau chạy lại sẽ tiếp tục từ đây.")
    finally:
        driver.quit()

# ---------------------------------------------------------
# CHẠY CHƯƠNG TRÌNH
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Chọn chế độ:")
    print("1. Quét tìm sản phẩm mới (Nên chạy lần đầu)")
    print("2. Chạy tiếp phần còn thiếu (Deep Crawl)")
    choice = input("Nhập số (1 hoặc 2): ")

    if choice == '1':
        phase_1_gather_links()
        print("\nĐã lấy xong danh sách. Hãy chạy chọn số 2 để bắt đầu cào chi tiết.")
    elif choice == '2':
        phase_2_deep_crawl_resume()
        
    conn.close()