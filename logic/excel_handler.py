import os
import pandas as pd
import openpyxl

class ExcelHandler:
    def __init__(self, target_file, log_callback):
        self.target_file = target_file
        self.log_callback = log_callback
        self.coupang_cat = None
        self.naver_cat = None
        
        # 초기 로드
        self.load_categories()

    def load_categories(self):
        """카테고리 엑셀 파일 로드"""
        try:
            if not os.path.exists(self.target_file): 
                self.log_callback(f"⚠️ [Excel] 파일 없음: {self.target_file}")
                return
            # 데이터 타입을 str로 강제 변환하여 로드 (에러 방지)
            self.coupang_cat = pd.read_excel(self.target_file, sheet_name='쿠팡 전체 카테고리 (240517)', dtype=str)
            self.naver_cat = pd.read_excel(self.target_file, sheet_name='네이버 전체 카테고리 (251215)', dtype=str)
            self.log_callback(f"✅ [Excel] 카테고리 데이터 로드 완료")
        except Exception as e:
            self.log_callback(f"❌ [Excel] 로드 실패: {e}")

    def find_best_category(self, ai_path_hint, platform='coupang'):
        """
        AI가 제안한 경로(ai_path_hint)와 가장 유사한 엑셀 카테고리를 찾습니다.
        단순 포함 여부가 아니라, '일치하는 단어 개수(Score)'가 가장 높은 것을 선택합니다.
        """
        df = self.coupang_cat if platform == 'coupang' else self.naver_cat
        if df is None or not ai_path_hint: return ""
        
        target_col = '여기서 카테고리를 복사해주세요'
        
        # AI 힌트를 단어 단위로 쪼갬 (예: "가구 > 조명" -> ['가구', '조명'])
        hint_keywords = [k.strip() for k in ai_path_hint.replace('>', ' ').split() if len(k.strip()) > 1]
        
        best_match = ""
        max_score = 0
        
        # 데이터프레임 순회는 느리므로, 후보군을 먼저 추리기 위해 핵심 키워드(마지막 단어)로 필터링
        # 하지만 정확도를 위해 전체 검색을 하되, 점수제를 도입합니다.
        
        # (성능 최적화) 힌트의 마지막 단어(가장 구체적인 단어)가 포함된 행만 1차 필터링
        if hint_keywords:
            last_keyword = hint_keywords[-1]
            # na=False로 NaN 처리
            candidates = df[df[target_col].str.contains(last_keyword, na=False, case=False)]
            
            if candidates.empty:
                # 마지막 단어가 없으면 전체에서 검색 (느리지만 안전하게)
                candidates = df
        else:
            candidates = df

        # 후보군 중에서 점수 계산
        for cat_path in candidates[target_col]:
            if not isinstance(cat_path, str): continue
            
            score = 0
            # 힌트의 단어들이 해당 카테고리 경로에 몇 개나 들어있는지 카운트
            for kw in hint_keywords:
                if kw in cat_path:
                    score += 1
            
            # 힌트 단어가 많이 포함될수록, 그리고 길이가 비슷할수록 좋은 매칭
            if score > max_score:
                max_score = score
                best_match = cat_path
            elif score == max_score and score > 0:
                # 점수가 같으면 더 짧은 것(상위 카테고리 오매칭 방지) 혹은 더 긴 것?
                # 보통 더 구체적인 것(긴 것)이 좋음
                if len(cat_path) > len(best_match):
                    best_match = cat_path

        return best_match

    def save_product(self, data_row):
        """수집된 상품 정보를 엑셀에 추가"""
        try:
            wb = openpyxl.load_workbook(self.target_file)
            ws = wb['엑셀 수집 양식 (Ver.9)']
            
            # 빈 행 찾기 (4열 상품명 기준)
            start_row = 7
            while ws.cell(row=start_row, column=4).value is not None:
                start_row += 1
            
            # 리스트 -> 문자열 변환
            tags_value = data_row['tags']
            if isinstance(tags_value, list):
                tags_value = ", ".join(tags_value)
            
            # 엑셀 쓰기
            ws.cell(row=start_row, column=2, value=data_row['cp_cat'])
            ws.cell(row=start_row, column=3, value=data_row['nv_cat'])
            ws.cell(row=start_row, column=4, value=data_row['title'])
            ws.cell(row=start_row, column=5, value=tags_value)
            ws.cell(row=start_row, column=6, value=data_row['url'])
            
            # 고정값들
            ws.cell(row=start_row, column=7, value=0)
            ws.cell(row=start_row, column=8, value='무료')
            ws.cell(row=start_row, column=9, value=0)
            ws.cell(row=start_row, column=10, value=5000)
            ws.cell(row=start_row, column=11, value=10000)
            ws.cell(row=start_row, column=12, value=data_row['manufacturer'])
            ws.cell(row=start_row, column=13, value=data_row['brand'])
            ws.cell(row=start_row, column=14, value=data_row['model'])
            
            wb.save(self.target_file)
            self.log_callback(f"💾 [Excel] {start_row}행 저장 | {data_row['title'][:10]}...")
            
        except Exception as e:
            self.log_callback(f"❌ [Excel] 저장 실패: {e}")