import customtkinter as ctk
from tkinter import messagebox
from config_manager import ConfigManager

class ConfigWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.cm = ConfigManager()
        self.success = False 

        # 윈도우 설정
        self.title("Global Sourcing Helper - Settings")
        self.geometry("750x850")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 메인 스크롤 프레임
        self.scrollable_frame = ctk.CTkScrollableFrame(self, width=720, height=800)
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        # 폰트 설정
        self.title_font = ctk.CTkFont(family="Malgun Gothic", size=28, weight="bold")
        self.label_font = ctk.CTkFont(family="Malgun Gothic", size=16, weight="bold")
        self.entry_font = ctk.CTkFont(family="Malgun Gothic", size=15)

        # 타이틀
        self.label_title = ctk.CTkLabel(self.scrollable_frame, text="수집 프로그램 설정", font=self.title_font)
        self.label_title.pack(pady=(30, 30))

        # --- 1. Gemini API Key (수정됨: 멀티 키 안내) ---
        # 텍스트 컬러를 변경하여 중요성 강조
        self._create_label("Gemini API Key (여러 개는 쉼표 ','로 구분)", color="#3B8ED0") 
        
        # 여러 개의 키를 편집할 때 *로 보이면 수정이 힘들어서 show="*" 제거함
        self.entry_gemini = ctk.CTkEntry(self.scrollable_frame, width=580, height=45, font=self.entry_font)
        self.entry_gemini.pack(pady=(5, 15), anchor="w", padx=85)
        self.entry_gemini.insert(0, self.cm.get_val("GEMINI_API_KEY"))

        # --- 2. KIPRIS API Key ---
        self._create_label("KIPRIS API Key (서비스키)")
        self.entry_kipris = ctk.CTkEntry(self.scrollable_frame, width=580, height=45, font=self.entry_font)
        self.entry_kipris.pack(pady=(5, 15), anchor="w", padx=85)
        self.entry_kipris.insert(0, self.cm.get_val("KIPRIS_API_KEY"))

        # --- 3. 쇼핑몰 홈 URL ---
        self._create_label("쇼핑몰 홈 URL (콤마로 구분)")
        self.txt_urls = ctk.CTkTextbox(self.scrollable_frame, width=580, height=130, font=self.entry_font, border_width=2)
        self.txt_urls.pack(pady=(5, 15), anchor="w", padx=85)
        self.txt_urls.insert("1.0", self.cm.get_val("SHOP_URLS"))

        # --- 4. 선호 판매 항목 ---
        self._create_label("선호 판매 항목 (콤마로 구분)")
        self.txt_items = ctk.CTkTextbox(self.scrollable_frame, width=580, height=160, font=self.entry_font, border_width=2)
        self.txt_items.pack(pady=(5, 15), anchor="w", padx=85)
        self.txt_items.insert("1.0", self.cm.get_val("TARGET_ITEMS"))

        # --- 5. 검색어당 수집 상품 개수 ---
        self._create_label("검색어당 수집 상품 개수 (숫자만 입력)")
        self.entry_count = ctk.CTkEntry(self.scrollable_frame, width=200, height=45, font=self.entry_font)
        self.entry_count.pack(pady=(5, 25), anchor="w", padx=85)
        existing_count = self.cm.get_val("ITEM_COUNT")
        self.entry_count.insert(0, existing_count if existing_count else "10")
        
        # --- 6. 대상 엑셀 파일명 ---
        self._create_label("대상 엑셀 파일명 (확장자 포함)")
        self.entry_excel = ctk.CTkEntry(self.scrollable_frame, width=580, height=45, font=self.entry_font)
        self.entry_excel.pack(pady=(5, 15), anchor="w", padx=85)
        self.entry_excel.insert(0, self.cm.get_val("EXCEL_FILE"))

        # 저장 버튼
        self.btn_save = ctk.CTkButton(
            self.scrollable_frame, 
            text="설정 저장 및 프로그램 시작", 
            command=self.save_config, 
            height=60, 
            width=320,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.btn_save.pack(pady=(20, 40))

    def _create_label(self, text, color=None):
        """레이블 생성을 위한 헬퍼 함수"""
        lbl = ctk.CTkLabel(self.scrollable_frame, text=text, font=self.label_font, text_color=color)
        lbl.pack(anchor="w", padx=85)

    def save_config(self):
        gemini = self.entry_gemini.get().strip() # 공백 제거
        kipris = self.entry_kipris.get().strip()
        urls = self.txt_urls.get("1.0", "end-1c").strip()
        items = self.txt_items.get("1.0", "end-1c").strip()
        count = self.entry_count.get().strip()
        excel_file = self.entry_excel.get().strip()

        # 유효성 검사
        if not count.isdigit():
            messagebox.showwarning("입력 오류", "수집 개수는 숫자만 입력 가능합니다.")
            return

        if not gemini or not kipris:
            messagebox.showwarning("입력 누락", "API 키 정보를 모두 입력해 주세요.")
            return

        # 설정 저장 (ConfigManager가 알아서 config.ini에 씁니다)
        self.cm.save(gemini, kipris, urls, items, count, excel_file)
        
        self.success = True
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다. 프로그램을 시작합니다.")
        self.destroy()