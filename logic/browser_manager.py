import os
import time
import shutil
import subprocess
from tkinter import messagebox # [추가] 팝업창용

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import random # 상단 추가

class BrowserManager:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.driver = None
        self.proc = None 

    def start_driver(self):
        """Selenium 탐지 회피 옵션을 적용한 크롬 실행"""
        try:
            subprocess.run("taskkill /F /IM chrome.exe /T", shell=True, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except: pass

        current_folder = os.getcwd()
        bot_profile_path = os.path.join(current_folder, "bot_profile")
        
        # ... (프로필 복사 로직은 그대로 유지) ...

        chrome_exe_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_exe_path): 
            chrome_exe_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        
        debug_port = 9222
        
        # [중요 1] 자동화 제어 메시지를 끄는 옵션 추가
        cmd = [
            chrome_exe_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={bot_profile_path}",
            "--profile-directory=Default",
            "--no-first-run", 
            "--remote-allow-origins=*",
            # 아래 옵션들이 추가되어야 함
            "--disable-blink-features=AutomationControlled", # 자동화 제어 감지 방지
            "--disable-infobars", # 상단 '자동화된...' 바 숨김
            "--disable-extensions" 
        ]
        
        self.log_callback(f"🚀 [Init] 크롬 프로세스 시작 (Stealth Mode)")
        self.proc = subprocess.Popen(cmd)
        time.sleep(3)

        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # [중요 2] 브라우저 내부 자바스크립트 변수 조작 (가장 중요)
            # 타오바오가 'navigator.webdriver'를 조회했을 때 'false'를 반환하게 속임
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false
                    });
                """
            })
            
            self.log_callback("✅ [Init] Selenium 연결 성공 (탐지 우회 적용)")
            return self.driver
        except Exception as e:
            self.log_callback(f"❌ [Init] 연결 실패: {e}")
            raise e

    def get_page_source(self):
        if self.driver:
            return self.driver.page_source
        return ""

    def search_and_collect(self, url, keyword, count, is_running_check):
        """키워드 검색 및 상품 목록 수집 (새 탭 전환 기능 추가)"""
        driver = self.driver
        if not driver: return []

        products = []
        page_num = 1
        is_first_load = True 

        while is_running_check():
            try:
                # --- [A] 검색 단계 (1페이지일 때만) ---
                if page_num == 1:
                    if is_first_load:
                        self.log_callback(f"🔍 [Search] '{keyword}' 검색 시작...")
                        driver.get(url)
                        time.sleep(3)
                        is_first_load = False

                    # 1. 검색 전 현재 탭 개수 기억 (비교용)
                    old_window_handles = driver.window_handles

                    # 2. 검색창 찾기 및 입력
                    search_input = None
                    search_selectors = [
                        "input#twotabsearchtextbox", "input#q", "input[name='q']", 
                        "input[type='search']", "input[name='keyword']", "input[id*='search']",
                        "input#home-header-searchbox", "input#common-header-search-input"
                    ]

                    for sel in search_selectors:
                        try:
                            search_input = WebDriverWait(driver, 1).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                            )
                            if search_input: break
                        except: continue

                    if search_input:
                        try:
                            current_val = search_input.get_attribute("value")
                            # 검색어가 비어있거나 다르면 입력 수행
                            if current_val != keyword:
                                search_input.click()
                                time.sleep(0.5)
                                search_input.clear()
                                search_input.send_keys(Keys.CONTROL + "a")
                                search_input.send_keys(Keys.DELETE)
                                search_input.send_keys(keyword)
                                time.sleep(1)
                                search_input.send_keys(Keys.ENTER)
                                time.sleep(3)
                                
                                # [핵심 추가] 검색 후 탭이 늘어났는지 확인하여 시선 이동
                                new_window_handles = driver.window_handles
                                if len(new_window_handles) > len(old_window_handles):
                                    self.log_callback("🔀 새 탭이 감지되었습니다. 시선을 이동합니다.")
                                    # 가장 마지막에 열린 탭(새 탭)으로 전환
                                    driver.switch_to.window(new_window_handles[-1])
                                    time.sleep(2) # 페이지 로딩 대기
                                else:
                                    # 탭이 안 늘어났어도, 혹시 URL이 바뀌었는지 확인
                                    pass

                        except: pass
                    
                # --- [B] 상품 수집 단계 ---
                # (이 시점에서 driver는 이미 결과 페이지 탭을 보고 있습니다)
                self.log_callback(f"📄 [Page {page_num}] 상품 스캔 중... (현재 {len(products)}/{count}개)")
                self._scroll_smoothly()

                selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name", "a[id*='item-title']", "h1", "h2", "h3", "span.a-text-normal"]
                current_page_products = [] 

                # 요소 찾기 시작
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if not elements: continue
                    
                    valid_elements = [el for el in elements if len(el.text.strip()) > 5]
                    
                    for el in valid_elements:
                        if not is_running_check(): return products
                        if len(products) >= count: break 

                        try:
                            product_name = el.text.strip()
                            product_link = driver.current_url 
                            
                            if el.tag_name == 'a': product_link = el.get_attribute('href')
                            else:
                                try: parent_a = el.find_element(By.XPATH, "./ancestor::a"); product_link = parent_a.get_attribute('href')
                                except:
                                    try: child_a = el.find_element(By.TAG_NAME, "a"); product_link = child_a.get_attribute('href')
                                    except: pass
                            
                            if not product_link or product_link == driver.current_url: continue
                            if any(p[1] == product_link for p in products): continue

                            products.append((product_name, product_link))
                            current_page_products.append((product_name, product_link))
                        except: continue
                    
                    if len(products) >= count: break

                # --- [C] 결과 확인 및 수동 개입 (탭 전환 후에도 못 찾으면 팝업) ---
                if len(current_page_products) == 0:
                    self.log_callback(f"⚠️ [Blocked] 상품을 찾을 수 없습니다.")
                    
                    is_retry = messagebox.askretrycancel(
                        "수동 개입 필요",
                        f"현재 탭에서 상품을 찾을 수 없습니다.\n(현재 URL: {driver.current_url})\n\n"
                        f"1. 새 탭이 열렸다면 셀레늄이 거기로 이동했을 것입니다.\n"
                        f"2. 만약 엉뚱한 페이지라면 직접 페이지를 이동해주세요.\n"
                        f"3. 캡차/로그인이 떴다면 해결해주세요.\n"
                        f"4. 준비가 되면 [재시도]를 눌러주세요."
                    )
                    
                    if is_retry:
                        self.log_callback("🔄 재시도: 현재 활성화된 탭에서 다시 스캔합니다.")
                        # 사용자가 탭을 바꿨을 수도 있으니, 현재 보고 있는 탭 유지
                        continue 
                    else:
                        break

                self.log_callback(f"   ㄴ {len(current_page_products)}개 신규 수집 완료.")

                if len(products) >= count:
                    self.log_callback("✅ 목표 수량 달성!")
                    break
                
                wait_time = random.uniform(3.5, 6.5)
                self.log_callback(f"   ⏳ {wait_time:.1f}초 대기 (사람처럼 고민 중)...")
                time.sleep(wait_time)
                
                # --- [D] 다음 페이지 이동 ---
                self.log_callback("   ⏩ 다음 페이지를 찾습니다...")
                
                next_btn = None
                next_buttons_xpath = [
                    # 1. [타오바오/티몰] 전용 (보내주신 HTML 기반)
                    # 클래스에 'next-next'가 포함된 버튼 (가장 정확함)
                    "//button[contains(@class, 'next-next')]",
                    # 버튼 내부에 '下一页' 텍스트를 가진 span이 있는 경우
                    "//button[span[contains(text(), '下一页')]]",
                    
                    # 2. [일반적인 중국어 사이트]
                    "//a[contains(text(), '下一页')]", 
                    "//span[contains(text(), '下一页')]", 
                    "//button[contains(text(), '下一页')]",
                    "//a[contains(text(), '下页')]",

                    # 3. [영어/한국어/기호]
                    "//a[contains(text(), 'Next')]", 
                    "//a[contains(text(), 'next')]", 
                    "//a[contains(text(), '다음')]", 
                    "//a[contains(text(), '>')]", 
                    "//a[contains(@class, 'next')]", 
                    "//li[contains(@class, 'next')]/a", 
                    "//a[contains(@class, 's-pagination-next')]", 
                    "//button[contains(@class, 'next')]",

                    # 4. [일본어]
                    "//a[contains(text(), '次へ')]", 
                    "//a[contains(text(), '次のページ')]", 
                    "//a[contains(@class, 'nextPage')]"     
                ]

                for xpath in next_buttons_xpath:
                    try:
                        btn = driver.find_element(By.XPATH, xpath)
                        # 버튼이 화면에 보이고(is_displayed), 활성화(is_enabled) 상태인지 확인
                        # 타오바오는 마지막 페이지에서 버튼이 disabled 처리될 수 있음
                        if btn and btn.is_displayed():
                            # disabled 속성이 있는지 체크 (마지막 페이지인지 확인)
                            if btn.get_attribute("disabled") or "disabled" in btn.get_attribute("class"):
                                continue
                                
                            next_btn = btn
                            break
                    except: continue
                
                if next_btn:
                    try:
                        # [중요] 타오바오는 하단 바가 버튼을 가리는 경우가 많으므로 JS로 스크롤 및 클릭 강제 실행
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", next_btn)
                        
                        self.log_callback(f"   ➡️ 다음 페이지({page_num + 1})로 이동합니다.")
                        
                        load_wait = random.uniform(3.3, 6.1)
                        time.sleep(load_wait)

                        page_num += 1
                    except Exception as e:
                        self.log_callback(f"   ⚠️ 다음 페이지 버튼 클릭 실패: {e}")
                        break
                else:
                    self.log_callback("   🛑 더 이상 '다음 페이지' 버튼이 없습니다.")
                    break

            except Exception as e:
                self.log_callback(f"⚠️ 에러 발생: {e}")
                is_retry = messagebox.askretrycancel("오류 발생", f"오류: {e}\n\n[재시도] 하시겠습니까?")
                if is_retry: continue
                else: break

        return products[:count]

    def _scroll_smoothly(self):
        """페이지를 부드럽게 끝까지 내림 (Lazy Loading 대응)"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(3): # 3번 정도 나눠서 내림
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height: break
                last_height = new_height
            # 다시 맨 위로 (다음 버튼이 위에 있을 수도 있고, 요소 찾기 안정성 위해)
            # self.driver.execute_script("window.scrollTo(0, 0);") 
        except: pass
    
    def visit_and_get_text(self, url):
        """URL로 이동하여 페이지의 텍스트 정보를 긁어옵니다."""
        if not self.driver: return ""
        try:
            self.driver.get(url)
            time.sleep(3) # 페이지 로딩 대기
            
            # 본문 텍스트 추출 (너무 길면 AI 토큰 낭비이므로 3000자 제한)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            return body_text[:3000] 
        except Exception as e:
            self.log_callback(f"⚠️ [Detail] 상세 페이지 로딩 실패: {e}")
            return ""

    def close(self):
        try: 
            if self.driver: self.driver.quit()
        except: pass
        try: 
            if self.proc: self.proc.kill()
        except: pass