import customtkinter as ctk
import configparser
import os
from tkinter import messagebox

# 1. 설정 관리 클래스
class ConfigManager:
    def __init__(self, filename='config.ini'):
        self.filename = filename
        self.config = configparser.ConfigParser()
        if not os.path.exists(self.filename):
            self.create_default_config()
        else:
            self.config.read(self.filename, encoding='utf-8')

    def create_default_config(self):
        self.config['SETTINGS'] = {
            'GEMINI_API_KEY': '',
            'KIPRIS_API_KEY': '',
            'TARGET_ITEMS': ''
        }
        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def save(self, gemini, kipris, items):
        if 'SETTINGS' not in self.config:
            self.config['SETTINGS'] = {}
        self.config['SETTINGS']['GEMINI_API_KEY'] = gemini
        self.config['SETTINGS']['KIPRIS_API_KEY'] = kipris
        self.config['SETTINGS']['TARGET_ITEMS'] = items
        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_val(self, key):
        try:
            return self.config['SETTINGS'][key]
        except KeyError:
            return ""

# 2. GUI UI 클래스
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.cm = ConfigManager()
        
        # 기본 윈도우 설정
        self.title("Global Sourcing Helper - Settings")
        self.geometry("700x750") # 높이를 더 키워서 넉넉하게 배치
        self.grid_columnconfigure(0, weight=1)
        
        # 테마 및 폰트 설정
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title_font = ctk.CTkFont(family="Malgun Gothic", size=28, weight="bold")
        self.label_font = ctk.CTkFont(family="Malgun Gothic", size=16, weight="bold")
        self.entry_font = ctk.CTkFont(family="Malgun Gothic", size=15)

        # 타이틀
        self.label_title = ctk.CTkLabel(self, text="수집 프로그램 설정", font=self.title_font)
        self.label_title.pack(pady=(40, 30))

        # --- 1. Gemini API Key (Entry - Masked) ---
        self.label_gemini = ctk.CTkLabel(self, text="Gemini API Key", font=self.label_font)
        self.label_gemini.pack(anchor="w", padx=80)
        self.entry_gemini = ctk.CTkEntry(self, width=540, height=45, font=self.entry_font, show="*")
        self.entry_gemini.pack(pady=(5, 20))
        self.entry_gemini.insert(0, self.cm.get_val("GEMINI_API_KEY"))

        # --- 2. KIPRIS API Key (Entry) ---
        self.label_kipris = ctk.CTkLabel(self, text="KIPRIS API Key (서비스키)", font=self.label_font)
        self.label_kipris.pack(anchor="w", padx=80)
        self.entry_kipris = ctk.CTkEntry(self, width=540, height=45, font=self.entry_font)
        self.entry_kipris.pack(pady=(5, 20))
        self.entry_kipris.insert(0, self.cm.get_val("KIPRIS_API_KEY"))

        # --- 3. 선호 판매 항목 (Textbox - Tall & Wide) ---
        self.label_items = ctk.CTkLabel(self, text="선호 판매 항목 (콤마로 구분)", font=self.label_font)
        self.label_items.pack(anchor="w", padx=80)
        
        # 여러 줄 입력이 가능한 Textbox 사용 (가시성 대폭 향상)
        self.txt_items = ctk.CTkTextbox(self, width=540, height=180, font=self.entry_font, border_width=2)
        self.txt_items.pack(pady=(5, 30))
        
        # 기존 값 불러와서 채우기
        existing_items = self.cm.get_val("TARGET_ITEMS")
        if existing_items:
            self.txt_items.insert("1.0", existing_items)

        # 저장 버튼
        self.btn_save = ctk.CTkButton(
            self, 
            text="설정 저장 및 프로그램 시작", 
            command=self.save_config, 
            height=60, 
            width=300,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.btn_save.pack(pady=20)

    def save_config(self):
        gemini = self.entry_gemini.get()
        kipris = self.entry_kipris.get()
        # Textbox에서 텍스트 가져오기 (마지막 줄바꿈 제거)
        items = self.txt_items.get("1.0", "end-1c").strip()

        if not gemini or not kipris:
            messagebox.showwarning("입력 누락", "API 키 정보를 모두 입력해 주세요.")
            return

        # 설정 파일에 저장
        self.cm.save(gemini, kipris, items)
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다. 분석 로직을 실행합니다.")
        
        # 메인 로직 실행을 위해 창 닫기 (필요시 주석 해제)
        # self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()