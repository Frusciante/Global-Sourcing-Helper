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

class BrowserManager:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.driver = None
        self.proc = None 

    def start_driver(self):
        """독립적인 크롬 프로세스 실행 후 Selenium 연결"""
        try:
            subprocess.run("taskkill /F /IM chrome.exe /T", shell=True, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except: pass

        current_folder = os.getcwd()
        bot_profile_path = os.path.join(current_folder, "bot_profile")
        real_user_data = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')

        if not os.path.exists(bot_profile_path):
            self.log_callback("♻️ [Init] 프로필 복제 중... (최초 1회)")
            try:
                shutil.copytree(real_user_data, bot_profile_path, 
                                ignore=shutil.ignore_patterns('*.lock', 'Singleton*', '*.tmp', 'Cache*', 'Code Cache*'))
            except: pass

        chrome_exe_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_exe_path): 
            chrome_exe_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        
        debug_port = 9222
        cmd = [
            chrome_exe_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={bot_profile_path}",
            "--profile-directory=Default",
            "--no-first-run", "--remote-allow-origins=*"
        ]
        
        self.log_callback(f"🚀 [Init] 크롬 프로세스 시작")
        self.proc = subprocess.Popen(cmd)
        time.sleep(3)

        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.log_callback("✅ [Init] Selenium 연결 성공")
            return self.driver
        except Exception as e:
            self.log_callback(f"❌ [Init] 연결 실패: {e}")
            raise e

    def get_page_source(self):
        if self.driver:
            return self.driver.page_source
        return ""

    def search_and_collect(self, url, keyword, count, is_running_check):
        """키워드 검색 및 상품 목록 수집 (다국어 페이지 이동 기능 추가)"""
        driver = self.driver
        if not driver: return []

        products = []
        page_num = 1
        
        while is_running_check():
            try:
                # --- [A] 첫 진입 시에만 검색어 입력 수행 ---
                if page_num == 1:
                    self.log_callback(f"🔍 [Search] '{keyword}' 검색 시작...")
                    driver.get(url)
                    time.sleep(3)

                    # 1. 검색창 찾기
                    search_input = None
                    search_selectors = [
                        "input#twotabsearchtextbox", "input#q", "input[name='q']", 
                        "input[type='search']", "input[name='keyword']", "input[id*='search']",
                        "input#home-header-searchbox", "input#common-header-search-input" # 1688, 라쿠텐 추가
                    ]

                    for sel in search_selectors:
                        try:
                            search_input = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                            )
                            if search_input: break
                        except: continue

                    if not search_input: 
                        self.log_callback("⚠️ 검색창 미발견 (이미 검색된 상태거나 로그인 화면)")
                    else:
                        # 2. 검색어 입력 및 실행
                        try:
                            search_input.click()
                            time.sleep(0.5)
                            search_input.clear()
                            search_input.send_keys(Keys.CONTROL + "a")
                            search_input.send_keys(Keys.DELETE)
                            search_input.send_keys(keyword)
                            time.sleep(1)
                            search_input.send_keys(Keys.ENTER)
                            time.sleep(3)
                        except Exception as e:
                            self.log_callback(f"❌ [Search] 입력 오류: {e}")

                # --- [B] 현재 페이지에서 상품 수집 ---
                self.log_callback(f"📄 [Page {page_num}] 상품 스캔 중... (현재 {len(products)}/{count}개)")
                
                self._scroll_smoothly()

                # 상품 목록 선택자 (범용)
                selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name", "a[id*='item-title']", "h1", "h2", "h3", "span.a-text-normal"]
                
                current_page_products = [] 

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

                self.log_callback(f"   ㄴ {len(current_page_products)}개 신규 수집 완료.")

                if len(products) >= count:
                    self.log_callback("✅ 목표 수량 달성!")
                    break

                # --- [C] 다음 페이지 이동 로직 (다국어 지원) ---
                self.log_callback("   ⏩ 다음 페이지를 찾습니다...")
                
                next_btn = None
                # [수정됨] 중국어/일본어 포함된 XPath 리스트
                next_buttons_xpath = [
                    "//a[contains(text(), 'Next')]",        # 영어
                    "//a[contains(text(), 'next')]", 
                    "//a[contains(text(), '다음')]",        # 한국어
                    "//a[contains(text(), '>')]",           # 기호
                    "//a[contains(@class, 'next')]",        # 클래스명
                    "//li[contains(@class, 'next')]/a",     
                    "//a[contains(@class, 's-pagination-next')]", # 아마존
                    "//button[contains(@class, 'next')]",

                    # [신규] 중국어 (타오바오, 1688, 티몰)
                    "//a[contains(text(), '下一页')]",      
                    "//span[contains(text(), '下一页')]",   
                    "//button[contains(text(), '下一页')]",
                    "//a[contains(text(), '下页')]",

                    # [신규] 일본어 (라쿠텐, 아마존 재팬)
                    "//a[contains(text(), '次へ')]",        
                    "//a[contains(text(), '次のページ')]",
                    "//a[contains(@class, 'nextPage')]"     
                ]

                for xpath in next_buttons_xpath:
                    try:
                        btn = driver.find_element(By.XPATH, xpath)
                        if btn and btn.is_displayed() and btn.is_enabled():
                            next_btn = btn
                            break
                    except: continue
                
                if next_btn:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", next_btn)
                        self.log_callback(f"   ➡️ 다음 페이지({page_num + 1})로 이동합니다.")
                        time.sleep(4)
                        page_num += 1
                    except Exception as e:
                        self.log_callback(f"   ⚠️ 다음 페이지 버튼 클릭 실패: {e}")
                        break
                else:
                    self.log_callback("   🛑 더 이상 '다음 페이지' 버튼이 없습니다.")
                    break 

            except Exception as e:
                self.log_callback(f"⚠️ 에러 발생 (재시도 루프): {e}")
                break

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