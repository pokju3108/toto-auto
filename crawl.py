"""
젠토토 축구토토 승무패 투표율 크롤러
매시간 GitHub Actions에서 자동 실행
"""
import os, re, json
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

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
    seen = set()

    # 종료/진행중 경기 파싱 (스코어 있음)
    # 패턴: 번호 (숫자들) 홈팀 스코어 결과 스코어 원정팀 (숫자들) XX.XX% YY.YY% ZZ.ZZ%
    p_done = re.compile(
        r'(\d+)\s+'
        r'(?:\d+\s+)*'
        r'([가-힣A-Za-z0-9\.]{2,8})\s+'
        r'(\d+)\s*(승|무|패)\s*(\d+)\s+'
        r'([가-힣A-Za-z0-9\.]{2,8})\s+'
        r'(?:\d+\s+)*'
        r'(\d{1,2}\.\d{2})\s*%\s+'
        r'(\d{1,2}\.\d{2})\s*%\s+'
        r'(\d{1,2}\.\d{2})\s*%'
    )
    for m in p_done.finditer(clean):
        no = int(m.group(1))
        if 1 <= no <= 14 and no not in seen:
            seen.add(no)
            games.append({
                "no": no,
                "home": m.group(2)[:6],
                "away": m.group(6)[:6],
                "w": round(float(m.group(7)), 2),
                "d": round(float(m.group(8)), 2),
                "l": round(float(m.group(9)), 2),
                "st": '종료',
                "result": m.group(4)
            })
            print(f"  {no}경기(종료): {m.group(2)} vs {m.group(6)} | {m.group(4)} | 승{m.group(7)}% 무{m.group(8)}% 패{m.group(9)}%")

    # 예정 경기 파싱 (스코어 없음)
    p_pred = re.compile(
        r'(\d+)\s+'
        r'([가-힣A-Za-z0-9\.]{2,8})\s+'
        r'([가-힣A-Za-z0-9\.]{2,8})\s+'
        r'(\d{1,2}\.\d{2})\s*%\s+'
        r'(\d{1,2}\.\d{2})\s*%\s+'
        r'(\d{1,2}\.\d{2})\s*%'
    )
    for m in p_pred.finditer(clean):
        no = int(m.group(1))
        if 1 <= no <= 14 and no not in seen:
            seen.add(no)
            games.append({
                "no": no,
                "home": m.group(2)[:6],
                "away": m.group(3)[:6],
                "w": round(float(m.group(4)), 2),
                "d": round(float(m.group(5)), 2),
                "l": round(float(m.group(6)), 2),
                "st": '예정',
                "result": ''
            })
            print(f"  {no}경기(예정): {m.group(2)} vs {m.group(3)} | 승{m.group(4)}% 무{m.group(5)}% 패{m.group(6)}%")

    games.sort(key=lambda x: x['no'])

    # 메타 정보
    meta = {'totalVotes': '', 'prize': '', 'salePeriod': '', 'round': ''}

    period_m = re.search(r'(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)\s*~\s*(\d{4}-\d{2}-\d{2})\s*\((\d{2}:\d{2})\)', html)
    if period_m:
        days = ['일','월','화','수','목','금','토']
        d1 = datetime.strptime(period_m.group(1), '%Y-%m-%d')
        d2 = datetime.strptime(period_m.group(3), '%Y-%m-%d')
        meta['salePeriod'] = (period_m.group(1)[2:].replace('-','.') +
            '(' + days[d1.isoweekday()%7] + ') ' + period_m.group(2) +
            ' ~ ' + period_m.group(3)[2:].replace('-','.') +
            '(' + days[d2.isoweekday()%7] + ') ' + period_m.group(4))

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

    print(f"총투표수: {meta['totalVotes']}, 회차: {meta['round']}")
    return games, meta

def update_sheet(sheet, games, meta):
    now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")

    if not games:
        print("데이터 없음 - 시트 업데이트 스킵")
        return

    # ✅ 배치 업데이트로 API 호출 최소화
    batch = []
    for g in games:
        row = g["no"] + 1
        # A~I열 한 번에 업데이트 (D열 lge는 건드리지 않음)
        batch.append({
            'range': f"A{row}:C{row}",
            'values': [[g["no"], g["home"], g["away"]]]
        })
        batch.append({
            'range': f"E{row}:I{row}",
            'values': [[g["w"], g["d"], g["l"], g["st"], now_str]]
        })
        if g["result"]:
            batch.append({
                'range': f"L{row}",
                'values': [[g["result"]]]
            })

    # 메타 정보
    meta_batch = []
    if meta['totalVotes']:
        meta_batch.append({'range': 'J2', 'values': [[meta['totalVotes']]]})
    if meta['prize']:
        meta_batch.append({'range': 'K2', 'values': [[meta['prize']]]})
    if meta['salePeriod']:
        meta_batch.append({'range': 'N2', 'values': [[meta['salePeriod']]]})

    # 한 번에 업데이트 (API 호출 1~2회로 줄임)
    all_batch = batch + meta_batch
    sheet.batch_update(all_batch)

    print(f"✅ 시트 업데이트: {len(games)}경기 | {now_str}")
    print("✅ 기존 데이터(한줄평/팀정보/포메이션) 보존됨")

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
