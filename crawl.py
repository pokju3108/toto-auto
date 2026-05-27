"""
젠토토 축구토토 승무패 투표율 크롤러
매시간 GitHub Actions에서 자동 실행
"""
import os, re, json
import requests
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1_nLxcE_ZpAB0GZ5UXFFkQO9rZqD8_K4aQeOqCbihXcA"
SHEET_NAME = "시트1"
ZENTOTO_URL = "https://www.zentoto.com/toto/soccer"

def get_google_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS 없음")
    creds_data = json.loads(creds_json)
    scopes = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def crawl_zentoto():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Referer': 'https://www.zentoto.com',
    }
    
    print(f"접속: {ZENTOTO_URL}")
    resp = requests.get(ZENTOTO_URL, headers=headers, timeout=30)
    print(f"상태코드: {resp.status_code}, 크기: {len(resp.text)}")
    
    html = resp.text
    clean = re.sub(r'<[^>]+>', ' ', html)
    clean = re.sub(r'\s+', ' ', clean)
    
    games = []
    result_map = {}
    st_map = {}
    
    # 결과 파싱 (승/무/패)
    result_pattern = re.compile(r'(\d+)\s+([가-힣A-Za-z0-9\.FC]+)\s+(\d+)\s*(승|무|패)\s*(\d+)\s+([가-힣A-Za-z0-9\.FC]+)\s+([\d\.]+)\s*%')
    for rm in result_pattern.finditer(clean):
        no = int(rm.group(1))
        if 1 <= no <= 14:
            result_map[no] = rm.group(4)
            st_map[no] = '종료'
    
    # 경기 파싱
    row_pattern = re.compile(r'(\d+)\s+([가-힣A-Za-z0-9\.FC]+)\s+경기분석\s+VS\s+([가-힣A-Za-z0-9\.FC]+)\s+([\d\.]+)\s*%\s+([\d\.]+)\s*%\s+([\d\.]+)\s*%')
    for m in row_pattern.finditer(clean):
        no = int(m.group(1))
        if 1 <= no <= 14:
            games.append({
                "no": no,
                "home": m.group(2)[:6],
                "away": m.group(3)[:6],
                "w": round(float(m.group(4)), 2),
                "d": round(float(m.group(5)), 2),
                "l": round(float(m.group(6)), 2),
                "st": st_map.get(no, '예정'),
                "result": result_map.get(no, '')
            })
            print(f"  {no}경기: {m.group(2)} vs {m.group(3)} | 승{m.group(4)}% 무{m.group(5)}% 패{m.group(6)}% | {st_map.get(no,'예정')}")
    
    # 메타 정보
    meta = {'totalVotes': '', 'prize': '', 'salePeriod': '', 'round': ''}
    
    period_m = re.search(r'(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)\s*~\s*(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)', html)
    if period_m:
        days = ['일','월','화','수','목','금','토']
        from datetime import datetime
        d1 = datetime.strptime(period_m.group(1), '%Y-%m-%d')
        d2 = datetime.strptime(period_m.group(3), '%Y-%m-%d')
        meta['salePeriod'] = (period_m.group(1)[2:].replace('-','.') + 
            '(' + days[d1.weekday()+1 if d1.weekday()<6 else 0] + ') ' + period_m.group(2) +
            ' ~ ' + period_m.group(3)[2:].replace('-','.') +
            '(' + days[d2.weekday()+1 if d2.weekday()<6 else 0] + ') ' + period_m.group(4))
    
    round_m = re.search(r'(\d+)\s*회차', clean)
    if round_m:
        meta['round'] = round_m.group(1)
    
    for pat in [r'투표수\s*가상조정\s*([\d,]+)', r'총\s*투표수\s*([\d,]+)', r'([\d,]{6,})\s*표']:
        vm = re.search(pat, clean)
        if vm:
            meta['totalVotes'] = vm.group(1)
            break
    
    for pat in [r'1등\s*예상금액\s*([\d,]{6,})', r'1등\s*당첨금액\s*([\d,]{6,})', r'예상\s*금액\s*([\d,]{6,})']:
        pm = re.search(pat, clean)
        if pm:
            meta['prize'] = pm.group(1)
            break
    
    print(f"총투표수: {meta['totalVotes']}, 회차: {meta['round']}, 발매기간: {meta['salePeriod'][:20] if meta['salePeriod'] else '없음'}")
    
    # 디버그: 실제 HTML 구조 파악
    if not games:
        print("=== 디버그: HTML 샘플 ===")
        # % 기호 근처 텍스트 추출
        pct_samples = re.findall(r'.{0,80}[\d\.]+\s*%.{0,80}', clean)
        for s in pct_samples[:5]:
            print(f"  PCT샘플: {s[:150]}")
        # 경기 번호 패턴 찾기
        no_samples = re.findall(r'\d+\s+경기.{0,100}', clean)
        for s in no_samples[:3]:
            print(f"  경기샘플: {s[:150]}")
        # VS 패턴
        vs_samples = re.findall(r'.{0,30}[Vv][Ss].{0,80}', clean)
        for s in vs_samples[:3]:
            print(f"  VS샘플: {s[:150]}")
        print(f"  클린텍스트 샘플: {clean[1000:1500]}")
    
    return games, meta

def update_sheet(sheet, games, meta):
    from datetime import datetime, timezone, timedelta
    now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")

    if not games:
        print("데이터 없음 - 시트 업데이트 스킵")
        return

    # ✅ 각 경기행의 투표율/상태/결과만 업데이트 (다른 컬럼 보존)
    for g in games:
        row = g["no"] + 1
        sheet.update(f"A{row}", [[g["no"]]])
        sheet.update(f"B{row}", [[g["home"]]])
        sheet.update(f"C{row}", [[g["away"]]])
        sheet.update(f"E{row}", [[g["w"]]])
        sheet.update(f"F{row}", [[g["d"]]])
        sheet.update(f"G{row}", [[g["l"]]])
        sheet.update(f"H{row}", [[g["st"]]])
        sheet.update(f"I{row}", [[now_str]])
        # 결과가 있을 때만 L열 업데이트
        if g["result"]:
            sheet.update(f"L{row}", [[g["result"]]])

    # 메타 정보 업데이트 (2행에)
    if meta['totalVotes']:
        sheet.update("J2", [[meta['totalVotes']]])
    if meta['prize']:
        sheet.update("K2", [[meta['prize']]])
    if meta['salePeriod']:
        sheet.update("N2", [[meta['salePeriod']]])

    print(f"✅ 시트 업데이트: {len(games)}경기 | {now_str}")
    print("✅ 기존 데이터(한줄평/팀정보/포메이션 등) 보존됨")

def main():
    print("="*50)
    print("젠토토 크롤러 시작")
    print("="*50)
    games, meta = crawl_zentoto()
    print(f"\n결과: {len(games)}경기")
    sheet = get_google_sheet()
    update_sheet(sheet, games, meta)
    print("완료!")

if __name__ == "__main__":
    main()
