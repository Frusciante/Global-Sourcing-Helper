import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import requests
import datetime

class StringListEditor(ctk.CTkFrame):
    """모던한 격자(Grid) 스타일 리스트 에디터 (순서 변경 및 전체 삭제 기능 포함)"""
    def __init__(self, master, title, initial_value="", height=200, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.items = []
        self.title_text = title 

        self.configure(fg_color="transparent") 

        # 1. 제목 라벨
        self.label = ctk.CTkLabel(self, text=title, font=("Malgun Gothic", 16, "bold"), anchor="w", text_color="#3B8ED0")
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 5))

        # 2. 스크롤 영역
        self.scroll_frame = ctk.CTkScrollableFrame(self, height=height, fg_color="#1A1A1A", scrollbar_button_color="#555555")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 3. 버튼 영역 (추가 / 전체삭제)
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        self.btn_frame.grid_columnconfigure(0, weight=1) 
        self.btn_frame.grid_columnconfigure(1, weight=0) 

        # [항목 추가 버튼]
        self.btn_add = ctk.CTkButton(self.btn_frame, text="+ 항목 추가", font=("Malgun Gothic", 14, "bold"), height=35,
                                     command=self.add_item_dialog, fg_color="#2CC985", hover_color="#229C68")
        self.btn_add.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # [전체 삭제 버튼]
        self.btn_clear_all = ctk.CTkButton(self.btn_frame, text="🗑️ 모두 삭제", font=("Malgun Gothic", 14, "bold"), height=35,
                                           width=100,
                                           command=self.clear_all_items, fg_color="#FF4757", hover_color="#C0392B")
        self.btn_clear_all.grid(row=0, column=1, sticky="ew")

        self.load_data(initial_value)

    def load_data(self, csv_string):
        self.items = []
        if csv_string:
            self.items = [item.strip() for item in csv_string.split(',') if item.strip()]
        self.render_items()

    def render_items(self):
        """리스트 아이템을 UI에 그리기 (순서 변경 버튼 포함)"""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        for idx, item_text in enumerate(self.items):
            item_card = ctk.CTkFrame(self.scroll_frame, fg_color="#333333", border_color="#555555", border_width=2, corner_radius=6)
            item_card.grid(row=idx, column=0, sticky="ew", padx=0, pady=3)
            item_card.grid_columnconfigure(0, weight=1) # 텍스트 영역
            
            # 1. 텍스트 라벨
            lbl = ctk.CTkLabel(item_card, text=item_text, font=("Malgun Gothic", 15), anchor="w", wraplength=300)
            lbl.grid(row=0, column=0, sticky="w", padx=10, pady=8)
            
            # 2. 컨트롤 버튼 영역 (위, 아래, 삭제)
            ctrl_frame = ctk.CTkFrame(item_card, fg_color="transparent")
            ctrl_frame.grid(row=0, column=1, sticky="e", padx=5, pady=5)
            
            # [위로 이동] ▲
            btn_up = ctk.CTkButton(ctrl_frame, text="▲", width=30, height=28, fg_color="#555555", hover_color="#777777",
                                   command=lambda i=idx: self.move_item(i, -1))
            btn_up.pack(side="left", padx=2)
            if idx == 0: btn_up.configure(state="disabled", fg_color="#333333") # 첫 번째는 위로 못 감

            # [아래로 이동] ▼
            btn_down = ctk.CTkButton(ctrl_frame, text="▼", width=30, height=28, fg_color="#555555", hover_color="#777777",
                                     command=lambda i=idx: self.move_item(i, 1))
            btn_down.pack(side="left", padx=2)
            if idx == len(self.items) - 1: btn_down.configure(state="disabled", fg_color="#333333") # 마지막은 아래로 못 감

            # [삭제] X
            btn_del = ctk.CTkButton(ctrl_frame, text="삭제", width=50, height=28, font=("Malgun Gothic", 12),
                                    fg_color="#FF4757", hover_color="#E04050", 
                                    command=lambda i=idx: self.delete_item(i))
            btn_del.pack(side="left", padx=(10, 2))
    
    def move_item(self, index, direction):
        """항목 순서 변경 (direction: -1=위로, 1=아래로)"""
        if direction == -1 and index > 0: # 위로
            self.items[index], self.items[index-1] = self.items[index-1], self.items[index]
        elif direction == 1 and index < len(self.items) - 1: # 아래로
            self.items[index], self.items[index+1] = self.items[index+1], self.items[index]
        
        self.render_items() # UI 갱신

    def add_items(self, new_items_list):
        for item in new_items_list:
            if item not in self.items:
                self.items.append(item)
        self.render_items()

    def add_item_dialog(self):
        dialog = ctk.CTkInputDialog(text="추가할 값을 입력하세요:", title="항목 추가")
        new_val = dialog.get_input()
        if new_val and new_val.strip():
            self.items.append(new_val.strip())
            self.render_items()

    def delete_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.render_items()

    def clear_all_items(self):
        if not self.items: return 
        ans = messagebox.askyesno("전체 삭제 확인", 
                                  f"[{self.title_text}]\n\n모든 항목을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.")
        if ans:
            self.items = []
            self.render_items()

    def get_value(self):
        return ", ".join(self.items)

class ConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, config_manager, save_callback):
        super().__init__(parent)
        self.title("설정 (Configuration)")
        self.geometry("700x900") # 높이를 조금 늘렸습니다
        self.resizable(False, True)
        
        self.cm = config_manager
        self.save_callback = save_callback
        
        # 메인 컨테이너
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 헤더
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 15))
        self.lbl_title = ctk.CTkLabel(self.header_frame, text="⚙️ 환경 설정", font=("Malgun Gothic", 24, "bold"))
        self.lbl_title.pack(side="left")
        self.btn_save = ctk.CTkButton(self.header_frame, text="💾 저장 및 닫기", font=("Malgun Gothic", 14, "bold"), 
                                      height=35, width=120, fg_color="#3B8ED0", hover_color="#36719F", command=self.save_config)
        self.btn_save.pack(side="right")
        
        # 스크롤 영역
        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, width=640, height=650)
        self.scrollable_frame.pack(fill="both", expand=True)

        # ==========================================================
        # 1. [섹션] API Key 관리
        # ==========================================================
        self.sec_api = self._create_section_frame(self.scrollable_frame, "🔑 API Key 관리", color="#2E3033")
        
        self.gemini_editor = StringListEditor(self.sec_api, title="Gemini API Key", initial_value=self.cm.get_val("GEMINI_API_KEY"), height=100)
        self.gemini_editor.pack(fill="x", pady=10)

        self.kipris_editor = StringListEditor(self.sec_api, title="KIPRIS API Key", initial_value=self.cm.get_val("KIPRIS_API_KEY"), height=100)
        self.kipris_editor.pack(fill="x", pady=10)


        # ==========================================================
        # 2. [섹션] 키워드 & 네이버 추천
        # ==========================================================
        self.sec_keyword = self._create_section_frame(self.scrollable_frame, "🛒 수집 키워드 및 자동 추천", color="#1A2E22")
        
        # (1) 수집 키워드 리스트
        self.target_editor = StringListEditor(self.sec_keyword, title="수집할 키워드 목록 (Target Items)", initial_value=self.cm.get_val("TARGET_ITEMS"), height=200)
        self.target_editor.pack(fill="x", pady=(10, 5))

        # (2) 네이버 추천 실행 버튼
        self.naver_cat_map = {
            "패션의류": "50000000", "패션잡화": "50000001", "화장품/미용": "50000002",
            "디지털/가전": "50000003", "가구/인테리어": "50000004", "출산/육아": "50000005",
            "식품": "50000006", "스포츠/레저": "50000007", "생활/건강": "50000008",
            "여가/생활편의": "50000009", "면세점": "50000010"
        }

        self.naver_action_frame = ctk.CTkFrame(self.sec_keyword, fg_color="transparent")
        self.naver_action_frame.pack(fill="x", pady=(5, 15)) 

        self.combo_cat = ctk.CTkComboBox(self.naver_action_frame, values=list(self.naver_cat_map.keys()), font=("Malgun Gothic", 13), width=150, state="readonly")
        self.combo_cat.pack(side="left", padx=(0, 10))
        self.combo_cat.set("생활/건강")

        self.btn_recommend = ctk.CTkButton(self.naver_action_frame, text="📈 네이버 트렌드 TOP 10 가져오기", 
                                           font=("Malgun Gothic", 14, "bold"), height=40, fg_color="#03C75A", hover_color="#029F48",
                                           command=self.run_naver_recommendation)
        self.btn_recommend.pack(side="left", fill="x", expand=True)


        # ==========================================================
        # 3. [섹션] 쇼핑몰 URL
        # ==========================================================
        self.sec_url = self._create_section_frame(self.scrollable_frame, "🌐 쇼핑몰 관리", color="#2E3033")
        
        self.url_editor = StringListEditor(self.sec_url, title="쇼핑몰 URL 목록", initial_value=self.cm.get_val("SHOP_URLS"), height=150)
        self.url_editor.pack(fill="x", pady=10)

        # ==========================================================
        # 4. [신규 섹션] 배송비 설정 (이미지 요청 반영)
        # ==========================================================
        self.sec_shipping = self._create_section_frame(self.scrollable_frame, "🚚 배송비 설정", color="#2E3033")
        
        # 그리드 레이아웃을 사용하여 테이블 형태로 배치
        self.shipping_grid = ctk.CTkFrame(self.sec_shipping, fg_color="transparent")
        self.shipping_grid.pack(fill="x", pady=10)
        self.shipping_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 4-1. 기본 배송비
        self._create_shipping_input(self.shipping_grid, 0, "기본 배송비", "COST_BASIC", "0")
        
        # 4-2. 교환 배송비
        self._create_shipping_input(self.shipping_grid, 1, "교환 배송비", "COST_EXCHANGE", "20000")
        
        # 4-3. 반품 배송비
        self._create_shipping_input(self.shipping_grid, 2, "반품 배송비", "COST_RETURN", "20000")

        # 4-4. [추가됨] 배송대행지 비용
        self._create_shipping_input(self.shipping_grid, 3, "배송대행지 비용", "COST_AGENCY", "0")


        # ==========================================================
        # 5. [섹션] 일반 설정
        # ==========================================================
        self.sec_general = self._create_section_frame(self.scrollable_frame, "🛠️ 일반 설정", color="#2E3033")

        self._create_sub_label(self.sec_general, "한 키워드당 수집 개수")
        self.entry_count = ctk.CTkEntry(self.sec_general, width=200, height=35, font=("Malgun Gothic", 14))
        self.entry_count.pack(pady=(5, 15), anchor="w")
        self.entry_count.insert(0, self.cm.get_val("ITEM_COUNT"))

        self._create_sub_label(self.sec_general, "저장할 엑셀 파일명")
        self.entry_excel = ctk.CTkEntry(self.sec_general, width=400, height=35, font=("Malgun Gothic", 14))
        self.entry_excel.pack(pady=(5, 15), anchor="w")
        self.entry_excel.insert(0, self.cm.get_val("EXCEL_FILE"))


    # --- Helper Methods ---
    def _create_section_frame(self, parent, title, color):
        frame = ctk.CTkFrame(parent, fg_color=color, corner_radius=10)
        frame.pack(fill="x", padx=10, pady=10)
        lbl = ctk.CTkLabel(frame, text=title, font=("Malgun Gothic", 18, "bold"), text_color="#E0E0E0")
        lbl.pack(anchor="w", padx=15, pady=(15, 5))
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        return inner

    def _create_sub_label(self, parent, text):
        label = ctk.CTkLabel(parent, text=text, font=("Malgun Gothic", 14, "bold"), text_color="#AAAAAA")
        label.pack(anchor="w", pady=(5, 0))

    # [신규] 배송비 입력 필드 생성 헬퍼
    def _create_shipping_input(self, parent, col_idx, title, config_key, default_val):
        frame = ctk.CTkFrame(parent, fg_color="#3A3A3A", corner_radius=6)
        frame.grid(row=0, column=col_idx, sticky="ew", padx=5)
        
        lbl = ctk.CTkLabel(frame, text=title, font=("Malgun Gothic", 14, "bold"), text_color="#FFD700") # 노란색 포인트
        lbl.pack(pady=(10, 5))
        
        entry = ctk.CTkEntry(frame, font=("Malgun Gothic", 14), justify="center")
        entry.pack(pady=(0, 10), padx=10)
        
        val = self.cm.get_val(config_key)
        if not val: val = default_val # 값이 없으면 기본값 사용
        entry.insert(0, val)
        
        # 나중에 저장할 때 참조하기 위해 인스턴스 변수로 저장 (예: self.entry_COST_BASIC)
        setattr(self, f"entry_{config_key}", entry)

    # --- Actions ---
    def run_naver_recommendation(self):
        """네이버 데이터랩 인기 검색어 가져오기"""
        
        selected_name = self.combo_cat.get()
        selected_code = self.naver_cat_map.get(selected_name, "50000008") 
        
        # 2일 전 데이터 요청
        target_date = (datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        
        url = "https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://datalab.naver.com"
        }
        
        data = {
            "cid": selected_code,
            "timeUnit": "date",
            "startDate": target_date,
            "endDate": target_date,
            "age": "",
            "gender": "",
            "device": "",
            "page": "1",
            "count": "20"
        }

        try:
            response = requests.post(url, headers=headers, data=data)
            
            if response.status_code == 200:
                try:
                    result_json = response.json()
                except:
                    messagebox.showerror("파싱 오류", "응답이 JSON 형식이 아닙니다.")
                    return

                # 딕셔너리 구조에서 바로 'ranks' 키를 찾음
                if isinstance(result_json, dict) and 'ranks' in result_json:
                    ranks = result_json['ranks']
                    keywords = [r['keyword'] for r in ranks[:10]]
                    
                    if keywords:
                        self.target_editor.add_items(keywords)
                        messagebox.showinfo("성공", f"'{selected_name}' 인기 키워드 TOP 10을 추가했습니다!\n({target_date} 기준)")
                    else:
                        messagebox.showinfo("결과 없음", "순위 데이터가 비어있습니다.")
                
                else:
                    import json
                    raw_msg = json.dumps(result_json, ensure_ascii=False, indent=2)
                    messagebox.showerror("응답 구조 오류", f"'ranks' 키를 찾을 수 없습니다.\n\n[응답 원본]\n{raw_msg}")

            else:
                messagebox.showerror("통신 오류", f"상태 코드: {response.status_code}\n내용: {response.text[:100]}")
                
        except Exception as e:
            messagebox.showerror("시스템 오류", f"에러 발생: {e}")

    def save_config(self):
        gemini_keys = self.gemini_editor.get_value()
        kipris_keys = self.kipris_editor.get_value()
        target_items = self.target_editor.get_value()
        shop_urls = self.url_editor.get_value()
        item_count = self.entry_count.get().strip()
        excel_file = self.entry_excel.get().strip()
        
        # [신규] 배송비 값 가져오기
        cost_basic = getattr(self, "entry_COST_BASIC").get().strip()
        cost_exchange = getattr(self, "entry_COST_EXCHANGE").get().strip()
        cost_return = getattr(self, "entry_COST_RETURN").get().strip()
        cost_agency = getattr(self, "entry_COST_AGENCY").get().strip() # [추가]

        if not gemini_keys:
            messagebox.showwarning("경고", "Gemini API Key는 필수입니다.")
            return

        new_config = {
            "GEMINI_API_KEY": gemini_keys,
            "KIPRIS_API_KEY": kipris_keys,
            "TARGET_ITEMS": target_items,
            "SHOP_URLS": shop_urls,
            "ITEM_COUNT": item_count,
            "EXCEL_FILE": excel_file,
            # [신규] 배송비 설정 저장
            "COST_BASIC": cost_basic,
            "COST_EXCHANGE": cost_exchange,
            "COST_RETURN": cost_return,
            "COST_AGENCY": cost_agency # [추가]
        }
        
        self.cm.update_config(new_config)
        if self.save_callback: self.save_callback()
        messagebox.showinfo("완료", "설정이 저장되었습니다.")
        self.destroy()