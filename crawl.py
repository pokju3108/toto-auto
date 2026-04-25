"""
베트맨 축구토토 승무패 투표율 크롤러
매시간 GitHub Actions에서 자동 실행
"""
import os
import re
import json
import time
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ── 구글 시트 설정 ────────────────────────────────────────────
SHEET_ID = "1_nLxcE_ZpAB0GZ5UXFFkQO9rZqD8_K4aQeOqCbihXcA"
SHEET_NAME = "Sheet1"

# ── 베트맨 URL ────────────────────────────────────────────────
BETMAN_URL = "https://www.betman.co.kr/main/mainPage/game/gmTotoSMGmBuyView.do?gmId=G101"

def get_google_sheet():
    """구글 시트 연결"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS 환경변수가 없습니다")
    
    creds_data = json.loads(creds_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    return sheet

def crawl_betman():
    """베트맨 크롤링"""
    games = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        print(f"베트맨 접속 중: {BETMAN_URL}")
        page.goto(BETMAN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        
        # 페이지 내용 확인
        content = page.content()
        print(f"페이지 로드 완료, 크기: {len(content)}")
        
        # 경기 행 찾기
        rows = page.query_selector_all("tbody tr")
        print(f"경기 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                # 경기 번호
                no_el = row.query_selector("td:first-child")
                if not no_el:
                    continue
                no_text = no_el.inner_text().strip()
                if not re.match(r'\d+경기', no_text):
                    continue
                no = int(re.search(r'\d+', no_text).group())
                
                # 홈/원정팀
                teams_el = row.query_selector_all("td")
                if len(teams_el) < 6:
                    continue
                
                # 팀명 (홈 vs 원정)
                team_text = teams_el[2].inner_text().strip()
                teams = team_text.split("vs")
                if len(teams) < 2:
                    continue
                home = teams[0].strip()
                away = teams[1].strip()
                
                # 투표율 (승/무/패 %)
                pcts = row.query_selector_all(".pct, .rate, [class*='percent'], [class*='rate']")
                
                # 버튼에서 투표율 추출
                btns = row.query_selector_all("button, .btn-pick, td[class*='sel']")
                rates = []
                for btn in btns:
                    txt = btn.inner_text().strip()
                    m = re.search(r'(\d+\.?\d*)%', txt)
                    if m:
                        rates.append(float(m.group(1)))
                
                if len(rates) < 3:
                    # 다른 방식으로 시도
                    all_tds = row.query_selector_all("td")
                    for td in all_tds:
                        txt = td.inner_text().strip()
                        m = re.search(r'(\d+\.?\d*)%', txt)
                        if m:
                            rates.append(float(m.group(1)))
                
                if len(rates) >= 3:
                    w, d, l = rates[0], rates[1], rates[2]
                else:
                    w, d, l = 33.3, 33.3, 33.3
                
                # 리그
                lge_el = teams_el[1] if len(teams_el) > 1 else None
                lge = lge_el.inner_text().strip() if lge_el else ""
                
                # 상태
                st = "예정"
                
                game = {
                    "no": no,
                    "home": home[:6],  # 6자 제한
                    "away": away[:6],
                    "lge": lge[:4] if lge else "분데스",
                    "w": round(w, 1),
                    "d": round(d, 1),
                    "l": round(l, 1),
                    "st": st
                }
                games.append(game)
                print(f"  {no}경기: {home} vs {away} | 승{w}% 무{d}% 패{l}%")
                
            except Exception as e:
                print(f"  행 {i} 파싱 오류: {e}")
                continue
        
        browser.close()
    
    return games

def update_sheet(sheet, games):
    """구글 시트 업데이트"""
    if not games:
        print("크롤링 데이터 없음 - 시트 업데이트 건너뜀")
        return
    
    # 헤더
    headers = ["no", "home", "away", "lge", "w", "d", "l", "st", "updated"]
    sheet.update("A1", [headers])
    
    # 데이터
    from datetime import datetime, timezone, timedelta
    kst = timezone(timedelta(hours=9))
    now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
    
    rows = []
    for g in sorted(games, key=lambda x: x["no"]):
        rows.append([
            g["no"], g["home"], g["away"], g["lge"],
            g["w"], g["d"], g["l"], g["st"], now_str
        ])
    
    if rows:
        sheet.update(f"A2:I{len(rows)+1}", rows)
    
    print(f"시트 업데이트 완료: {len(rows)}경기, {now_str}")

def main():
    print("=" * 50)
    print("베트맨 크롤러 시작")
    print("=" * 50)
    
    # 크롤링
    games = crawl_betman()
    print(f"\n크롤링 결과: {len(games)}경기")
    
    # 구글 시트 업데이트
    if games:
        sheet = get_google_sheet()
        update_sheet(sheet, games)
    else:
        print("데이터 없음 - 크롤링 실패 가능성")
        # 실패해도 오류로 종료하지 않음
    
    print("\n완료!")

if __name__ == "__main__":
    main()
