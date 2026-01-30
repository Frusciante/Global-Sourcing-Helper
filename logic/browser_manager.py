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
        """키워드 검색 및 상품 목록 수집 (로그인 대기 기능 포함)"""
        driver = self.driver
        if not driver: return []

        # [핵심] 재시도 루프: 로그인/캡차 발생 시 사용자가 풀고 다시 시도할 수 있게 함
        while is_running_check():
            try:
                self.log_callback(f"🔍 [Search] '{keyword}' 검색 시작...")
                driver.get(url)
                time.sleep(3)

                # 1. 검색창 찾기
                search_input = None
                search_selectors = [
                    "input#twotabsearchtextbox", "input#q", "input[name='q']", 
                    "input[type='search']", "input[name='keyword']", "input[id*='search']"
                ]

                for sel in search_selectors:
                    try:
                        search_input = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                        )
                        if search_input: break
                    except: continue

                if not search_input: 
                    raise Exception("검색창 미발견 (로그인 페이지 가능성)")

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
                    self.log_callback("   ㄴ 엔터 입력")
                    
                    time.sleep(2)
                    # URL 변화 없으면 버튼 클릭 시도
                    if driver.current_url == url or "search" not in driver.current_url:
                        self.log_callback("   ⚠️ 엔터 반응 없음. 버튼 클릭 시도...")
                        btn_selectors = ["input[type='submit']", "button[class*='search']", "[aria-label='Go']"]
                        for btn_sel in btn_selectors:
                            try:
                                btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
                                driver.execute_script("arguments[0].click();", btn)
                                break
                            except: pass
                    time.sleep(5)
                except Exception as e:
                    self.log_callback(f"❌ [Search] 입력 오류: {e}")
                    raise e

                # 3. 상품 목록 수집
                selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name", "a[id*='item-title']", "h1", "h2", "h3", "span.a-text-normal"]
                products = []
                
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if not elements: continue
                    
                    valid_elements = [el for el in elements if len(el.text.strip()) > 5]
                    if valid_elements:
                        self.log_callback(f"   ㄴ 목록 발견: '{selector}' ({len(valid_elements)}개)")
                        for el in valid_elements:
                            if not is_running_check(): return products # 중단 체크

                            product_name = el.text.strip()
                            product_link = driver.current_url 
                            
                            try:
                                if el.tag_name == 'a': product_link = el.get_attribute('href')
                                else:
                                    try: parent_a = el.find_element(By.XPATH, "./ancestor::a"); product_link = parent_a.get_attribute('href')
                                    except:
                                        try: child_a = el.find_element(By.TAG_NAME, "a"); product_link = child_a.get_attribute('href')
                                        except: pass
                            except: pass

                            if product_link == driver.current_url: continue 
                            products.append((product_name, product_link))
                        
                        if len(products) >= 3: break
                
                if not products: 
                    raise Exception("검색 결과 0개 (로그인/캡차 가능성)")
                
                return products[:count] # 성공 시 리턴

            except WebDriverException as we:
                self.log_callback(f"🚨 [Browser] 연결 끊김: {we}")
                raise we # 브라우저가 꺼진 건 어쩔 수 없이 재시작해야 함

            except Exception as e:
                # [복구된 기능] 여기서 사용자에게 물어봄
                self.log_callback(f"⚠️ [Pause] 수집 중단: {e}")
                
                is_retry = messagebox.askretrycancel(
                    "수동 개입 필요 (로그인/인증)", 
                    f"상품을 찾을 수 없습니다.\n사이트({url})에서 로그인이나 슬라이드 인증이 필요한지 확인해주세요.\n\n"
                    "1. 브라우저에서 직접 로그인/인증을 완료하세요.\n"
                    "2. 완료 후 [재시도]를 누르면 수집을 다시 시작합니다.\n"
                    "3. [취소]를 누르면 이 키워드는 건너뜁니다."
                )
                
                if is_retry:
                    self.log_callback("🔄 사용자가 재시도를 요청했습니다. 다시 시도합니다...")
                    continue # while 루프 처음으로 돌아감
                else:
                    self.log_callback("⏩ 사용자가 취소를 선택했습니다. 다음으로 넘어갑니다.")
                    return [] # 빈 리스트 반환하고 종료
    
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