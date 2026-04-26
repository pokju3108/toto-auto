"""
베트맨 축구토토 승무패 투표율 크롤러
매시간 GitHub Actions에서 자동 실행
"""
import os, re, json, time
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright
 
SHEET_ID = "1_nLxcE_ZpAB0GZ5UXFFkQO9rZqD8_K4aQeOqCbihXcA"
SHEET_NAME = "Sheet1"
BETMAN_URL = "https://www.betman.co.kr/main/mainPage/game/gmTotoSMGmBuyView.do?gmId=G101"
 
def get_google_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS 없음")
    creds_data = json.loads(creds_json)
    scopes = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
 
def crawl_betman():
    games = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":800}
        )
        page = ctx.new_page()
        print(f"접속: {BETMAN_URL}")
        page.goto(BETMAN_URL, timeout=60000)
 
        # JS 렌더링 최대 20초 대기
        for i in range(20):
            time.sleep(1)
            rows = page.query_selector_all("tr")
            texts = [r.inner_text() for r in rows if re.match(r'^\d+경기', r.inner_text().strip())]
            if texts:
                print(f"  {i+1}초 후 경기 행 {len(texts)}개 발견!")
                break
            if i % 5 == 4:
                print(f"  {i+1}초 대기...")
 
        html = page.content()
        print(f"페이지 크기: {len(html)}")
 
        # 전체 tr에서 경기 행 파싱
        all_rows = page.query_selector_all("tr")
        print(f"전체 tr: {len(all_rows)}개")
 
        for row in all_rows:
            try:
                text = row.inner_text().strip()
                m = re.match(r'^(\d+)경기', text)
                if not m:
                    continue
                no = int(m.group(1))
                if no < 1 or no > 14:
                    continue
 
                rates = re.findall(r'(\d+\.?\d*)%', text)
                if len(rates) < 3:
                    continue
 
                w, d, l = float(rates[0]), float(rates[1]), float(rates[2])
                if not (0 < w < 100 and 0 < d < 100 and 0 < l < 100):
                    continue
 
                tm = re.search(r'([가-힣A-Za-z0-9\.\s]+)\s+vs\s+([가-힣A-Za-z0-9\.\s]+)', text)
                home = tm.group(1).strip()[:6] if tm else f"홈{no}"
                away = tm.group(2).strip()[:6] if tm else f"원정{no}"
 
                games.append({"no":no,"home":home,"away":away,"lge":"","w":round(w,1),"d":round(d,1),"l":round(l,1),"st":"예정"})
                print(f"  {no}경기: {home} vs {away} | 승{w}% 무{d}% 패{l}%")
            except:
                continue
 
        # HTML 직접 파싱 (fallback)
        if not games:
            print("Fallback: HTML 직접 파싱")
            blocks = re.findall(r'(\d+)경기.{0,200}?(\d+\.\d+).{0,50}?(\d+\.\d+).{0,50}?(\d+\.\d+)', html, re.DOTALL)
            for b in blocks[:14]:
                try:
                    no=int(b[0]); w,d,l=float(b[1]),float(b[2]),float(b[3])
                    if 1<=no<=14 and 0<w<100 and 0<d<100 and 0<l<100:
                        games.append({"no":no,"home":f"홈{no}","away":f"원정{no}","lge":"","w":round(w,1),"d":round(d,1),"l":round(l,1),"st":"예정"})
                        print(f"  Fallback {no}경기: {w}% {d}% {l}%")
                except:
                    continue
 
        browser.close()
 
    seen=set(); unique=[]
    for g in games:
        if g["no"] not in seen:
            seen.add(g["no"]); unique.append(g)
    return sorted(unique, key=lambda x: x["no"])
 
def update_sheet(sheet, games):
    from datetime import datetime, timezone, timedelta
    now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
    headers = ["no","home","away","lge","w","d","l","st","updated"]
    sheet.update("A1", [headers])
    if not games:
        print("데이터 없음"); return
    rows = [[g["no"],g["home"],g["away"],g["lge"],g["w"],g["d"],g["l"],g["st"],now_str] for g in games]
    sheet.update(f"A2:I{len(rows)+1}", rows)
    print(f"시트 업데이트: {len(rows)}경기 | {now_str}")
 
def main():
    print("="*50)
    print("베트맨 크롤러 시작")
    print("="*50)
    games = crawl_betman()
    print(f"\n결과: {len(games)}경기")
    sheet = get_google_sheet()
    update_sheet(sheet, games)
    print("완료!")
 
if __name__ == "__main__":
    main()
