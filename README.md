# Global-Sourcing-Helper

# 🛒 Global Sourcing Helper

**Global Sourcing Helper**는 해외 쇼핑몰의 상품 정보를 자동으로 수집하여 국내 오픈마켓(쿠팡, 네이버) 등록 양식에 맞춰 엑셀 파일로 정리해주는 자동화 도구입니다. Gemini AI를 활용한 상품 분석과 KIPRIS API를 통한 상표권 검토 기능을 포함하고 있습니다.

---

## ✨ 주요 기능

- **AI 상품 분석**: Google Gemini API를 사용하여 상품명 번역, 카테고리 추천, 태그 추출 및 브랜드/제조사 정보를 자동으로 분류합니다.
- **상표권 자동 검토**: KIPRIS API와 연동하여 추출된 브랜드의 상표권 등록 여부를 실시간으로 확인합니다.
- **카테고리 매칭**: 엑셀 내의 카테고리 DB를 검색하여 쿠팡 및 네이버 쇼핑에 최적화된 카테고리 코드를 찾아줍니다.
- **자동 엑셀 기록**: 수집된 데이터를 지정된 엑셀 양식(`windly-excel-bulk-upload-ver9.xlsx`)에 즉시 기록합니다.
- **멀티 플랫폼 검색**: 설정된 쇼핑몰 URL에서 키워드 기반의 자동 크롤링을 수행합니다.

---

## 📋 사전 준비 사항

프로그램 실행을 위해 다음 사항들이 필요합니다:

1. **Python 3.14** 설치
2. **Chrome 브라우저** 설치 (Selenium 연동용)
3. **API 키 발급**:
   - [Google AI Studio](https://aistudio.google.com/) : Gemini API Key 발급
   - [지식재산정보 검색 서비스](https://kipris.or.kr/) : 특허청_상표 정보 조회 서비스(KIPRIS) 활용 신청 및 서비스키 발급
4. **엑셀 양식 파일**: `windly-excel-bulk-upload-ver9.xlsx` 파일이 프로젝트 루트 폴더에 있어야 합니다.

---

## 🚀 설치 및 실행 방법

### 1. 라이브러리 설치
터미널(또는 CMD)에서 아래 명령어를 입력하여 필요한 패키지를 설치합니다.
```bash
pip install customtkinter pandas openpyxl selenium webdriver-manager google-genai requests
