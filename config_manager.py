import configparser
import os

class ConfigManager:
    def __init__(self, filename='config.ini'):
        self.filename = filename
        self.config = configparser.ConfigParser()
        if not os.path.exists(self.filename):
            self.create_default_config()
        else:
            self.config.read(self.filename, encoding='utf-8')

    def create_default_config(self):
        self.config['SETTINGS'] = {'GEMINI_API_KEY': '', 'KIPRIS_API_KEY': '', 'SHOP_URLS': '', 'TARGET_ITEMS': '', 'ITEM_COUNT': '10'}
        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def save(self, gemini, kipris, urls, items, count):
        # 공백 제거 로직 포함
        clean_urls = ",".join([url.strip() for url in urls.split(",") if url.strip()])
        clean_items = ",".join([item.strip() for item in items.split(",") if item.strip()])
        self.config['SETTINGS'] = {
            'GEMINI_API_KEY': gemini.strip(),
            'KIPRIS_API_KEY': kipris.strip(),
            'SHOP_URLS': clean_urls,
            'TARGET_ITEMS': clean_items,
            'ITEM_COUNT': str(count)
        }
        with open(self.filename, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_val(self, key):
        try:
            val = self.config['SETTINGS'][key]
            if key in ['SHOP_URLS', 'TARGET_ITEMS'] and val:
                return ", ".join(val.split(","))
            return val
        except KeyError: return ""