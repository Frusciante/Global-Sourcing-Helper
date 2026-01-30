import time
import json
import requests
import xml.etree.ElementTree as ET
import google.genai as genai 
from selenium.common.exceptions import WebDriverException
from tkinter import messagebox # [필수] 에러 팝업용 추가

# 분리된 모듈 임포트
from logic.excel_handler import ExcelHandler
from logic.browser_manager import BrowserManager

class SourcingProcessor:
    def __init__(self, config, log_callback):
        self.config = config
        self.log_callback = log_callback
        self.is_running = True
        
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
        
        # [설정] 모델 후보군
        self.model_candidates = [
            "gemini-2.5-flash",      
            "gemini-2.5-flash-lite" 
        ]

        self.current_model_idx = 0
        
        self.client = None  # [변경] model 객체 대신 client 객체 사용

        try:
            self._configure_genai()
        except Exception as e:
            self.log_callback(f"❌ [Error] Gemini 초기 설정 실패: {e}")

    # ==========================
    # [NEW] 공통 키 로테이션 로직
    # ==========================
    def _rotate_index(self, keys, current_idx, service_name):
        """키 리스트와 현재 인덱스를 받아 다음 인덱스를 반환하는 공통 함수"""
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
            # [변경] 신버전 SDK: Client 인스턴스 생성
            self.client = genai.Client(api_key=current_key)
            
            model_name = self.model_candidates[self.current_model_idx]
            self.log_callback(f"🔑 [AI] 키 설정 ({self.current_key_idx + 1}/{len(self.api_keys)}) | 타겟 모델: {model_name}")
            
        except Exception as e:
            self.log_callback(f"❌ [AI] 설정 오류: {e}")
            self.client = None

    def _rotate_api_key(self):
        """Gemini 키 교체 (공통 함수 사용)"""
        self.current_key_idx, success = self._rotate_index(self.api_keys, self.current_key_idx, "AI")
        if success:
            self._configure_genai() # Gemini는 재설정이 필요함
        return success
    
    def _switch_model(self):
        """모델 인덱스만 변경 (Client는 그대로 사용)"""
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
                # 1. Client 객체 확인 및 복구
                if not self.client: self._configure_genai()
                if not self.client: raise Exception("AI Client 객체 생성 실패")

                # 2. 실행 (신버전 문법)
                # client.models.generate_content(model='모델명', contents='프롬프트')
                current_model = self.model_candidates[self.current_model_idx]
                
                response = self.client.models.generate_content(
                    model=current_model,
                    contents=prompt
                )
                
                if response and response.text: 
                    return response.text.replace('```json', '').replace('```', '').strip()

            except Exception as e:
                error_msg = str(e).lower()
                attempt_count += 1 
                
                # 3. 에러 핸들링
                if "429" in error_msg or "quota" in error_msg or "resource" in error_msg or "model" in error_msg or "404" in error_msg:
                    self.log_callback(f"⏳ [AI] {context} 중 오류, AI API 키를 재설정합니다. ({attempt_count}/{total_combinations})...")
                    key_rotated = self._rotate_api_key()
                    
                    # 키가 한 바퀴 돌았으면 모델 변경
                    if (self.current_key_idx == 0) or (not key_rotated):
                        self.log_callback(f"⚠️ [AI] ({context}) 키 소진. 모델 변경.")
                        self._switch_model()
                    
                    time.sleep(1)
                    continue
                
                else:
                    self.log_callback(f"⚠️ [AI] {context} 실패: {error_msg}")
                    time.sleep(1)
                    continue

        # [최후의 수단]
        self.log_callback(f"❌ [Critical] '{context}' 작업 중 모든 수단 실패.")
        self.stop()
        
        messagebox.showerror(
            "AI 한도 초과 (비상 정지)", 
            f"'{context}' 작업 실패.\n모든 키/모델을 사용했으나 응답이 없습니다.\n프로그램을 종료합니다."
        )
        return None

    # ==========================
    # KIPRIS 관련 로직
    # ==========================
    def _rotate_kipris_key(self):
        """KIPRIS 키 교체 (공통 함수 사용)"""
        self.current_kipris_idx, success = self._rotate_index(self.kipris_keys, self.current_kipris_idx, "KIPRIS")
        return success

    def check_trademark(self, brand):
        if not brand or str(brand).upper() in ["NULL", "NONE", "N/A"]: return True
        if not self.kipris_keys: return True 

        api_url = "https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getWordSearch"
        
        max_retries = 3
        for attempt in range(max_retries):
            current_key = self.kipris_keys[self.current_kipris_idx]
            params = {'searchString': brand, 'ServiceKey': current_key}
            
            try:
                res = requests.get(api_url, params=params, timeout=5)
                if res.status_code != 200:
                    self.log_callback(f"⚠️ [KIPRIS] 서버 오류({res.status_code}). 키 교체 시도...")
                    if self._rotate_kipris_key(): continue
                    return True 

                root = ET.fromstring(res.content)
                error_info = root.find(".//errMsg")
                if error_info is not None and error_info.text:
                    self.log_callback(f"⚠️ [KIPRIS] API 에러: {error_info.text}. 키 교체 시도...")
                    if self._rotate_kipris_key(): continue
                    return True

                count_tag = root.find(".//totalCount")
                if count_tag is None: return True
                    
                count = int(count_tag.text)
                if count > 0:
                    self.log_callback(f"   ❌ [KIPRIS] 상표권 발견! '{brand}' ({count}건)")
                    return False
                return True 

            except Exception as e:
                self.log_callback(f"⚠️ [KIPRIS] 조회 실패({e}). 재시도...")
                if self._rotate_kipris_key(): continue
                return True 
        return True

    # ==========================
    # 메인 비즈니스 로직
    # ==========================
    def analyze_category_with_ai(self, product_title):
        prompt = (
            f"Role: E-commerce Category Classifier\n"
            f"Task: Classify the product '{product_title}' into a Korean e-commerce category path (Coupang/Naver style).\n"
            f"Format: BigCategory > MiddleCategory > SmallCategory\n"
            f"Constraints:\n"
            f"1. Output ONLY the path string.\n"
            f"2. Do NOT write explanations like 'Here is the category'.\n"
            f"3. Do NOT use Markdown.\n"
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
    
    # [수정] 인자에 detail_text 추가 및 프롬프트에 반영
    def extract_full_info(self, p_name, detail_text=""):
        prompt = (
            f"Role: Product Data Extractor\n"
            f"Input Title: '{p_name}'\n"
            f"Input Detail Context (Truncated): '{detail_text[:2000]}'\n\n"
            f"Task: Extract detailed info using BOTH Title and Context. Then translate Title to Korean.\n"
            f"Rules:\n"
            f"1. validity: 'false' if menu/nav/login page.\n"
            f"2. brand/manufacturer: Extract from Context if possible. Output 'NULL' if unknown.\n"
            f"3. productTitle: Natural Korean translation for e-commerce.\n"
            f"4. keywords: 5 Korean tags.\n"
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
                if not data.get('is_valid', True): 
                    self.log_callback(f"   🗑️ 유효하지 않음: {p_name[:10]}...")
                    return None
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
                    f"Role: Professional Translator\n"
                    f"Task: Translate shopping keyword '{keyword}' into {target_lang}.\n"
                    f"Constraint: Output ONLY the translated word. No explanations. No symbols. No Markdown.\n"
                    f"Input: {keyword}\n"
                    f"Output:"
                )
                translated = self._call_gemini_with_retry(trans_prompt, "번역")
                if translated: 
                    translated = translated.replace('"', '').replace("'", "").replace(".", "").strip()
                    self.log_callback(f"   ㄴ 번역: '{keyword}' -> '{translated}'")
                    return translated
            return keyword
        except: return keyword

    def run(self):
        keywords = [k.strip() for k in self.config['TARGET_ITEMS'].split(",") if k.strip()]
        urls = [u.strip() for u in self.config['SHOP_URLS'].split(",") if u.strip()]
        max_count = int(self.config.get('ITEM_COUNT', 10))
        
        self.browser.start_driver()
        try:
            for kw in keywords:
                if not self.is_running: break
                self.log_callback(f"\n=== 🏁 키워드 작업 시작: {kw} ===")
                
                for shop_url in urls:
                    if not self.is_running: break
                    try:
                        t_kw = self.detect_and_translate(shop_url, kw)
                        if len(t_kw) > 50: t_kw = kw 

                        product_list = self.browser.search_and_collect(shop_url, t_kw, max_count, lambda: self.is_running)
                        self.log_callback(f"📊 [Info] {len(product_list)}개 상품 상세 분석 시작...")
                        
                        for i, (p_name, p_url) in enumerate(product_list):
                            if not self.is_running: break
                            self.log_callback(f"🔎 [{i+1}/{len(product_list)}] 상세 페이지 이동 및 분석...")
                            
                            # [추가됨] 상세 페이지 내용 긁어오기
                            detail_text = self.browser.visit_and_get_text(p_url)
                            
                            # [수정됨] detail_text를 함께 전달
                            info = self.extract_full_info(p_name, detail_text)
                            time.sleep(2) 
                            
                            if info:
                                if self.check_trademark(info['brand']):
                                    cat_hint = self.analyze_category_with_ai(info['productTitle'])
                                    time.sleep(1)
                                    
                                    best_cp = self.excel.find_best_category(cat_hint, 'coupang')
                                    best_nv = self.excel.find_best_category(cat_hint, 'naver')
                                    self.log_callback(f"   ㄴ 카테고리: {best_cp[:10]}... / {best_nv[:10]}...")
                                    
                                    self.excel.save_product({
                                        'cp_cat': best_cp, 'nv_cat': best_nv,
                                        'title': info['productTitle'], 'tags': info['keywords'],
                                        'url': p_url, 'manufacturer': info['manufacturer'],
                                        'brand': info['brand'], 'model': info['model']
                                    })
                            time.sleep(1)

                    except WebDriverException:
                        self.log_callback("🚨 브라우저 오류. 재시작...")
                        self.browser.close(); self.browser.start_driver()
                    except Exception as e:
                        self.log_callback(f"⚠️ [Loop Error] {e}")
        finally:
            self.browser.close()
            self.log_callback("\n🏁 [Finish] 작업 종료")

    def stop(self):
        self.is_running = False
        self.log_callback("🛑 [Stop] 중지 요청됨")