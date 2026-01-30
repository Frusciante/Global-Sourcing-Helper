import configparser
import os

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(self.config_file):
            self.create_default()
        else:
            self.load()

    def create_default(self):
        """기본 설정 생성"""
        self.config['SETTINGS'] = {
            'GEMINI_API_KEY': '',
            'KIPRIS_API_KEY': '',
            'TARGET_ITEMS': '',
            'SHOP_URLS': '',
            'ITEM_COUNT': '10',
            'EXCEL_FILE': 'result.xlsx'
        }
        self.save()

    def load(self):
        """설정 파일 읽기"""
        # 한글 깨짐 방지를 위해 utf-8로 읽기
        self.config.read(self.config_file, encoding='utf-8')
        
        # 파일은 있는데 내용이 비어있거나 SETTINGS 섹션이 없으면 기본값 생성
        if not self.config.sections() or 'SETTINGS' not in self.config:
            self.create_default()

    def save(self):
        """설정 파일 저장"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_val(self, key):
        """값 가져오기 (없으면 빈 문자열 반환)"""
        return self.config['SETTINGS'].get(key, '')

    def update_config(self, new_settings):
        """딕셔너리를 받아 설정을 일괄 업데이트하고 저장"""
        if 'SETTINGS' not in self.config:
            self.config['SETTINGS'] = {}
            
        for key, value in new_settings.items():
            # 모든 값을 문자열로 변환하여 저장
            self.config['SETTINGS'][key] = str(value)
            
        self.save()