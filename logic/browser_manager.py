import os
import time
import shutil
import subprocess
import random
from tkinter import messagebox

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

class BrowserManager:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.driver = None
        self.proc = None 
        self.checked_sites = set() # [추가] 로그인 확인을 완료한 사이트 목록

    def start_driver(self):
        """
        Selenium 실행 (기존 프로필/하드웨어 정보 유지 + 창 크기/리퍼러만 자연스럽게 변경)
        """
        try:
            subprocess.run("taskkill /F /IM chrome.exe /T", shell=True, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except: pass

        current_folder = os.getcwd()
        bot_profile_path = os.path.join(current_folder, "bot_profile")
        real_user_data = os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')

        # 프로필이 없으면 복사 (최초 1회만)
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
        
        # [은신 1] 창 크기 랜덤화 (User-Agent나 하드웨어 정보는 건드리지 않음)
        # 매번 조금씩 다른 크기로 브라우저를 띄워 '기계적인 느낌'만 제거
        win_w = random.randint(1200, 1600)
        win_h = random.randint(800, 1000)

        cmd = [
            chrome_exe_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={bot_profile_path}",
            "--profile-directory=Default",
            "--no-first-run", 
            "--remote-allow-origins=*",
            "--disable-extensions",
            "--disable-blink-features=AutomationControlled",
            # User-Agent 변경 옵션 제거 -> 원래 크롬 정보 그대로 사용
            f"--window-size={win_w},{win_h}", 
            "--lang=ko_KR" 
        ]
        
        self.log_callback(f"🚀 [Init] 크롬 프로세스 시작 (Stealth Mode)")
        self.proc = subprocess.Popen(cmd)
        time.sleep(3)

        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # [필수] CDP 명령어로 navigator.webdriver 속성 숨김
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false
                    });
                """
            })

            # [은신 2] 구글을 거쳐서 들어온 척하기 (Referer 조작 효과)
            # 타겟 사이트 접속 전에 구글을 한 번 띄워줌
            try:
                self.driver.get("https://www.google.com")
                time.sleep(1.5) # 구글이 로딩될 때까지 잠깐 대기
            except: pass
            
            self.log_callback("✅ [Init] Selenium 연결 성공")
            return self.driver
        except Exception as e:
            self.log_callback(f"❌ [Init] 연결 실패: {e}")
            raise e

    def get_page_source(self):
        if self.driver: return self.driver.page_source
        return ""


    def search_and_collect(self, url, keyword, count, is_running_check, process_callback=None):
        """
        [순서 교정본] 
        1. 페이지 이동(driver.get)을 가장 먼저 수행
        2. 그 다음 사이트 타입(이베이/라쿠텐 등)을 감지
        3. 올바른 식별자를 장전하여 0개 발견 문제 해결
        """
        driver = self.driver
        if not driver: return 0

        collected_count = 0
        page_num = 1
        is_first_load = True 
        processed_links = set()

        # -------------------------------------------------------------
        # 1. 사이트별 설정 정의
        # -------------------------------------------------------------
        next_btns_map = {
            'ebay': ["//a[contains(@type, 'next')]", "//a[@aria-label='Next page']", "//a[contains(@class, 'pagination__next')]"],
            'rakuten': ["//a[@class='nextPage']", "//div[@class='pagination']//a[contains(text(), '次の')]"],
            'taobao': ["//button[contains(@class, 'next-next')]", "//span[contains(text(), '下一页')]"],
            'amazon': ["//a[contains(@class, 's-pagination-next')]", "//a[contains(text(), 'Next')]"],
            '1688': ["//a[contains(@class, 'next')]", "//a[contains(text(), '下一页')]"],
            'common': [
                "//a[contains(text(), 'Next')]", "//a[contains(text(), 'next')]", 
                "//a[contains(text(), '다음')]", "//a[contains(@class, 'next')]",
                "//li[contains(@class, 'next')]/a"
            ]
        }

        product_selectors_map = {
            'ebay': [
                # 1. [표준] 가장 일반적인 상품 링크 클래스
                "a.s-item__link",
                
                # 2. [제목 기반] 링크가 아니라 제목 텍스트(h3)를 직접 찾음
                "h3.s-item__title",
                
                # 3. href 주소에 '/itm/'이 포함된 모든 링크 (가장 강력함)
                # 이베이 상품 주소는 무조건 ebay.com/itm/1234... 형식을 따릅니다.
                "a[href*='/itm/']",
                
                # 4. [구조 기반] 상품 정보 박스 안의 첫 번째 링크
                "div.s-item__info a"
            ],
            'rakuten': [
                "div.searchresultitem h2 a",   # [라쿠텐]
                "div[data-shop-id] h2 a",      
                "a[data-link='item']",         
                "div[class*='title-link-wrapper'] a",
                "div[class*='title--'] a"
            ],
            'taobao': [
                "div[class*='title--']",       # [타오바오]
                "a[class*='doubleCardWrapper']",
                ".ctx-box .title a"
            ],
            '1688': [
                "div.title a",
                ".offer-title a"
            ],
            'amazon': [
                "div[data-component-type='s-search-result'] h2 a", # 검색 결과 표준
                "div.s-result-item h2 a",      # 백업
                "h2.a-size-mini a",            # 모바일/컴팩트 뷰
                "a.a-link-normal.s-underline-text" # 최신 텍스트 링크
            ],           
            'common': [ 
                "[class*='title--']", "[class*='Title--']", 
                "span.a-text-normal", "div.item-name", "a[id*='item-title']", 
                "h1", "h2", "h3"
            ]
        }

        search_selectors = [
            "input#q", "input[name='q']", "input#mq",               # 타오바오
            "input#commonSearchInput", "input[name='k']",           # 라쿠텐
            "input#gh-ac",                                          # 이베이
            "input.alisearch-input", "input#alisearch-input",       # 1688
            "input#twotabsearchtextbox", "input[name='field-keywords']", # 아마존
            "input#headerSearchKeyword",                            # 쿠팡
            "input[name='keyword']", "input[type='search']", "input[id*='search']"
        ]

        # --- [A] 페이지 진입 (최초 1회) - 순서 변경됨 ---
        if is_first_load:
            self.log_callback(f"🚀 [Access] 사이트 접속 중: {url}")
            try:
                driver.get(url)
                time.sleep(3) # 페이지 로딩 대기
            except Exception as e:
                self.log_callback(f"❌ 접속 실패: {e}")
                return 0

        while is_running_check():
            try:
                found_on_page = 0 
                
                # --- [B] 현재 사이트 감지 (페이지 접속 후에 해야 정확함) ---
                current_url_lower = driver.current_url.lower()
                
                current_site_key = 'common'
                if 'ebay' in current_url_lower: current_site_key = 'ebay'
                elif 'rakuten' in current_url_lower: current_site_key = 'rakuten'
                elif 'taobao' in current_url_lower or 'tmall' in current_url_lower: current_site_key = 'taobao'
                elif '1688' in current_url_lower: current_site_key = '1688'
                elif 'amazon' in current_url_lower: current_site_key = 'amazon'

                target_selectors = product_selectors_map[current_site_key]
                target_next_btns = next_btns_map.get(current_site_key, []) + next_btns_map['common']

                # 첫 로드 시에만 로그 출력
                if is_first_load:
                    self.log_callback(f"🌍 사이트 식별: {current_site_key.upper()} 모드")

                # --- [C] 검색 수행 (최초 1회) ---
                if page_num == 1 and is_first_load:
                    self.log_callback(f"🔍 [Search] '{keyword}' 검색어 입력...")
                    
                    # 로그인 체크
                    if current_site_key in ['taobao', '1688'] and (url not in self.checked_sites):
                        self.log_callback("👮 [Login Check] 로그인 확인 요청...")
                        is_ok = messagebox.askokcancel("로그인 확인", "로그인이 완료되었다면 [확인]을 눌러주세요.")
                        if is_ok:
                            self.checked_sites.add(url)
                        else:
                            return collected_count 
                    
                    # 검색어 입력
                    search_input = None
                    for sel in search_selectors:
                        try:
                            search_input = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                            if search_input: break
                        except: continue

                    if search_input:
                        try:
                            # 기존 검색어 있으면 지우기
                            search_input.click()
                            time.sleep(0.5)
                            search_input.clear()
                            search_input.send_keys(Keys.CONTROL + "a")
                            search_input.send_keys(Keys.DELETE)
                            # 새 검색어 입력
                            search_input.send_keys(keyword)
                            time.sleep(1)
                            search_input.send_keys(Keys.ENTER)
                            
                            # 검색 결과 대기
                            self.log_callback("   ⏳ 검색 결과 로딩 대기...")
                            time.sleep(3)
                            
                            # (중요) 사이트별 상품 컨테이너가 뜰 때까지 대기
                            try:
                                WebDriverWait(driver, 8).until(
                                    lambda d: any(d.find_elements(By.CSS_SELECTOR, s) for s in target_selectors)
                                )
                                self.log_callback("   ✅ 리스트 로딩 완료.")
                            except TimeoutException:
                                self.log_callback("   ⚠️ 로딩 지연 (상품 탐색 계속 시도)")

                        except Exception as e:
                            self.log_callback(f"⚠️ 검색어 입력 중 오류: {e}")

                    is_first_load = False # 검색 완료

                # --- [D] 상품 수집 루프 ---
                self.log_callback(f"📄 [Page {page_num}] 탐색 중... ({collected_count}/{count})")
                
                last_scroll_y = driver.execute_script("return window.scrollY")
                same_scroll_count = 0
                next_page_clicked = False 

                while True:
                    if not is_running_check() or collected_count >= count: break
                    
                    found_target = None
                    
                    # 식별자로 상품 탐색
                    for selector in target_selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            try:
                                if len(el.text.strip()) < 5: continue

                                txt = el.text.lower()
                                link = el.get_attribute('href')
                                if not link or link in processed_links: continue
                                
                                # 금지어 필터
                                bad_words = ['contact', 'policy', 'terms', 'privacy', 'guide', 'faq', 'customer', 'support', 'about us']
                                if any(b in txt for b in bad_words) or (link and any(b in link.lower() for b in bad_words)): 
                                    continue
                                
                                # Y좌표 필터
                                try:
                                    if el.location['y'] > 0 and el.location['y'] > driver.execute_script("return document.body.scrollHeight") - 400:
                                        continue
                                except: pass

                                found_target = (el, link)
                                break
                            except: continue
                        if found_target: break
                    
                    if found_target:
                        target_el, target_link = found_target
                        processed_links.add(target_link)
                        found_on_page += 1 
                        product_name = target_el.text.strip()
                        self.log_callback(f"   🔎 발견! '{product_name[:15]}...'")

                        try:
                            main_window = driver.current_window_handle
                            old_windows = driver.window_handles
                            current_list_url = driver.current_url 
                            
                            self._click_like_human(target_el)
                            time.sleep(3)
                            
                            new_windows = driver.window_handles
                            success = False
                            
                            if len(new_windows) > len(old_windows):
                                new_tab = [w for w in new_windows if w not in old_windows][-1]
                                driver.switch_to.window(new_tab)
                                if process_callback:
                                    self._scroll_a_bit_in_detail()
                                    success = process_callback(driver, product_name)
                                try:
                                    if len(driver.window_handles) > 1: driver.close()
                                except: pass
                                driver.switch_to.window(main_window)
                            else:
                                if driver.current_url != current_list_url:
                                    if process_callback:
                                        self._scroll_a_bit_in_detail()
                                        success = process_callback(driver, product_name)
                                    driver.back()
                                    time.sleep(2)
                                    if driver.current_url != current_list_url:
                                        driver.get(current_list_url)
                                        time.sleep(3)
                            
                            if success:
                                collected_count += 1
                                self.log_callback(f"   ✅ 수집 완료 ({collected_count}/{count})")
                                time.sleep(random.uniform(1.0, 3.0))
                            
                        except Exception as e:
                            self.log_callback(f"   ⚠️ 에러: {e}")
                            try: driver.switch_to.window(main_window)
                            except: pass
                        continue 

                    # 상품 못 찾음 (0개) -> 캡차 수동 개입
                    if found_on_page == 0:
                        self.log_callback("🚫 화면 내 상품 0개. (스크롤 시도)")
                        time.sleep(2)
                        driver.execute_script("window.scrollBy(0, 350);") 
                        
                        same_scroll_count += 1
                        if same_scroll_count > 3: # 3번 정도 못 찾으면 사용자에게 물어봄
                            is_retry = messagebox.askretrycancel(
                                "상품 탐색 실패", 
                                "상품을 찾을 수 없습니다 (캡차 의심).\n\n"
                                "1. 브라우저에서 캡차를 확인하고 직접 풀어주세요.\n"
                                "2. 풀었다면 [재시도]를 눌러주세요.\n"
                                "3. [취소]를 누르면 다음 페이지로 넘어갑니다."
                            )
                            if is_retry:
                                same_scroll_count = 0
                                continue
                            else:
                                self.log_callback("❌ 사용자 취소. 다음 페이지 이동.")
                                break
                        continue

                    # 다음 페이지 이동
                    found_next_btn = None
                    for xpath in target_next_btns:
                        try:
                            btns = driver.find_elements(By.XPATH, xpath)
                            for btn in btns:
                                if btn.is_displayed():
                                    try:
                                        if btn.location['y'] < 2000: continue
                                    except: pass
                                    found_next_btn = btn
                                    break
                            if found_next_btn: break
                        except: continue
                    
                    if found_next_btn:
                        self.log_callback("   🚀 다음 페이지 이동")
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", found_next_btn)
                            self._click_like_human(found_next_btn)
                            time.sleep(random.uniform(4.0, 6.0))
                            page_num += 1
                            next_page_clicked = True
                            break 
                        except: pass

                    # 일반 스크롤
                    driver.execute_script(f"window.scrollBy({{top: {random.randint(300, 600)}, behavior: 'smooth'}});")
                    time.sleep(1.5)
                    
                    current_scroll_y = driver.execute_script("return window.scrollY")
                    if current_scroll_y == last_scroll_y:
                        self.log_callback("   🛑 페이지 끝")
                        break
                    else:
                        last_scroll_y = current_scroll_y
                
                if collected_count >= count:
                    self.log_callback("🎉 목표 달성")
                    break
                if next_page_clicked: continue 
                break

            except Exception as e:
                self.log_callback(f"⚠️ 에러: {e}")
                if not messagebox.askretrycancel("오류", f"오류 발생: {e}\n재시도 하시겠습니까?"): break

        return collected_count

    def _scroll_a_bit_in_detail(self):
        """상세 페이지에서 사람처럼 불규칙하게 스크롤 (속도/깊이 랜덤 변형)"""
        try:
            # 1. 최종적으로 내려갈 깊이 설정 (400px ~ 1500px 사이 랜덤)
            # 기존보다 범위를 넓혀서 어떤 상품은 많이 보고, 어떤 건 조금만 보게 함
            target_depth = random.randint(400, 1500)
            current_y = 0
            
            # 2. 목표 지점까지 한 번에 가지 않고, 조금씩 끊어서 이동
            while current_y < target_depth:
                # 한 번에 휠을 굴리는 거리 (100px ~ 350px)
                step = random.randint(100, 350)
                current_y += step
                
                # 스크롤 실행 (smooth 옵션으로 부드럽게)
                self.driver.execute_script(f"window.scrollTo({{top: {current_y}, behavior: 'smooth'}});")
                
                # [속도 조절 핵심] 스크롤 후 다음 스크롤까지의 대기 시간
                # 0.3초(빠름) ~ 1.2초(느림) 사이로 계속 변함 -> 사람의 불규칙한 속도 모방
                time.sleep(random.uniform(0.3, 1.2))
                
                # 3. 가끔(15% 확률) 위로 살짝 다시 올림 (꼼꼼히 보는 척)
                if random.random() < 0.15:
                    reverse = random.randint(50, 150)
                    current_y = max(0, current_y - reverse) # 0보다 작아지지 않게
                    self.driver.execute_script(f"window.scrollTo({{top: {current_y}, behavior: 'smooth'}});")
                    time.sleep(random.uniform(0.5, 0.8))

        except: pass

    def _click_like_human(self, element):
        """요소를 화면 중앙으로 부드럽게 가져온 후 클릭"""
        try:
            # [수정] behavior: 'smooth' 옵션 추가
            # 발견된 상품으로 이동할 때도 '스르륵' 이동하게 만듭니다.
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            
            # 스크롤이 이동하는 시간을 벌어줌 (0.5~1.0초)
            time.sleep(random.uniform(0.5, 1.0))
            
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            
            # 클릭 전 뜸 들이기
            time.sleep(random.uniform(0.2, 0.5))
            
            actions.click(element).perform()
        except Exception:
            # 실패 시 안전하게 일반 클릭
            self.driver.execute_script("arguments[0].click();", element)

    def visit_and_get_text(self, url):
        if not self.driver: return ""
        try:
            self.driver.get(url)
            time.sleep(3)
            return self.driver.find_element(By.TAG_NAME, "body").text[:3000]
        except: return ""

    def close(self):
        try: 
            if self.driver: self.driver.quit()
        except: pass
        try: 
            if self.proc: self.proc.kill()
        except: pass