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
# ... (Phần khởi tạo target và driver giữ nguyên) ...

try:
    for target in targets:
        print(f"🚀 Đang quét: {target['cat']}")
        driver.get(target['url'])
        time.sleep(5)

        # 1. Nhấn "Xem thêm" để bung dữ liệu (range(20) để thử nghiệm nhanh, tăng lên nếu muốn lấy nhiều)
        for _ in range(20):
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "a.btn-show-more")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
            except: break

        # 2. Lấy danh sách link sản phẩm từ trang danh sách
        # Dùng container bao ngoài cùng để lấy thông tin chuẩn
        items = driver.find_elements(By.CLASS_NAME, "product-info-container")
        print(f"  - Tìm thấy {len(items)} sản phẩm. Bắt đầu cào sâu...")

        # Lưu danh sách tạm để tránh lỗi stale element khi chuyển tab
        temp_list = []
        for p in items:
            try:
                name = p.find_element(By.TAG_NAME, "h3").text.strip()
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")
                price_text = p.find_element(By.CLASS_NAME, "product__price--show").text
                price = int(re.sub(r"[^\d]", "", price_text))
                temp_list.append({"name": name, "link": link, "price": price})
            except: continue

        # 3. Truy cập từng link để lấy RAM, Screen, Chip
        for item in temp_list:
            try:
                # Mở link trong tab mới
                driver.execute_script("window.open(arguments[0], '_blank');", item['link'])
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2.5) # Chờ load bảng thông số

                ram, screen, chip = "N/A", "N/A", "N/A"
                # Lấy dữ liệu từ bảng technical-content
                try:
                    rows = driver.find_elements(By.CSS_SELECTOR, "table.technical-content tr")
                    for row in rows:
                        row_text = row.text.lower()
                        # Lấy giá trị ở ô td thứ 2
                        val = row.find_elements(By.TAG_NAME, "td")[-1].text.strip()
                        
                        if "dung lượng ram" in row_text: ram = val
                        elif "kích thước màn hình" in row_text: screen = val
                        elif "chipset" in row_text: chip = val
                except: pass

                # Đóng tab chi tiết và quay về trang chính
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                # Lưu vào DB
                cursor.execute("""
                    INSERT OR IGNORE INTO products (product_url, brand, product_name, category, price, ram, screen, chip)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (item['link'], detect_brand(item['name']), item['name'], target['cat'], item['price'], ram, screen, chip))
                conn.commit()
                print(f"    ✔ Đã lưu: {item['name'][:30]}...")

            except Exception as e:
                # Đảm bảo luôn quay về tab chính nếu có lỗi
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                continue

finally:
    driver.quit()
    conn.close()
    print("✅ Hoàn thành! Bạn hãy mở SQLiteStudio để xem kết quả.")

# 6. THỐNG KÊ KẾT QUẢ
print("\n" + "="*50)
print(pd.read_sql_query("SELECT brand, COUNT(*) as SL, ROUND(AVG(rating_score), 2) as 'Sao_TB' FROM products GROUP BY brand HAVING SL > 5 ORDER BY SL DESC", conn))
conn.close()