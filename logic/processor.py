import os
import time
import json
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import openpyxl

# API 및 브라우저 제어
from google import genai
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class SourcingProcessor:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self.is_running = True
        
        # config.ini에서 엑셀 파일명 가져오기
        self.target_file = self.config.get('EXCEL_FILE', 'windly-excel-bulk-upload-ver9.xlsx')
        
        # 1. 엑셀 시트에서 카테고리 데이터 로드
        self.load_categories_from_excel()

        try:
            self.client = genai.Client(api_key=self.config['GEMINI_API_KEY'])
            self.model_name = "gemini-1.5-flash"
        except Exception as e:
            self.log_callback(f"❌ Gemini 설정 실패: {e}")

    def load_categories_from_excel(self):
        """설정된 엑셀 파일의 시트들을 직접 읽어 카테고리 DB 구축"""
        try:
            if not os.path.exists(self.target_file):
                self.log_callback(f"⚠️ '{self.target_file}' 파일이 존재하지 않습니다. 경로를 확인해주세요.")
                return

            self.log_callback(f"📊 {self.target_file} 에서 카테고리 시트 읽는 중...")
            # 시트명은 양식의 고유 이름이므로 유지하되, 파일명만 변수로 처리
            self.coupang_cat = pd.read_excel(self.target_file, sheet_name='쿠팡 전체 카테고리 (240517)')
            self.naver_cat = pd.read_excel(self.target_file, sheet_name='네이버 전체 카테고리 (251215)')
            self.log_callback("✅ 카테고리 데이터 로드 완료")
        except Exception as e:
            self.log_callback(f"❌ 카테고리 로드 에러: {e}")
            self.coupang_cat = None
            self.naver_cat = None

    def find_best_category(self, hint, platform='coupang'):
        """AI 힌트를 기반으로 엑셀 내 전체 경로 매칭"""
        df = self.coupang_cat if platform == 'coupang' else self.naver_cat
        if df is None: return ""
        
        target_col = '여기서 카테고리를 복사해주세요'
        keywords = hint.replace('>', ' ').split()
        
        for kw in reversed(keywords):
            if len(kw.strip()) < 2: continue
            match = df[df[target_col].str.contains(kw, na=False, case=False)]
            if not match.empty:
                return match.iloc[0][target_col]
        return ""

    def append_to_excel(self, data_row):
        """지정된 엑셀 파일의 수집 양식 시트에 데이터 추가"""
        try:
            wb = openpyxl.load_workbook(self.target_file)
            ws = wb['엑셀 수집 양식 (Ver.9)']
            
            start_row = 6
            while ws.cell(row=start_row, column=1).value is not None:
                start_row += 1
            
            # 셀 값 입력
            ws.cell(row=start_row, column=1, value=start_row - 5)
            ws.cell(row=start_row, column=2, value=data_row['cp_cat'])
            ws.cell(row=start_row, column=3, value=data_row['nv_cat'])
            ws.cell(row=start_row, column=4, value=data_row['title'])
            ws.cell(row=start_row, column=5, value=data_row['tags'])
            ws.cell(row=start_row, column=6, value=data_row['url'])
            ws.cell(row=start_row, column=7, value=0)
            ws.cell(row=start_row, column=8, value='무료')
            ws.cell(row=start_row, column=9, value=0)
            ws.cell(row=start_row, column=10, value=5000)
            ws.cell(row=start_row, column=11, value=10000)
            ws.cell(row=start_row, column=12, value=data_row['manufacturer'])
            ws.cell(row=start_row, column=13, value=data_row['brand'])
            ws.cell(row=start_row, column=14, value=data_row['model'])
            
            wb.save(self.target_file)
            self.log_callback(f"   ㄴ 엑셀 기록 완료 ({self.target_file})")
        except Exception as e:
            self.log_callback(f"❌ 엑셀 기록 에러: {e}")

    def init_driver(self):
        chrome_options = Options()
        user_data_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def detect_and_translate(self, html_source, keyword):
        try:
            prompt = f"다음 HTML 소스를 보고 이 쇼핑몰 언어 코드(예: zh-CN)만 한 단어로 답해.\n{html_source[:800]}"
            lang_code = self.client.models.generate_content(model=self.model_name, contents=prompt).text.strip().lower()
            
            target = "중국어 간체" if 'zh' in lang_code else "영어" if 'en' in lang_code else None
            if not target: return keyword

            trans_prompt = f"'{keyword}'를 {target} 쇼핑 검색어로 번역해줘. 결과만 출력."
            translated = self.client.models.generate_content(model=self.model_name, contents=trans_prompt).text.strip()
            return translated
        except: return keyword

    def get_shopping_products(self, driver, url, keyword, count):
        try:
            self.log_callback(f"🌐 {url}에서 '{keyword}' 검색 중...")
            driver.get(url)
            time.sleep(2)

            search_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#q, input[type='search']"))
            )
            search_input.clear()
            search_input.send_keys(keyword)
            search_input.send_keys(Keys.ENTER)
            
            time.sleep(7) 

            selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name"]
            products = []
            
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    products = [(el.text.strip(), driver.current_url) for el in elements if el.text.strip()]
                    if len(products) >= 3: break
            
            return products[:count]
        except Exception as e:
            self.log_callback(f"⚠️ 검색 오류: {e}")
            return []

    def extract_full_info(self, p_name):
        try:
            prompt = (
                f"상품명: {p_name}\n이 상품에서 정보를 추출해 JSON으로 응답해.\n"
                f"productTitle(깔끔한 한글명), manufacturer(제조사), brand(브랜드), model(모델명), "
                f"keywords(태그 5개 쉼표구분), category_hint(분류 경로, 예: 가구>의자>사무용의자)\n"
                f"JSON 형식으로만 답변."
            )
            response = self.client.models.generate_content(model=self.model_name, contents=prompt)
            clean_json = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_json)
        except: return None

    def check_trademark(self, brand):
        if not brand or brand == "None": return True
        api_url = "https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getWordSearch"
        params = {'searchString': brand, 'ServiceKey': self.config['KIPRIS_API_KEY']}
        try:
            res = requests.get(api_url, params=params, timeout=10)
            root = ET.fromstring(res.content)
            count = root.find(".//totalCount")
            return int(count.text) == 0 if count is not None else True
        except: return True

    def run(self):
        keywords = [k.strip() for k in self.config['TARGET_ITEMS'].split(",") if k.strip()]
        urls = [u.strip() for u in self.config['SHOP_URLS'].split(",") if u.strip()]
        max_count = int(self.config.get('ITEM_COUNT', 10))
        
        driver = self.init_driver()
        
        try:
            for kw in keywords:
                if not self.is_running: break
                driver.get(urls[0])
                time.sleep(2)
                t_kw = self.detect_and_translate(driver.page_source, kw)
                
                product_list = self.get_shopping_products(driver, urls[0], t_kw, max_count)
                
                for p_name, p_url in product_list:
                    if not self.is_running: break
                    self.log_callback(f"🔎 분석: {p_name[:20]}...")
                    
                    info = self.extract_full_info(p_name)
                    if info:
                        if self.check_trademark(info['brand']):
                            cp_cat = self.find_best_category(info['category_hint'], 'coupang')
                            nv_cat = self.find_best_category(info['category_hint'], 'naver')
                            
                            self.append_to_excel({
                                'cp_cat': cp_cat, 'nv_cat': nv_cat,
                                'title': info['productTitle'], 'tags': info['keywords'],
                                'url': p_url, 'manufacturer': info['manufacturer'],
                                'brand': info['brand'], 'model': info['model']
                            })
                        else:
                            self.log_callback(f"   ㄴ ❌ 상표권 위험({info['brand']}) 제외")
                    
                    time.sleep(4)
        finally:
            driver.quit()
            self.log_callback("🏁 모든 작업이 종료되었습니다.")

    def stop(self):
        self.is_running = False