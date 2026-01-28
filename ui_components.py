import customtkinter as ctk
from tkinter import messagebox
import time
from config_manager import ConfigManager

class ConfigWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 설정 관리자 로드
        self.cm = ConfigManager()
        self.success = False # 저장 성공 여부 플래그

        # 기본 윈도우 설정
        self.title("Global Sourcing Helper - Settings")
        self.geometry("750x880")
        self.grid_columnconfigure(0, weight=1)
        
        # 테마 및 폰트 설정
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title_font = ctk.CTkFont(family="Malgun Gothic", size=28, weight="bold")
        self.label_font = ctk.CTkFont(family="Malgun Gothic", size=16, weight="bold")
        self.entry_font = ctk.CTkFont(family="Malgun Gothic", size=15)

        # 타이틀
        self.label_title = ctk.CTkLabel(self, text="수집 프로그램 설정", font=self.title_font)
        self.label_title.pack(pady=(30, 20))

        # --- 1. Gemini API Key (Entry - Masked) ---
        self.label_gemini = ctk.CTkLabel(self, text="Gemini API Key", font=self.label_font)
        self.label_gemini.pack(anchor="w", padx=85)
        self.entry_gemini = ctk.CTkEntry(self, width=580, height=45, font=self.entry_font, show="*")
        self.entry_gemini.pack(pady=(5, 15))
        self.entry_gemini.insert(0, self.cm.get_val("GEMINI_API_KEY"))

        # --- 2. KIPRIS API Key (Entry) ---
        self.label_kipris = ctk.CTkLabel(self, text="KIPRIS API Key (서비스키)", font=self.label_font)
        self.label_kipris.pack(anchor="w", padx=85)
        self.entry_kipris = ctk.CTkEntry(self, width=580, height=45, font=self.entry_font, show='*')
        self.entry_kipris.pack(pady=(5, 15))
        self.entry_kipris.insert(0, self.cm.get_val("KIPRIS_API_KEY"))

        # --- 3. 쇼핑몰 홈 URL (Textbox - Tall) ---
        self.label_urls = ctk.CTkLabel(self, text="쇼핑몰 홈 URL (콤마로 구분)", font=self.label_font)
        self.label_urls.pack(anchor="w", padx=85)
        self.txt_urls = ctk.CTkTextbox(self, width=580, height=130, font=self.entry_font, border_width=2)
        self.txt_urls.pack(pady=(5, 15))
        self.txt_urls.insert("1.0", self.cm.get_val("SHOP_URLS"))

        # --- 4. 선호 판매 항목 (Textbox - Tall) ---
        self.label_items = ctk.CTkLabel(self, text="선호 판매 항목 (콤마로 구분)", font=self.label_font)
        self.label_items.pack(anchor="w", padx=85)
        self.txt_items = ctk.CTkTextbox(self, width=580, height=160, font=self.entry_font, border_width=2)
        self.txt_items.pack(pady=(5, 25))
        self.txt_items.insert("1.0", self.cm.get_val("TARGET_ITEMS"))

        # 저장 버튼
        self.btn_save = ctk.CTkButton(
            self, 
            text="설정 저장 및 프로그램 시작", 
            command=self.save_config, 
            height=60, 
            width=320,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.btn_save.pack(pady=20)

    def save_config(self):
        gemini = self.entry_gemini.get()
        kipris = self.entry_kipris.get()
        urls = self.txt_urls.get("1.0", "end-1c").strip()
        items = self.txt_items.get("1.0", "end-1c").strip()

        if not gemini or not kipris:
            messagebox.showwarning("입력 누락", "API 키 정보를 모두 입력해 주세요.")
            return

        # 설정 관리자를 통한 데이터 저장 (공백 제거 로직 포함)
        self.cm.save(gemini, kipris, urls, items)
        
        self.success = True # 성공 플래그 설정
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다. 작업을 시작합니다.")
        self.destroy() # 설정 창 닫기


class MainProcessWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 메인 프로세스 창 설정
        self.title("Global Sourcing Helper - Running")
        self.geometry("850x650")
        self.grid_columnconfigure(0, weight=1)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 타이틀
        self.label_status = ctk.CTkLabel(self, text="작업 진행 상태", font=("Malgun Gothic", 22, "bold"))
        self.label_status.pack(pady=20)

        # 실시간 로그 출력을 위한 텍스트 박스
        self.log_box = ctk.CTkTextbox(
            self, 
            width=750, 
            height=480, 
            font=("Consolas", 14), # 코딩 폰트 스타일
            border_width=2
        )
        self.log_box.pack(pady=10)
        
        self.add_log("메인 프로세스 창이 활성화되었습니다.")
        self.add_log("수집 및 브랜드 추출 작업을 준비 중입니다...")

    def add_log(self, message):
        """로그 박스에 메시지를 추가하고 스크롤을 가장 아래로 내립니다."""
        current_time = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{current_time}] {message}\n")
        self.log_box.see("end")