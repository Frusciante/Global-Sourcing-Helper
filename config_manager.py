import configparser
import os

class ConfigManager:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # [중요] 키의 대소문자를 유지하도록 설정 (이 설정 때문에 기존 소문자 파일을 못 읽는 문제 발생)
        self.config.optionxform = str 
        
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
            'EXCEL_FILE': 'result.xlsx',
            # 배송비 기본값
            'COST_BASIC': '3000',
            'COST_EXCHANGE': '6000',
            'COST_RETURN': '6000',
            'COST_AGENCY': '10000'
        }
        self.save()

    def load(self):
        """설정 파일 읽기 및 마이그레이션(소문자->대문자 변환)"""
        # 한글 깨짐 방지를 위해 utf-8로 읽기
        self.config.read(self.config_file, encoding='utf-8')
        
        # 1. SETTINGS 섹션이 아예 없으면 기본값 생성
        if not self.config.sections() or 'SETTINGS' not in self.config:
            self.create_default()
            return

        # 2. [자동 마이그레이션] 기존 소문자 키를 대문자로 변환
        # (optionxform = str 설정으로 인해 소문자 키를 인식 못하는 문제 해결)
        settings = self.config['SETTINGS']
        is_modified = False
        
        # 현재 파일에 있는 키 목록을 리스트로 복사해서 순회 (순회 중 딕셔너리 변경 방지)
        for key in list(settings.keys()):
            if key.islower(): # 키가 소문자라면 (예: gemini_api_key)
                upper_key = key.upper() # 대문자로 변환 (GEMINI_API_KEY)
                
                # 대문자 키로 값을 옮김 (기존 값 유지)
                settings[upper_key] = settings[key]
                
                # 기존 소문자 키 삭제
                del settings[key]
                is_modified = True
        
        # 3. [신규 키 추가] 새로 추가된 배송비 키가 없는 경우 기본값 추가
        default_costs = {
            'COST_BASIC': '3000',
            'COST_EXCHANGE': '6000',
            'COST_RETURN': '6000',
            'COST_AGENCY': '10000'
        }
        for key, val in default_costs.items():
            if key not in settings:
                settings[key] = val
                is_modified = True

        # 변경사항(소문자 변환 or 신규 키 추가)이 있었으면 파일에 즉시 저장
        if is_modified:
            self.save()

    def save(self):
        """설정 파일 저장"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_val(self, key):
        """값 가져오기 (없으면 빈 문자열 반환)"""
        if 'SETTINGS' not in self.config:
            return ''
        return self.config['SETTINGS'].get(key, '')

    def update_config(self, new_settings):
        """딕셔너리를 받아 설정을 일괄 업데이트하고 저장"""
        if 'SETTINGS' not in self.config:
            self.config['SETTINGS'] = {}
            
        for key, value in new_settings.items():
            # 모든 값을 문자열로 변환하여 저장
            self.config['SETTINGS'][key] = str(value)
            
        self.save()