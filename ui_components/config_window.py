import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

class StringListEditor(ctk.CTkFrame):
    """모던한 격자(Grid) 스타일 리스트 에디터"""
    def __init__(self, master, title, initial_value="", height=200, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.items = []

        # 제목 (맑은 고딕 적용)
        self.label = ctk.CTkLabel(
            self, text=title, 
            font=("Malgun Gothic", 16, "bold"), 
            anchor="w", text_color="#3B8ED0"
        )
        self.label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 5))

        # 스크롤 영역
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, height=height, fg_color="#2B2B2B", scrollbar_button_color="#555555"
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # 추가 버튼
        self.btn_add = ctk.CTkButton(
            self, text="+ 항목 추가 (Add Item)", 
            font=("Malgun Gothic", 14, "bold"),
            height=35,
            command=self.add_item_dialog, 
            fg_color="#2CC985", hover_color="#229C68"
        )
        self.btn_add.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        self.load_data(initial_value)

    def load_data(self, csv_string):
        self.items = []
        if csv_string:
            self.items = [item.strip() for item in csv_string.split(',') if item.strip()]
        self.render_items()

    def render_items(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for idx, item_text in enumerate(self.items):
            item_card = ctk.CTkFrame(
                self.scroll_frame, fg_color="#333333", 
                border_color="#555555", border_width=2, corner_radius=6
            )
            item_card.grid(row=idx, column=0, sticky="ew", padx=0, pady=3)
            item_card.grid_columnconfigure(0, weight=1)

            # 항목 텍스트
            lbl = ctk.CTkLabel(
                item_card, text=item_text, 
                font=("Malgun Gothic", 15), 
                anchor="w", wraplength=380
            )
            lbl.grid(row=0, column=0, sticky="w", padx=10, pady=8)

            btn_del = ctk.CTkButton(
                item_card, text="삭제", 
                width=60, height=28,
                font=("Malgun Gothic", 12),
                fg_color="#FF4757", hover_color="#E04050",
                command=lambda i=idx: self.delete_item(i)
            )
            btn_del.grid(row=0, column=1, sticky="e", padx=10, pady=8)

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

    def get_value(self):
        return ", ".join(self.items)


class ConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, config_manager, save_callback):
        super().__init__(parent)
        self.title("설정 (Configuration)")
        self.geometry("650x800")
        self.resizable(False, True)
        
        self.cm = config_manager
        self.save_callback = save_callback
        
        # 메인 컨테이너
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # ==========================================================
        # [수정됨] 헤더 영역 (제목 + 저장 버튼)
        # ==========================================================
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 15))

        # 제목 (왼쪽 정렬)
        self.lbl_title = ctk.CTkLabel(
            self.header_frame, 
            text="⚙️ 환경 설정", 
            font=("Malgun Gothic", 24, "bold")
        )
        self.lbl_title.pack(side="left")

        # 저장 버튼 (오른쪽 정렬 - 상단으로 이동)
        self.btn_save = ctk.CTkButton(
            self.header_frame, 
            text="💾 저장 및 닫기", 
            font=("Malgun Gothic", 14, "bold"), 
            height=35,
            width=120,
            fg_color="#3B8ED0", 
            hover_color="#36719F",
            command=self.save_config
        )
        self.btn_save.pack(side="right")
        
        # ==========================================================
        # 스크롤 가능한 메인 영역
        # ==========================================================
        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, width=580, height=600)
        self.scrollable_frame.pack(fill="both", expand=True)

        # 1. API 키 설정
        self.gemini_editor = StringListEditor(
            self.scrollable_frame, title="Gemini API Key 관리", 
            initial_value=self.cm.get_val("GEMINI_API_KEY"), height=150
        )
        self.gemini_editor.pack(fill="x", pady=15)

        self.kipris_editor = StringListEditor(
            self.scrollable_frame, title="KIPRIS API Key 관리", 
            initial_value=self.cm.get_val("KIPRIS_API_KEY"), height=150
        )
        self.kipris_editor.pack(fill="x", pady=15)

        # 2. 수집 설정
        self.target_editor = StringListEditor(
            self.scrollable_frame, title="수집 키워드 (Target Items)", 
            initial_value=self.cm.get_val("TARGET_ITEMS"), height=200
        )
        self.target_editor.pack(fill="x", pady=15)

        self.url_editor = StringListEditor(
            self.scrollable_frame, title="쇼핑몰 URL 목록 (Shop URLs)", 
            initial_value=self.cm.get_val("SHOP_URLS"), height=150
        )
        self.url_editor.pack(fill="x", pady=15)

        # 3. 일반 설정
        self._create_label("한 키워드당 수집 개수")
        self.entry_count = ctk.CTkEntry(self.scrollable_frame, width=200, height=40, font=("Malgun Gothic", 14))
        self.entry_count.pack(pady=(5, 20), anchor="w", padx=5)
        self.entry_count.insert(0, self.cm.get_val("ITEM_COUNT"))

        self._create_label("저장할 엑셀 파일명")
        self.entry_excel = ctk.CTkEntry(self.scrollable_frame, width=500, height=40, font=("Malgun Gothic", 14))
        self.entry_excel.pack(pady=(5, 20), anchor="w", padx=5)
        self.entry_excel.insert(0, self.cm.get_val("EXCEL_FILE"))

        # (하단에 있던 저장 버튼 코드는 삭제됨)

    def _create_label(self, text):
        label = ctk.CTkLabel(self.scrollable_frame, text=text, font=("Malgun Gothic", 16, "bold"), text_color="#3B8ED0")
        label.pack(anchor="w", padx=5, pady=(5, 0))

    def save_config(self):
        gemini_keys = self.gemini_editor.get_value()
        kipris_keys = self.kipris_editor.get_value()
        target_items = self.target_editor.get_value()
        shop_urls = self.url_editor.get_value()
        item_count = self.entry_count.get().strip()
        excel_file = self.entry_excel.get().strip()
        
        if not gemini_keys:
            messagebox.showwarning("경고", "Gemini API Key는 필수입니다.")
            return

        new_config = {
            "GEMINI_API_KEY": gemini_keys,
            "KIPRIS_API_KEY": kipris_keys,
            "TARGET_ITEMS": target_items,
            "SHOP_URLS": shop_urls,
            "ITEM_COUNT": item_count,
            "EXCEL_FILE": excel_file
        }
        
        self.cm.update_config(new_config)
        if self.save_callback: self.save_callback()
        messagebox.showinfo("완료", "설정이 저장되었습니다.")
        self.destroy()