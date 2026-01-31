import customtkinter as ctk
import threading
import tkinter as tk # 필요한 경우를 대비해 import

# 모듈 임포트
from ui_components.config_window import ConfigWindow
from logic.processor import SourcingProcessor
import datetime

class MainUI(ctk.CTk):
    def __init__(self, config_manager):
        super().__init__()
        self.cm = config_manager
        self.processor = None
        self.thread = None

        # 윈도우 설정
        self.title("Global Sourcing Helper (AI + Automation)")
        self.geometry("900x650") 
        
        # 그리드 설정
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) 

        # 1. 상단 타이틀 및 버튼 영역
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        
        # [폰트] 맑은 고딕, 26pt
        self.lbl_title = ctk.CTkLabel(self.top_frame, text="🚀 소싱 자동화 (AI Powered)", font=("Malgun Gothic", 26, "bold"))
        self.lbl_title.pack(side="left")

        # 설정 버튼
        self.btn_setting = ctk.CTkButton(
            self.top_frame, 
            text="⚙️ 설정 (Settings)", 
            width=140, 
            height=35,
            font=("Malgun Gothic", 14, "bold"),
            fg_color="#555555", 
            command=self.open_settings
        )
        self.btn_setting.pack(side="right", padx=5)

        # 2. 로그 출력 영역
        # [폰트] 맑은 고딕, 15pt
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 15))
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        # [수정] line_spacing 옵션 제거 (에러 원인 해결)
        self.log_box.configure(state="disabled") 

        # 3. 하단 컨트롤 버튼 영역
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))

        self.btn_start = ctk.CTkButton(
            self.bottom_frame, 
            text="▶ 작업 시작", 
            font=("Malgun Gothic", 18, "bold"), 
            height=55, 
            fg_color="#3B8ED0", 
            command=self.start_process
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_stop = ctk.CTkButton(
            self.bottom_frame, 
            text="⏹ 작업 중지", 
            font=("Malgun Gothic", 18, "bold"), 
            height=55, 
            fg_color="#FF4757", 
            hover_color="#C0392B", 
            command=self.stop_process
        )
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(10, 0))
        self.btn_stop.configure(state="disabled")

        # 초기 메시지
        self.log("✅ 프로그램이 준비되었습니다.")
        self.log(f"   - 타겟 키워드: {self.cm.get_val('TARGET_ITEMS')}")

    def log(self, message):
        """로그 박스에 메시지 출력 (시간 정보 자동 추가)"""
        self.log_box.configure(state="normal")
        
        # [수정] 현재 시간 구하기 (시:분:초)
        current_time = datetime.datetime.now().strftime("[%H:%M:%S]")
        
        # [수정] 시간 + 메시지 합치기
        formatted_msg = f"{current_time} {message}"
        
        # 변경된 메시지를 출력
        self.log_box.insert("end", formatted_msg + "\n")
        self.log_box.see("end") 
        self.log_box.configure(state="disabled")

    def open_settings(self):
        """설정창 열기"""
        if hasattr(self, 'setting_window') and self.setting_window is not None and self.setting_window.winfo_exists():
            self.setting_window.focus()
        else:
            self.setting_window = ConfigWindow(self, self.cm, self.on_save_config)
            self.setting_window.grab_set()
    def on_save_config(self):
        self.log("\n🔄 설정이 변경되었습니다.")
        self.log(f"   - 타겟 키워드: {self.cm.get_val('TARGET_ITEMS')}")

    def start_process(self):
        if self.processor and self.processor.is_running: return

        self.btn_start.configure(state="disabled", fg_color="#aaaaaa")
        self.btn_stop.configure(state="normal")
        self.btn_setting.configure(state="disabled")
        
        self.log("\n🚀 작업을 시작합니다...")
        config_data = self.cm.config['SETTINGS'] if 'SETTINGS' in self.cm.config else {}
        self.processor = SourcingProcessor(config_data, self.log)
        
        self.thread = threading.Thread(target=self.run_thread)
        self.thread.daemon = True
        self.thread.start()

    def run_thread(self):
        try:
            self.processor.run()
        except Exception as e:
            self.log(f"❌ 치명적 오류 발생: {e}")
        finally:
            self.reset_ui_state()

    def stop_process(self):
        if self.processor:
            self.processor.stop()
            self.log("🛑 중지 요청 중... 잠시만 기다려주세요.")
            self.btn_stop.configure(state="disabled")

    def reset_ui_state(self):
        self.btn_start.configure(state="normal", fg_color="#3B8ED0")
        self.btn_stop.configure(state="disabled")
        self.btn_setting.configure(state="normal")
        self.log("🏁 작업이 완전히 종료되었습니다.\n")