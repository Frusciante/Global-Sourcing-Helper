# main.py 수정 부분
import threading
from ui_components.config_window import ConfigWindow
from ui_components.main_process_window import MainProcessWindow
from logic.processor import SourcingProcessor

def main():
    settings_app = ConfigWindow()
    settings_app.mainloop()

    if settings_app.success:
        # 1. 설정값 가져오기
        config_data = settings_app.cm.config['SETTINGS']
        
        # 2. 메인 창 생성
        process_app = MainProcessWindow()
        
        # 3. 로직 엔진 생성 및 스레드 시작
        processor = SourcingProcessor(config_data, process_app.add_log)
        thread = threading.Thread(target=processor.run, daemon=True)
        thread.start()
        
        process_app.mainloop()
        
if __name__ == "__main__":
    main()