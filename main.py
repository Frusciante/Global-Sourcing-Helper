import customtkinter as ctk
from config_manager import ConfigManager
from ui_components.main_ui import MainUI

def main():
    # 1. 테마 및 색상 설정 (다크 모드, 파란색 테마)
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    # 2. 설정 매니저(ConfigManager) 초기화
    # config.json 파일을 읽어와서 관리하는 객체입니다.
    cm = ConfigManager()

    # 3. 메인 화면(MainUI) 실행
    # MainUI 안에서 [설정] 버튼을 누르면 ConfigWindow가 뜨고,
    # [시작] 버튼을 누르면 Processor 스레드가 돌아가는 구조입니다.
    app = MainUI(cm)
    app.mainloop()

if __name__ == "__main__":
    main()