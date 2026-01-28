from ui_components import ConfigWindow, MainProcessWindow

def run_program():
    # 1. 설정 창 실행
    settings_app = ConfigWindow()
    settings_app.mainloop()

    # 2. 설정창이 정상적으로 저장(destroy)된 후 다음 단계 진행
    if settings_app.success:
        process_app = MainProcessWindow()
        
        # 여기서 실제 로직(크롤링/AI)을 별도 스레드로 실행하면 좋습니다.
        process_app.add_log("설정 로드 완료. 작업을 시작합니다...")
        
        process_app.mainloop()

if __name__ == "__main__":
    run_program()