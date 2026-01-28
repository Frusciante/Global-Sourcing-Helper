import customtkinter as ctk
import time

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