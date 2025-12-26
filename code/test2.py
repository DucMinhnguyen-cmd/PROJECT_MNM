import time
import re
import json
import logging
import sys
import os
from datetime import datetime

# Cài đặt thư viện: pip install pymongo selenium webdriver-manager
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================
# CẤU HÌNH HỆ THỐNG
# =====================================================
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Kết nối MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["CellphoneS_Project"]
collection = db["products_final"]
collection.create_index("product_url", unique=True) # Đảm bảo không lưu trùng

# Tên file lưu danh sách Link (Bộ nhớ đệm)
LINK_FILE = "all_product_links.txt"

# =====================================================
# CÁC HÀM XỬ LÝ DỮ LIỆU
# =====================================================
def clean_number(text):
    """Chuyển đổi '31.190.000đ' -> 31190000"""
    if not text: return 0
    clean = re.sub(r"[^\d]", "", str(text))
    return int(clean) if clean else 0

def detect_brand(name):
    """Tự động nhận diện thương hiệu"""
    name = name.lower()
    brands = {
        'iphone': 'Apple', 'ipad': 'Apple', 'macbook': 'Apple', 'apple': 'Apple',
        'samsung': 'Samsung', 'galaxy': 'Samsung',
        'xiaomi': 'Xiaomi', 'redmi': 'Xiaomi', 'poco': 'Xiaomi',
        'oppo': 'OPPO', 'realme': 'Realme', 'vivo': 'Vivo',
        'asus': 'ASUS', 'rog': 'ASUS', 'tuf': 'ASUS',
        'acer': 'Acer', 'nitro': 'Acer', 'aspire': 'Acer',
        'dell': 'Dell', 'hp': 'HP', 'lenovo': 'Lenovo', 'thinkpad': 'Lenovo',
        'msi': 'MSI', 'sony': 'Sony', 'lg': 'LG',
        'huawei': 'Huawei', 'honor': 'Honor', 'nokia': 'Nokia',
        'garmin': 'Garmin', 'amazfit': 'Amazfit', 'jbl': 'JBL', 'marshall': 'Marshall'
    }
    for k, v in brands.items():
        if k in name: return v
    return "Khac"

def setup_driver():
    """Khởi tạo trình duyệt (ĐÃ SỬA LỖI BẢO MẬT)"""
    opts = ChromeOptions()
    opts.add_argument("--window-size=1200,800")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--log-level=3")
    
    # --- THÊM 3 DÒNG NÀY ĐỂ KHÔNG BỊ CHROME CHẶN ---
    opts.add_argument('--ignore-certificate-errors')
    opts.add_argument('--ignore-ssl-errors')
    opts.add_argument('--allow-insecure-localhost')
    # -----------------------------------------------
    
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)

# =====================================================
# GIAI ĐOẠN 1: THU THẬP LINK (CHẠY 1 LẦN)
# =====================================================
def fetch_and_save_links():
    """Chỉ đi quét Link và lưu vào file txt"""
    if os.path.exists(LINK_FILE) and os.path.getsize(LINK_FILE) > 0:
        print(f"✅ Đã tìm thấy file '{LINK_FILE}' chứa link.")
        choice = input("Bạn có muốn dùng tiếp file này không? (y/n): ").lower()
        if choice == 'y': return

    print("🚀 GIAI ĐOẠN 1: Đang đi thu thập Link...")
    driver = setup_driver()
    
    # Danh sách các trang cần quét
    targets = [
        {"url": "https://cellphones.com.vn/mobile.html", "cat": "Smartphone", "type": "Moi"},
        {"url": "https://cellphones.com.vn/laptop.html", "cat": "Laptop", "type": "Moi"},
        {"url": "https://cellphones.com.vn/tablet.html", "cat": "Tablet", "type": "Moi"},
        {"url": "https://cellphones.com.vn/dong-ho-thong-minh.html", "cat": "Smartwatch", "type": "Moi"},
        {"url": "https://cellphones.com.vn/thiet-bi-am-thanh/tai-nghe.html", "cat": "Tai nghe", "type": "Phu kien"},
        {"url": "https://cellphones.com.vn/hang-cu/dien-thoai.html", "cat": "Smartphone", "type": "Cu"},
        {"url": "https://cellphones.com.vn/hang-cu/laptop.html", "cat": "Laptop", "type": "Cu"},
    ]

    all_links = []
    try:
        for target in targets:
            print(f"   [*] Đang quét danh mục: {target['cat']} ({target['type']})...")
            driver.get(target['url'])
            time.sleep(3)
            
            # Cuộn trang (Tăng range lên nếu muốn lấy nhiều hơn)
            for i in range(40): 
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1)
                    btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-show-more")))
                    driver.execute_script("arguments[0].click();", btn)
                except: break 
            
            # Lấy Link
            elems = driver.find_elements(By.CSS_SELECTOR, ".product-item a")
            count = 0
            for e in elems:
                href = e.get_attribute("href")
                if href and "cellphones.com.vn" in href and ".html" in href:
                    # Lưu định dạng: URL|Category|Type
                    entry = f"{href}|{target['cat']}|{target['type']}"
                    if entry not in all_links:
                        all_links.append(entry)
                        count += 1
            print(f"      -> Tìm thấy {count} sản phẩm.")

        # Lưu xuống file
        with open(LINK_FILE, "w", encoding="utf-8") as f:
            for line in all_links:
                f.write(line + "\n")
        print(f"✅ ĐÃ LƯU {len(all_links)} LINK VÀO FILE '{LINK_FILE}'")
        
    finally:
        driver.quit()

# =====================================================
# GIAI ĐOẠN 2: CÀO CHI TIẾT (CHẠY NHIỀU LẦN)
# =====================================================
def crawl_details_from_file():
    print("🚀 GIAI ĐOẠN 2: Bắt đầu cào chi tiết từ file...")
    
    with open(LINK_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    
    driver = setup_driver()
    total = len(lines)
    
    try:
        for i, line in enumerate(lines):
            # Tách thông tin
            parts = line.split("|")
            link, cat, typ = parts[0], parts[1], parts[2]
            
            # --- 1. KIỂM TRA DB (SKIP NẾU ĐÃ CÓ) ---
            if collection.find_one({"product_url": link}):
                print(f"   [SKIP] {i+1}/{total} - Đã có trong DB", end='\r')
                continue
            
            # --- 2. CÀO CHI TIẾT ---
            product = crawl_product_logic(driver, link, cat, typ)
            
            if product:
                try:
                    collection.insert_one(product)
                    print(f"   [OK] {i+1}/{total} | {product['price_sale']:,}đ | {product['product_name'][:30]}...")
                except Exception as e:
                    print(f"   [ERR] Lỗi lưu DB: {e}")
            else:
                # Nếu lỗi mạng hoặc link chết
                print(f"   [FAIL] {i+1}/{total} - Không lấy được dữ liệu")

    except KeyboardInterrupt:
        print("\n[!] Tạm dừng. Bạn có thể chạy lại code để tiếp tục!")
    finally:
        driver.quit()
        client.close()

# Hàm Logic Cào 1 Sản Phẩm (Đã Fix Giá & Specs)
def crawl_product_logic(driver, link, category, type_prod):
    try:
        driver.get(link)
        # time.sleep(0.5) # Bật nếu mạng chậm

        # 1. Tên
        try:
            name = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except: return None

        # 2. Giá (Ưu tiên JSON-LD -> CSS Mới -> CSS Cũ)
        price_sale = 0; price_orig = 0
        
        # A. JSON-LD
        try:
            scripts = driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
            for script in scripts:
                data = json.loads(script.get_attribute("innerHTML"))
                if isinstance(data, list): data = data[0]
                if data.get("@type") == "Product" and "offers" in data:
                    offer = data["offers"][0] if isinstance(data["offers"], list) else data["offers"]
                    price_sale = clean_number(offer.get("price", 0))
                    if price_sale > 0: break
        except: pass

        # B. CSS Selector (Fix theo HTML mới)
        if price_sale == 0:
            try:
                # Tìm đúng khối chứa giá (tránh khối thu cũ đổi mới)
                box = driver.find_element(By.CSS_SELECTOR, ".box-product-price .smember-price-label")
                price_sale = clean_number(box.find_element(By.CSS_SELECTOR, ".sale-price").text)
                try:
                    price_orig = clean_number(box.find_element(By.CSS_SELECTOR, ".base-price").text)
                except: pass
            except:
                # Fallback class cũ
                for sel in [".tpt---sale-price", ".product__price--show", ".special-price"]:
                    try:
                        val = clean_number(driver.find_element(By.CSS_SELECTOR, sel).text)
                        if val > 0: price_sale = val; break
                    except: continue

        # Chống giá ảo cho điện thoại/laptop (<1tr là sai)
        if category in ["Smartphone", "Laptop", "Tablet"] and price_sale < 1000000:
            price_sale = 0 

        if price_orig == 0: price_orig = price_sale

        # Tính % giảm
        discount = "0%"
        if price_orig > price_sale and price_sale > 0:
            pct = int(((price_orig - price_sale)/price_orig)*100)
            discount = f"-{pct}%"

        # 3. Rating
        rating_count = 0
        try:
            rating_count = clean_number(driver.find_element(By.CSS_SELECTOR, ".total-rating").text)
        except: pass

        # 4. Thông số kỹ thuật (Bảng + List)
        specs = {}
        try:
            # Click xem thêm
            try:
                btn = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".button__show-modal-technical, .btn-detail-specs")))
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
            except: pass
            
            # Quét Bảng (tr/td)
            rows = driver.find_elements(By.CSS_SELECTOR, ".technical-content-item, .technical-content tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    specs[cols[0].text.strip().replace(".", "")] = cols[1].text.strip()
            
            # Quét List (li) - Dự phòng
            if not specs:
                items = driver.find_elements(By.CSS_SELECTOR, ".technical-content li, .box-kithuat li")
                for item in items:
                    if ":" in item.text:
                        p = item.text.split(":", 1)
                        specs[p[0].strip().replace(".", "")] = p[1].strip()
        except: pass

        return {
            "product_url": link, "product_name": name, "brand": detect_brand(name),
            "category": category, "type": type_prod, 
            "price_sale": price_sale, "price_original": price_orig, "discount_rate": discount,
            "rating_count": rating_count, "specs": specs, 
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except: return None

# =====================================================
# CHẠY CHƯƠNG TRÌNH
# =====================================================
if __name__ == "__main__":
    # Bước 1: Lấy link (Nếu chưa có file link)
    fetch_and_save_links()
    
    # Bước 2: Cào chi tiết (Tự động bỏ qua cái đã có)
    crawl_details_from_file()