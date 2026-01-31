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
        [수정됨] 타오바오/1688 접속 시 무조건 팝업 띄워서 로그인 확인 (URL 감지 방식 제거)
        """
        driver = self.driver
        if not driver: return 0

        collected_count = 0
        page_num = 1
        is_first_load = True 
        processed_links = set()

        next_buttons_xpath = [
            "//a[contains(@class, 's-pagination-next')]", 
            "//button[contains(@class, 'next-next')]",
            "//button[span[contains(text(), '下一页')]]",
            "//a[contains(text(), '下一页')]", "//span[contains(text(), '下一页')]", 
            "//button[contains(text(), '下一页')]", "//a[contains(text(), '下页')]",
            "//a[contains(text(), 'Next')]", "//a[contains(text(), 'next')]", 
            "//a[contains(text(), '다음')]", "//a[contains(text(), '>')]", 
            "//a[contains(@class, 'next')]", "//li[contains(@class, 'next')]/a", 
            "//button[contains(@class, 'next')]",
            "//a[contains(text(), '次へ')]", "//a[contains(text(), '次のページ')]"
        ]

        while is_running_check():
            try:
                found_on_page = 0 

                # --- [A] 검색 단계 (1페이지, 최초 1회) ---
                if page_num == 1 and is_first_load:
                    self.log_callback(f"🔍 [Search] '{keyword}' 검색 시작...")
                    driver.get(url)
                    time.sleep(3)
                    
                    # -----------------------------------------------------------
                    # 🔥 [수정됨] URL 자동 감지 로직 제거 -> 무조건 물어보기 (사이트별 1회)
                    # -----------------------------------------------------------
                    # 타오바오, 1688, 티몰 등 중국 사이트인지 확인
                    is_login_target = any(site in url for site in ['taobao', '1688', 'tmall'])
                    
                    # 해당 사이트이고, 아직 확인하지 않았다면 팝업 띄움
                    if is_login_target and (url not in self.checked_sites):
                        self.log_callback("👮 [Login Check] 사용자에게 로그인 확인을 요청합니다.")
                        
                        # [확인]을 누를 때까지 여기서 대기함
                        is_ok = messagebox.askokcancel(
                            "로그인 상태 확인",
                            f"타오바오/1688 등에 접속했습니다.\n\n"
                            f"1. 브라우저에서 로그인이 잘 되어 있는지 확인해주세요.\n"
                            f"   (로그인이 안 되어 있다면 지금 직접 로그인해주세요.)\n\n"
                            f"2. 로그인이 완료되었다면 [확인]을 눌러주세요.\n\n"
                            f"([취소]를 누르면 이 작업을 건너뜁니다.)"
                        )
                        
                        if is_ok:
                            self.checked_sites.add(url) # 확인 완료 목록에 추가
                            self.log_callback("✅ 사용자가 로그인을 확인했습니다. 검색을 시작합니다...")
                        else:
                            self.log_callback("🚫 사용자가 작업을 취소했습니다.")
                            return collected_count # 작업 중단
                    
                    is_first_load = False

                    # (이하 검색창 입력 로직 - 기존과 동일)
                    old_window_handles = driver.window_handles
                    search_input = None
                    search_selectors = ["input#twotabsearchtextbox", "input#q", "input[name='q']", "input[type='search']", "input[name='keyword']", "input[id*='search']", "input#home-header-searchbox", "input#common-header-search-input"]

                    for sel in search_selectors:
                        try:
                            search_input = WebDriverWait(driver, 1).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                            if search_input: break
                        except: continue

                    if search_input:
                        try:
                            if search_input.get_attribute("value") != keyword:
                                search_input.click()
                                time.sleep(0.5)
                                search_input.clear()
                                search_input.send_keys(Keys.CONTROL + "a")
                                search_input.send_keys(Keys.DELETE)
                                search_input.send_keys(keyword)
                                time.sleep(1)
                                search_input.send_keys(Keys.ENTER)
                                time.sleep(3)
                                
                                new_window_handles = driver.window_handles
                                if len(new_window_handles) > len(old_window_handles):
                                    driver.switch_to.window(new_window_handles[-1])
                                    time.sleep(2)
                        except: pass

                # --- [B] 실시간 스크롤 및 수집 루프 ---
                self.log_callback(f"📄 [Page {page_num}] 탐색 중... (현재 {collected_count}/{count}개)")
                
                last_scroll_y = driver.execute_script("return window.scrollY")
                same_scroll_count = 0
                next_page_clicked = False 

                while True:
                    if not is_running_check() or collected_count >= count: break
                    
                    # 1. 상품 스캔
                    selectors = ["[class*='title--']", "[class*='Title--']", "div.title", "div.item-name", "a[id*='item-title']", "h1", "h2", "h3", "span.a-text-normal"]
                    found_target = None
                    
                    for selector in selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        candidates = [el for el in elements if len(el.text.strip()) > 5]
                        for el in candidates:
                            try:
                                if el.tag_name == 'a': link = el.get_attribute('href')
                                else: link = el.find_element(By.XPATH, "./ancestor::a").get_attribute('href')
                                
                                if not link or link in processed_links: continue
                                found_target = (el, link)
                                break
                            except: continue
                        if found_target: break
                    
                    if found_target:
                        target_el, target_link = found_target
                        processed_links.add(target_link)
                        found_on_page += 1 
                        
                        product_name = target_el.text.strip()
                        self.log_callback(f"   🔎 발견! '{product_name[:15]}...' 진입")

                        # 진입 및 콜백 실행 (기존과 동일)
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
                                self.log_callback(f"   ✅ 수집 성공 (누적 {collected_count}/{count})")
                                wait_time = random.uniform(0.8, 3.0)
                                self.log_callback(f"   ⏳ 다음 상품 탐색 전 대기 ({wait_time:.1f}s)...")
                                time.sleep(wait_time)
                            
                        except Exception as e:
                            self.log_callback(f"   ⚠️ 처리 중 에러: {e}")
                            try: driver.switch_to.window(main_window)
                            except: pass
                        continue 

                    # 2. 다음 페이지 버튼 감지 (즉시 이동)
                    found_next_btn = None
                    for xpath in next_buttons_xpath:
                        try:
                            btns = driver.find_elements(By.XPATH, xpath)
                            for btn in btns:
                                if btn.is_displayed():
                                    if btn.get_attribute("disabled") or "disabled" in btn.get_attribute("class"): continue
                                    try:
                                        if btn.location['y'] < 2000: 
                                            # self.log_callback("   🛡️ 상단 버튼 감지됨(오탐지 방지). 무시합니다.")
                                            continue
                                    except: pass
                                    found_next_btn = btn
                                    break
                            if found_next_btn: break
                        except: continue
                    
                    if found_next_btn:
                        self.log_callback("   🚀 다음 버튼 발견! 즉시 이동.")
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", found_next_btn)
                            self._click_like_human(found_next_btn)
                            time.sleep(random.uniform(3.5, 6.0))
                            page_num += 1
                            next_page_clicked = True
                            break 
                        except: pass

                    # -------------------------------------------------------
                    # 3. [수정됨] 스크롤 다운 (천천히, 사람처럼)
                    # -------------------------------------------------------
                    scroll_goal = random.randint(500, 800) # 이번 턴에 내려갈 총 거리
                    current_moved = 0
                    
                    while current_moved < scroll_goal:
                        # [미세 조정] 한 번에 100~250px 씩 부드럽게 이동
                        step = random.randint(100, 250)
                        
                        driver.execute_script(f"window.scrollBy({{top: {step}, behavior: 'smooth'}});")
                        current_moved += step
                        
                        # [속도 조절] 휠 굴리고 시선 두는 시간 (0.8 ~ 1.5초)
                        time.sleep(random.uniform(0.8, 1.5))
                        
                        # [사람 특징] 15% 확률로 역주행 (다시 확인)
                        if random.random() < 0.15:
                            reverse = random.randint(50, 150)
                            driver.execute_script(f"window.scrollBy({{top: -{reverse}, behavior: 'smooth'}});")
                            time.sleep(random.uniform(0.6, 1.0))
                            current_moved -= reverse 

                    # -------------------------------------------------------
                    # 4. 스크롤 멈춤 감지 및 대기 로그
                    # -------------------------------------------------------
                    wait_time = random.uniform(1.5, 2.5)
                    self.log_callback(f"   ⏳ 천천히 스크롤 중... ({wait_time:.1f}s 대기)")
                    time.sleep(wait_time)
                    
                    current_scroll_y = driver.execute_script("return window.scrollY")
                    
                    if current_scroll_y == last_scroll_y:
                        same_scroll_count += 1
                        if same_scroll_count >= 3:
                            self.log_callback("   🛑 페이지 끝 도달")
                            break
                    else:
                        same_scroll_count = 0
                        last_scroll_y = current_scroll_y
                
                # --- [C] 결과 확인 (캡차 감지 - 기존 기능 유지) ---
                if collected_count >= count:
                    self.log_callback("🎉 목표 수량 달성!")
                    break

                if found_on_page == 0:
                    self.log_callback("⚠️ [Warning] 이 페이지에서 상품을 하나도 못 찾았습니다. (캡차/로그인 차단 의심)")
                    is_retry = messagebox.askretrycancel(
                        "수동 개입 필요 (상품 0개)",
                        f"현재 페이지에서 상품을 찾을 수 없습니다.\n\n"
                        f"1. 브라우저에 캡차나 로그인이 떴는지 확인하세요.\n"
                        f"2. 문제를 해결했다면 [재시도]를 눌러주세요."
                    )
                    if is_retry:
                        self.log_callback("🔄 재시도: 현재 페이지 다시 스캔...")
                        continue 
                    else:
                        break

                if next_page_clicked:
                    continue 

                self.log_callback("   🛑 다음 페이지 버튼 부재로 종료.")
                break

            except Exception as e:
                self.log_callback(f"⚠️ 에러 발생: {e}")
                is_retry = messagebox.askretrycancel("오류 발생", f"오류: {e}\n\n[재시도] 하시겠습니까?")
                if is_retry: continue
                else: break

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