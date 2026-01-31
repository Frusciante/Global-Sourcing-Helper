import time
import json
import requests
import xml.etree.ElementTree as ET
import google.genai as genai 
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By # [필수] 본문 추출용 추가
from tkinter import messagebox 

from logic.excel_handler import ExcelHandler
from logic.browser_manager import BrowserManager

class SourcingProcessor:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self.is_running = True
        
        # KIPRIS 상표권 캐시
        self.brand_cache = {}
        
        # 1. 엑셀 핸들러
        excel_file = self.config.get('EXCEL_FILE', 'windly-excel-bulk-upload-ver9.xlsx')
        self.excel = ExcelHandler(excel_file, log_callback)
        
        # 2. 브라우저 매니저
        self.browser = BrowserManager(log_callback)

        # 3. AI 설정
        raw_keys = self.config['GEMINI_API_KEY']
        self.api_keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
        self.current_key_idx = 0
        
        # 4. KIPRIS 키 설정
        raw_kipris = self.config['KIPRIS_API_KEY']
        self.kipris_keys = [k.strip() for k in raw_kipris.split(',') if k.strip()]
        self.current_kipris_idx = 0
        
        # 모델 후보군
        self.model_candidates = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash"      
        ]
        self.current_model_idx = 0
        self.client = None

        try:
            self._configure_genai()
        except Exception as e:
            self.log_callback(f"❌ [Error] Gemini 초기 설정 실패: {e}")

    # ... (키 로테이션, AI 호출, KIPRIS 관련 메서드는 기존과 동일하므로 생략하지 않고 유지) ...
    # 코드가 길어지므로, 변경되지 않은 헬퍼 메서드들은 그대로 두었다고 가정하고 
    # 핵심 변경 부분인 콜백과 run 메서드를 중심으로 전체 구조를 잡겠습니다.

    # ==========================
    # [NEW] 공통 키 로테이션 로직
    # ==========================
    def _rotate_index(self, keys, current_idx, service_name):
        if len(keys) <= 1:
            self.log_callback(f"⚠️ [{service_name}] 교체할 여분 키가 없습니다.")
            return current_idx, False
        new_idx = (current_idx + 1) % len(keys)
        self.log_callback(f"🔄 [{service_name}] 키 교체 ({new_idx + 1}/{len(keys)})")
        return new_idx, True

    # ==========================
    # AI 관련 로직 (Gemini)
    # ==========================
    def _configure_genai(self):
        if not self.api_keys: return
        current_key = self.api_keys[self.current_key_idx]
        try:
            self.client = genai.Client(api_key=current_key)
            model_name = self.model_candidates[self.current_model_idx]
            self.log_callback(f"🔑 [AI] 키 설정 ({self.current_key_idx + 1}/{len(self.api_keys)}) | 타겟 모델: {model_name}")
        except Exception as e:
            self.log_callback(f"❌ [AI] 설정 오류: {e}")
            self.client = None

    def _rotate_api_key(self):
        self.current_key_idx, success = self._rotate_index(self.api_keys, self.current_key_idx, "AI")
        if success: self._configure_genai()
        return success
    
    def _switch_model(self):
        if len(self.model_candidates) <= 1: return False
        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_candidates)
        new_model_name = self.model_candidates[self.current_model_idx]
        self.log_callback(f"⚠️ [AI] 모델 한도 초과 예상 -> '{new_model_name}'(으)로 타겟 변경")
        return True

    def _call_gemini_with_retry(self, prompt, context=""):
        total_combinations = len(self.api_keys) * len(self.model_candidates)
        if total_combinations == 0: total_combinations = 1
        attempt_count = 0 

        while attempt_count < total_combinations:
            try:
                if not self.client: self._configure_genai()
                if not self.client: raise Exception("AI Client 객체 생성 실패")

                current_model = self.model_candidates[self.current_model_idx]
                response = self.client.models.generate_content(
                    model=current_model, contents=prompt
                )
                if response and response.text: 
                    return response.text.replace('```json', '').replace('```', '').strip()

            except Exception as e:
                error_msg = str(e).lower()
                attempt_count += 1 
                
                if "429" in error_msg or "quota" in error_msg or "resource" in error_msg or "model" in error_msg:
                    self.log_callback(f"⏳ [AI] {context} 중 오류, AI API 키를 재설정합니다. ({attempt_count}/{total_combinations})...")
                    key_rotated = self._rotate_api_key()
                    if (self.current_key_idx == 0) or (not key_rotated):
                        self.log_callback(f"⚠️ [AI] ({context}) 키 소진. 모델 변경.")
                        self._switch_model()
                    time.sleep(1)
                    continue
                else:
                    self.log_callback(f"⚠️ [AI] {context} 실패: {error_msg}")
                    time.sleep(1)
                    continue

        self.log_callback(f"❌ [Critical] '{context}' 작업 중 모든 수단 실패.")
        self.stop()
        messagebox.showerror("AI 한도 초과", f"'{context}' 작업 실패. 프로그램을 종료합니다.")
        return None

    # ==========================
    # KIPRIS 관련 로직
    # ==========================
    def _rotate_kipris_key(self):
        self.current_kipris_idx, success = self._rotate_index(self.kipris_keys, self.current_kipris_idx, "KIPRIS")
        return success

    def check_trademark(self, brand):
        if not brand or str(brand).upper() in ["NULL", "NONE", "N/A"]: return True
        brand_key = str(brand).strip().upper()

        if brand_key in self.brand_cache: return self.brand_cache[brand_key]
        if not self.kipris_keys: return True 

        api_url = "https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getWordSearch"
        max_retries = max(1, len(self.kipris_keys))
        
        for attempt in range(max_retries):
            current_key = self.kipris_keys[self.current_kipris_idx]
            params = {'searchString': brand, 'ServiceKey': current_key}
            
            try:
                res = requests.get(api_url, params=params, timeout=5)
                if res.status_code != 200:
                    self.log_callback(f"⚠️ [KIPRIS] 서버 오류({res.status_code}). 키 교체...")
                    if self._rotate_kipris_key(): continue
                    return True 
                
                root = ET.fromstring(res.content)
                error_info = root.find(".//errMsg")
                if error_info is not None and error_info.text:
                    self.log_callback(f"⚠️ [KIPRIS] API 에러. 키 교체...")
                    if self._rotate_kipris_key(): continue
                    return True

                count_tag = root.find(".//totalCount")
                if count_tag is None: return True
                
                count = int(count_tag.text)
                if count > 0:
                    self.log_callback(f"   ❌ [KIPRIS] 상표권 발견! '{brand}' ({count}건)")
                    self.brand_cache[brand_key] = False
                    return False
                
                self.brand_cache[brand_key] = True
                return True

            except Exception as e:
                self.log_callback(f"⚠️ [KIPRIS] 조회 실패. 재시도...")
                if self._rotate_kipris_key(): continue
                return True
        return True

    # ==========================
    # 분석 및 데이터 처리 로직
    # ==========================
    def analyze_category_with_ai(self, product_title):
        prompt = (
            f"Role: E-commerce Category Classifier\n"
            f"Task: Classify the product '{product_title}' into a Korean e-commerce category path (Coupang/Naver style).\n"
            f"Format: BigCategory > MiddleCategory > SmallCategory\n"
            f"Input: {product_title}\n"
            f"Output:"
        )
        path_hint = self._call_gemini_with_retry(prompt, "개별 카테고리 분석")
        if path_hint:
            lines = path_hint.split('\n')
            for line in lines:
                if '>' in line: return line.strip()
            return lines[0].strip()
        return ""
    
    def extract_full_info(self, p_name, detail_text=""):
        prompt = (
            f"Role: Product Data Extractor\n"
            f"Input Title: '{p_name}'\n"
            f"Input Detail Context (Truncated): '{detail_text[:2000]}'\n\n"
            f"Task: Extract detailed info using BOTH Title and Context. Then translate Title to Korean.\n"
            f"Output JSON: {{ \"is_valid\": true, \"productTitle\": \"...\", \"manufacturer\": \"...\", \"brand\": \"...\", \"model\": \"...\", \"keywords\": [] }}"
        )
        res = self._call_gemini_with_retry(prompt, "정보추출")
        if res:
            try:
                clean_json = res.replace('```json', '').replace('```', '').strip()
                if not clean_json.startswith('{'):
                    start = clean_json.find('{'); end = clean_json.rfind('}') + 1
                    if start != -1 and end != -1: clean_json = clean_json[start:end]
                data = json.loads(clean_json)
                return data
            except: return None
        return None

    def detect_and_translate(self, url, keyword):
        try:
            target_lang = None
            if any(site in url for site in ['taobao', 'tmall', '1688']): target_lang = "Simplified Chinese"
            elif any(site in url for site in ['rakuten', 'yahoo']): target_lang = "Japanese"
            elif any(site in url for site in ['amazon', 'ebay']): target_lang = "English"

            if target_lang:
                trans_prompt = (
                    f"Role: Translator\nTask: Translate '{keyword}' into {target_lang}.\n"
                    f"Output ONLY the word."
                )
                translated = self._call_gemini_with_retry(trans_prompt, "번역")
                if translated: 
                    translated = translated.replace('"', '').replace("'", "").replace(".", "").strip()
                    self.log_callback(f"   ㄴ 번역: '{keyword}' -> '{translated}'")
                    return translated
            return keyword
        except: return keyword

    # ==========================
    # [NEW] 상세 페이지 처리 콜백
    # ==========================
    def _process_product_callback(self, driver, product_name):
        """
        BrowserManager가 상세 페이지에 진입했을 때 호출되는 콜백 함수
        여기서 텍스트 추출 -> AI 분석 -> KIPRIS -> 엑셀 저장을 수행함
        """
        try:
            # 1. 상세 페이지 본문 텍스트 추출
            try:
                # body 태그의 텍스트를 가져옴 (최대 3000자)
                detail_text = driver.find_element(By.TAG_NAME, "body").text[:3000]
            except:
                detail_text = ""

            # 2. AI 정보 추출
            info = self.extract_full_info(product_name, detail_text)
            
            if info is None or not info.get('is_valid', True):
                self.log_callback(f"   🗑️ [Skip] 유효하지 않은 상품")
                return False

            # 3. KIPRIS 상표권 확인
            if not self.check_trademark(info.get('brand', '')):
                return False # 상표권 이슈로 저장 안 함

            # 4. 카테고리 분석
            cat_hint = self.analyze_category_with_ai(info['productTitle'])
            
            # 5. 엑셀 매칭 및 저장
            best_cp = self.excel.find_best_category(cat_hint, 'coupang')
            best_nv = self.excel.find_best_category(cat_hint, 'naver')
            
            self.log_callback(f"     ㄴ 카테고리: {best_cp.split('>')[-1]} / {best_nv.split('>')[-1]}")

            self.excel.save_product({
                'cp_cat': best_cp, 
                'nv_cat': best_nv,
                'title': info['productTitle'], 
                'tags': info['keywords'],
                'url': driver.current_url, # 현재 상세페이지 URL
                'manufacturer': info.get('manufacturer', ''),
                'brand': info.get('brand', ''), 
                'model': info.get('model', '')
            })
            
            return True # 저장 성공

        except Exception as e:
            self.log_callback(f"   ⚠️ [Process Error] 분석 중 오류: {e}")
            return False

    def stop(self):
        self.is_running = False
        self.log_callback("🛑 [Stop] 중지 요청됨")

    def run(self):
        keywords = [k.strip() for k in self.config['TARGET_ITEMS'].split(",") if k.strip()]
        urls = [u.strip() for u in self.config['SHOP_URLS'].split(",") if u.strip()]
        max_count = int(self.config.get('ITEM_COUNT', 10))
        
        self.browser.start_driver()
        try:
            for shop_url in urls:
                if not self.is_running: break
                self.log_callback(f"\n\n🌐 [Shop] 쇼핑몰 이동 및 작업 시작: {shop_url}")
                
                for kw in keywords:
                    if not self.is_running: break
                    
                    self.brand_cache = {} 
                    self.log_callback(f"\n 📍 [Keyword] 키워드 검색 시작: '{kw}'")

                    try:
                        # 1. 언어 감지 및 번역
                        t_kw = self.detect_and_translate(shop_url, kw)
                        if len(t_kw) > 50: t_kw = kw 

                        # 2. [통합 실행] 수집 + 분석 + 저장
                        # process_callback에 우리가 만든 함수를 넘겨줍니다.
                        collected = self.browser.search_and_collect(
                            url=shop_url, 
                            keyword=t_kw, 
                            count=max_count, 
                            is_running_check=lambda: self.is_running,
                            process_callback=self._process_product_callback  # <--- [핵심 연결]
                        )
                        
                        self.log_callback(f"   🏁 '{kw}' 수집 종료 (총 {collected}개 저장됨)")
                        time.sleep(2)

                    except WebDriverException:
                        self.log_callback("🚨 브라우저 오류. 재시작...")
                        self.browser.close(); self.browser.start_driver()
                    except Exception as e:
                        self.log_callback(f"⚠️ [Loop Error] {e}")
        finally:
            self.browser.close()
            self.log_callback("\n🏁 [Finish] 작업 종료")