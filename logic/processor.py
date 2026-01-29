import os
import time
import json
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import openpyxl
from tkinter import messagebox

# [중요] 표준 라이브러리 임포트
import google.generativeai as genai 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

class SourcingProcessor:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self.is_running = True
        self.target_file = self.config.get('EXCEL_FILE', 'windly-excel-bulk-upload-ver9.xlsx')
        
        self.model_candidates = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash"
        ]
        self.current_model_idx = 0
        self.model = None # 초기화
        
        self.load_categories_from_excel()

        # [수정] 표준 인증 방식 (configure)
        try:
            genai.configure(api_key=self.config['GEMINI_API_KEY'])
            self._set_model()
        except Exception as e:
            self.log_callback(f"❌ Gemini 설정 실패: {e}")

    def _set_model(self):
        """현재 인덱스의 모델로 설정"""
        model_name = self.model_candidates[self.current_model_idx]
        self.log_callback(f"🤖 AI 모델 설정: {model_name}")
        self.model = genai.GenerativeModel(model_name)

    def _switch_model(self):
        """다음 모델로 교체"""
        self.current_model_idx += 1
        if self.current_model_idx < len(self.model_candidates):
            self._set_model()
            return True
        return False

    def _call_gemini_with_retry(self, prompt, context=""):
        """안정적인 재시도 로직"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # [핵심] 표준 호출 방식
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    return response.text.strip()
                else:
                    raise Exception("빈 응답")
            
            except Exception as e:
                error_msg = str(e).lower()
                
                # 1. 429: 너무 많이 요청함 -> 대기
                if "429" in error_msg or "resource" in error_msg:
                    self.log_callback(f"⏳ 사용량 초과. 10초 대기... ({attempt+1}/{max_retries})")
                    time.sleep(10)
                    continue
                
                # 2. 404/Invalid: 모델 문제 -> 모델 교체
                elif "404" in error_msg or "not found" in error_msg or "supported" in error_msg:
                    self.log_callback(f"⚠️ 모델 호환성 문제({self.model_candidates[self.current_model_idx]}). 다음 모델로 변경...")
                    if self._switch_model():
                        time.sleep(2)
                        continue
                    else:
                        self.log_callback("❌ 모든 AI 모델이 실패했습니다.")
                        return None
                
                # 3. 기타 에러
                else:
                    self.log_callback(f"⚠️ AI 오류({context}): {error_msg}")
                    return None
        return None

    def load_categories_from_excel(self):
        try:
            if not os.path.exists(self.target_file):
                self.log_callback(f"⚠️ '{self.target_file}' 파일이 없습니다.")
                return
            self.coupang_cat = pd.read_excel(self.target_file, sheet_name='쿠팡 전체 카테고리 (240517)')
            self.naver_cat = pd.read_excel(self.target_file, sheet_name='네이버 전체 카테고리 (251215)')
            self.log_callback("✅ 카테고리 로드 완료")
        except Exception as e:
            self.log_callback(f"❌ 카테고리 로드 에러: {e}")
            self.coupang_cat = None
            self.naver_cat = None

    def find_best_category(self, hint, platform='coupang'):
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
        try:
            wb = openpyxl.load_workbook(self.target_file)
            ws = wb['엑셀 수집 양식 (Ver.9)']
            start_row = 6
            while ws.cell(row=start_row, column=1).value is not None:
                start_row += 1
            
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
            self.log_callback(f"   ㄴ 엑셀 저장 완료: {data_row['title'][:10]}...")
        except Exception as e:
            self.log_callback(f"❌ 엑셀 기록 에러: {e}")

    def init_driver(self):
        chrome_options = Options()
        curr_folder = os.getcwd()
        profile_path = os.path.join(curr_folder, "chrome_profile")
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            self.log_callback(f"❌ 브라우저 실행 실패: {e}")
            raise e

    def detect_and_translate(self, url, html_source, keyword):
        """URL 및 HTML 기반 언어 감지 및 번역"""
        try:
            target_lang = None
            if any(site in url for site in ['taobao', 'tmall', '1688', 'jd.com', 'baidu']):
                target_lang = "중국어 간체(Simplified Chinese)"
            elif any(site in url for site in ['rakuten', 'yahoo.co.jp', 'zozo']):
                target_lang = "일본어"
            elif any(site in url for site in ['amazon', 'ebay', 'walmart', 'aliexpress']):
                target_lang = "영어"

            if not target_lang:
                prompt = f"다음 HTML 소스를 분석해서 '주요 언어' 하나만 말해(영어, 중국어, 일본어, 한국어 중 1).\nSource: {html_source[:500]}"
                detected = self._call_gemini_with_retry(prompt, "언어 감지")
                if detected:
                    if "중국" in detected: target_lang = "중국어 간체"
                    elif "일본" in detected: target_lang = "일본어"
                    elif "영" in detected: target_lang = "영어"
            
            if target_lang:
                self.log_callback(f"🌐 타겟 언어: {target_lang} (번역 시도)")
                trans_prompt = f"쇼핑 검색어 '{keyword}'를 '{target_lang}'로 번역해줘. 설명 없이 번역된 단어만 출력해."
                
                translated = self._call_gemini_with_retry(trans_prompt, "키워드 번역")
                
                if translated:
                    self.log_callback(f"   ㄴ 번역 결과: {keyword} ➔ {translated}")
                    return translated
                else:
                    self.log_callback("⚠️ 번역 실패 (AI 응답 없음), 원본 사용")
                    return keyword
            else:
                return keyword

        except Exception as e:
            self.log_callback(f"⚠️ 번역 로직 에러: {e}")
            return keyword

    def get_shopping_products(self, driver, url, keyword, count):
        while self.is_running:
            try:
                self.log_callback(f"🔍 '{keyword}' 검색 시작...")
                driver.get(url)
                time.sleep(3)

                search_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input#q, input[type='search'], input[name='q'], input[id*='search']"))
                )
                search_input.clear()
                search_input.send_keys(keyword)
                search_input.send_keys(Keys.ENTER)
                
                time.sleep(5) 

                selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name", "a[id*='item-title']", "h1", "h2", "h3"]
                products = []
                
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    valid_elements = [el for el in elements if len(el.text.strip()) > 5]
                    if valid_elements:
                        products = [(el.text.strip(), driver.current_url) for el in valid_elements]
                        if len(products) >= 3: break
                
                if not products:
                    raise Exception("검색 결과 0개")

                return products[:count]

            except WebDriverException as we:
                self.log_callback(f"🚨 브라우저 연결 끊김! 재시작합니다... ({we})")
                raise we

            except Exception as e:
                self.log_callback(f"⚠️ 검색 중단: {e}")
                is_retry = messagebox.askretrycancel(
                    "수동 개입 필요", 
                    f"상품을 찾을 수 없습니다.\n사이트({url})에서 인증(로그인/슬라이드)이 떴는지 확인해주세요.\n\n해결 후 [재시도]를 누르면 진행합니다."
                )
                if not is_retry: return []
                self.log_callback("🔄 재시도 중...")
                continue

    def extract_full_info(self, p_name):
        prompt = (
            f"상품명: {p_name}\n정보 추출 후 JSON 응답:\n"
            f"productTitle(깔끔한 한글명), manufacturer(제조사), brand(브랜드), model(모델명), "
            f"keywords(태그 5개), category_hint(분류 경로)\nJSON 형식만 출력."
        )
        result_text = self._call_gemini_with_retry(prompt, "상세 정보 추출")
        
        if result_text:
            try:
                clean_json = result_text.replace('```json', '').replace('```', '').strip()
                return json.loads(clean_json)
            except:
                return None
        return None

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
        raw_urls = self.config['SHOP_URLS'].split(",")
        urls = [u.strip() for u in raw_urls if u.strip()]
        
        max_count = int(self.config.get('ITEM_COUNT', 10))
        driver = self.init_driver()
        
        try:
            for kw in keywords:
                if not self.is_running: break
                self.log_callback(f"=== 키워드 분석 시작: {kw} ===")
                
                for shop_url in urls:
                    if not self.is_running: break
                    
                    try:
                        if len(driver.window_handles) == 0: raise WebDriverException("Window closed")
                    except:
                        self.log_callback("♻️ 브라우저가 닫혀있어 재시작합니다.")
                        try: driver.quit() 
                        except: pass
                        driver = self.init_driver()

                    self.log_callback(f"🌐 사이트 이동: {shop_url}")
                    
                    try:
                        driver.get(shop_url)
                        time.sleep(3)
                        
                        t_kw = self.detect_and_translate(shop_url, driver.page_source, kw)
                        product_list = self.get_shopping_products(driver, shop_url, t_kw, max_count)
                        
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
                            
                            time.sleep(2)
                    except WebDriverException:
                        self.log_callback("🚨 작업 중 브라우저 오류 발생! 재시작합니다.")
                        try: driver.quit()
                        except: pass
                        driver = self.init_driver()
                        continue

        finally:
            try: driver.quit()
            except: pass
            self.log_callback("🏁 모든 작업이 종료되었습니다.")

    def stop(self):
        self.is_running = False