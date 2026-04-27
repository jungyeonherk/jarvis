"""
☁️ 자비스 클라우드 스캐너 (GitHub Actions용)

보스의 스캔.py를 클라우드 환경으로 이식한 버전.
- 1차: 네이버 금융 (시그널 ②③④⑤)
- 추가: pykrx로 KRX 공매도 (시그널 ①)
- GitHub Actions에서 매일 18:00 자동 실행
- docs/scan_result.json에 결과 저장 → 자비스가 자동 fetch

Author: 보스 + 자비스 (J.A.R.V.I.S Mk XII)
"""

import os
import sys
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import requests
from bs4 import BeautifulSoup

# pykrx for 공매도 데이터
try:
    from pykrx import stock as krx_stock
    HAS_PYKRX = True
except ImportError:
    HAS_PYKRX = False
    print("⚠️ pykrx 미설치 — 공매도(①) 시그널 비활성", flush=True)

# ════════════════════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════════════════════
NAVER = "https://finance.naver.com"
OUTPUT_DIR = Path("docs")
OUTPUT_DIR.mkdir(exist_ok=True)

# 한국 시간 (KST = UTC+9)
def kst_now():
    return datetime.utcnow() + timedelta(hours=9)

KST_TODAY = kst_now().strftime("%Y%m%d")
KST_DATE_FMT = kst_now().strftime("%Y-%m-%d")

# Thread-local session
_local = threading.local()
def get_session():
    if not hasattr(_local, 's'):
        _local.s = requests.Session()
        _local.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        })
    return _local.s

def http_get(url, timeout=10):
    try:
        r = get_session().get(url, timeout=timeout)
        if r.status_code == 200:
            r.encoding = 'euc-kr'  # 네이버 금융 인코딩
            return r.text
    except Exception as e:
        pass
    return ""

def to_int(s):
    if not s: return 0
    c = re.sub(r'[^\d-]', '', s.strip())
    return int(c) if c and c != "-" else 0

# ════════════════════════════════════════════════════════════
# 테마 분류 (보스 sector_config 기반)
# ════════════════════════════════════════════════════════════
THEME_MAP = {
    "반도체": ["반도체", "전자", "메모리"],
    "바이오": ["바이오", "제약", "의약", "진단"],
    "2차전지": ["2차전지", "배터리", "전지"],
    "AI/IT": ["AI", "인공지능", "소프트웨어", "IT", "플랫폼"],
    "조선/방산": ["조선", "방산", "방위"],
    "원전": ["원자력", "원전"],
    "자동차": ["자동차", "부품"],
    "엔터": ["엔터", "미디어", "콘텐츠"],
    "건설": ["건설", "건축"],
    "화학": ["화학", "정유"],
    "금융": ["은행", "증권", "보험", "금융"],
}

EXCLUDED_SECTORS = {"기타금융", "리츠", "부동산투자", "창업투자", "투자회사"}

def classify_theme(name, sector=""):
    text = f"{name} {sector}"
    for theme, keywords in THEME_MAP.items():
        for kw in keywords:
            if kw in text:
                return theme
    return sector if sector else "기타"

# ════════════════════════════════════════════════════════════
# 1차 스캔: 네이버 금융 (보스 스캔.py 그대로 이식)
# ════════════════════════════════════════════════════════════
def scan_stock_naver(code, name):
    """네이버 금융에서 시그널 ②③④⑤ 분석"""
    r = {
        "code": code, "name": name, "score": 0, "signals": [],
        "d3_change": 0, "consec_rise": 0, "quiet_days": 0,
        "inst_days": 0, "frgn_days": 0, "cur_price": 0,
        "day_volume": 0,
        "short_consec": 0, "short_pct": 0, "short_detail": "",
        "ah_vol": 0, "ah_ratio": 0,
        "sector": "", "theme": "",
    }

    # ━━ 일봉 데이터 (2 페이지) ━━
    all_rows = []
    for pg in range(1, 3):
        html = http_get(f"{NAVER}/item/sise_day.naver?code={code}&page={pg}")
        if not html: break
        for tr in BeautifulSoup(html, "html.parser").select("table.type2 tr"):
            tds = tr.find_all("td")
            if len(tds) < 7: continue
            dt = tds[0].get_text(strip=True)
            if not re.match(r'\d{4}\.\d{2}\.\d{2}', dt): continue
            c_ = to_int(tds[1].get_text())
            o = to_int(tds[3].get_text())
            v = to_int(tds[6].get_text())
            if c_ > 0 and v > 0:
                all_rows.append({"close": c_, "open": o, "vol": v})
        if len(all_rows) >= 30: break
        time.sleep(0.03)

    if len(all_rows) < 10: return r
    rows = all_rows
    r["cur_price"] = rows[0]["close"]
    r["day_volume"] = rows[0]["vol"]

    vol_avg = sum(x["vol"] for x in rows[:20]) / 20
    if vol_avg <= 0: return r

    # ━━ ② 조용한 상승 ━━
    consec = 0; quiet = 0
    for x in rows:
        if x["close"] > x["open"]:
            consec += 1
            if x["vol"] < vol_avg: quiet += 1
        else: break
    r["consec_rise"] = consec
    r["quiet_days"] = quiet

    if len(rows) >= 4 and rows[3]["close"] > 0:
        r["d3_change"] = round((rows[0]["close"] - rows[3]["close"]) / rows[3]["close"] * 100, 2)

    if consec >= 3 and quiet >= 2:
        r["score"] += 1
        r["signals"].append("②조용한상승")
    if consec < 2: return r
    time.sleep(0.03)

    # ━━ ④⑤ 기관/외인 ━━
    html = http_get(f"{NAVER}/item/frgn.naver?code={code}")
    if html:
        ic = fc = 0
        i_done = f_done = False
        for tr in BeautifulSoup(html, "html.parser").select("table.type2 tr"):
            tds = tr.find_all("td")
            if len(tds) < 9: continue
            dt = tds[0].get_text(strip=True)
            if not re.match(r'\d{4}\.\d{2}\.\d{2}', dt): continue
            inst = to_int(tds[5].get_text())
            frgn = to_int(tds[6].get_text())
            if not i_done:
                if inst > 0: ic += 1
                else: i_done = True
            if not f_done:
                if frgn > 0: fc += 1
                else: f_done = True
            if i_done and f_done: break
        r["inst_days"] = ic
        r["frgn_days"] = fc
        if ic >= 3:
            r["score"] += 1
            r["signals"].append(f"④기관{ic}일")
        if fc >= 3:
            r["score"] += 1
            r["signals"].append(f"⑤외인{fc}일")

    return r

# ════════════════════════════════════════════════════════════
# 코스피/코스닥 전종목 가져오기
# ════════════════════════════════════════════════════════════
def fetch_all_codes():
    """KOSPI + KOSDAQ 시가총액 상위 종목 코드 수집"""
    codes = []

    def is_excluded(name):
        # 우선주, ETF, 스팩 등 제외
        if re.search(r'(우|2우|3우|우B|우C)$', name): return True
        if any(kw in name for kw in ['스팩', 'ETF', 'ETN', 'KODEX', 'TIGER', 'KBSTAR', 'ARIRANG', 'HANARO', 'KINDEX']): return True
        return False

    print(f"[CODES] KRX 전종목 수집 중...", flush=True)

    for sosok in [0, 1]:  # 0=KOSPI, 1=KOSDAQ
        market_name = "KOSPI" if sosok == 0 else "KOSDAQ"
        for pg in range(1, 35):  # 페이지당 50종목 → 35페이지면 1750종목
            html = http_get(f"{NAVER}/sise/sise_market_sum.naver?sosok={sosok}&page={pg}")
            if not html: break
            soup = BeautifulSoup(html, "html.parser")
            count_before = len(codes)
            for a in soup.select("a.tltle"):
                href = a.get('href', '')
                m = re.search(r'code=(\d{6})', href)
                if m:
                    code = m.group(1)
                    name = a.get_text(strip=True)
                    if not is_excluded(name):
                        codes.append({"code": code, "name": name, "market": market_name})
            count_after = len(codes)
            if count_after == count_before: break  # 더 이상 종목 없음
            time.sleep(0.05)
        print(f"[CODES] {market_name} 수집 완료: {len([c for c in codes if c['market']==market_name])}개", flush=True)

    # 중복 제거
    seen = set()
    unique = []
    for c in codes:
        if c["code"] not in seen:
            seen.add(c["code"])
            unique.append(c)

    print(f"[CODES] 총 {len(unique)}개 종목", flush=True)
    return unique

# ════════════════════════════════════════════════════════════
# pykrx 공매도 데이터 (시그널 ①번 - 보스 키움 OpenAPI 대체)
# ════════════════════════════════════════════════════════════
def add_short_signal(results):
    """pykrx로 7일 공매도 추이 분석 → 시그널 ① 추가"""
    if not HAS_PYKRX or not results:
        print("[SHORT] pykrx 비활성 또는 후보 없음 — 건너뜀", flush=True)
        return results

    print(f"[SHORT] pykrx로 공매도 데이터 조회 ({len(results)}종목)...", flush=True)

    # 최근 영업일 7일치
    today = kst_now()
    end_date = today.strftime("%Y%m%d")
    start_date = (today - timedelta(days=14)).strftime("%Y%m%d")

    for r in results:
        try:
            df = krx_stock.get_shorting_volume_by_date(start_date, end_date, r["code"])
            if df is None or df.empty or len(df) < 7:
                continue

            # 최근 7일 공매도 거래량 (DataFrame 마지막 7행)
            recent7 = df.tail(7)
            short_vols = recent7['공매도'].tolist() if '공매도' in recent7.columns else []
            if len(short_vols) < 7: continue

            # 최근 3일 연속 감소 검사
            consec_down = 0
            for i in range(len(short_vols) - 1, 0, -1):
                if short_vols[i] < short_vols[i-1]:
                    consec_down += 1
                else:
                    break

            # 평균 감소율 (최근 3일 vs 이전 4일)
            recent_avg = sum(short_vols[-3:]) / 3 if len(short_vols) >= 3 else 0
            prev_avg = sum(short_vols[-7:-3]) / 4 if len(short_vols) >= 7 else 0
            pct_change = ((recent_avg - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0

            r["short_consec"] = consec_down
            r["short_pct"] = round(pct_change, 1)
            r["short_detail"] = ">".join(str(int(v)) for v in short_vols)

            # 시그널 ① 추가
            if consec_down >= 3:
                r["score"] += 1
                r["signals"].append("①공매도3일↓")
            elif pct_change <= -30:
                r["score"] += 1
                r["signals"].append(f"①공매도평균↓{abs(int(pct_change))}%")

            time.sleep(0.05)  # KRX rate limit 보호
        except Exception as e:
            continue

    print(f"[SHORT] 완료", flush=True)
    return results

# ════════════════════════════════════════════════════════════
# 메인 스캐너
# ════════════════════════════════════════════════════════════
def main():
    print("="*60, flush=True)
    print(f"☁️  J.A.R.V.I.S 클라우드 스캐너 시작 — {kst_now().strftime('%Y-%m-%d %H:%M KST')}", flush=True)
    print("="*60, flush=True)

    # 1. 전종목 코드 수집
    all_codes = fetch_all_codes()
    if not all_codes:
        print("[ERROR] 종목 수집 실패", flush=True)
        sys.exit(1)

    # 2. 1차 스캔 (네이버, 병렬 처리)
    print(f"\n[SCAN] 1차 스캔 시작 ({len(all_codes)}종목, 병렬 8 thread)...", flush=True)
    results = []
    completed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(scan_stock_naver, c["code"], c["name"]): c for c in all_codes}
        for fut in as_completed(futures):
            try:
                r = fut.result()
                if r["score"] >= 2:
                    results.append(r)
            except Exception:
                pass
            completed += 1
            if completed % 100 == 0:
                print(f"[SCAN] {completed}/{len(all_codes)} 진행 — 후보 {len(results)}개", flush=True)

    print(f"\n[SCAN] 1차 완료: {len(results)}종목 발견", flush=True)

    # 3. 공매도 시그널 추가 (pykrx)
    results = add_short_signal(results)

    # 4. 정렬: 점수 내림차순 → d3_change 내림차순
    results.sort(key=lambda x: (-x["score"], -x.get("d3_change", 0)))

    # 5. TOP 10 추출 + 테마 분류 + 신규 표시
    top10 = []
    for i, r in enumerate(results[:10]):
        r["rank"] = i + 1
        r["theme"] = classify_theme(r["name"], r.get("sector", ""))
        r["sector"] = r["theme"]
        r["final_score"] = r["score"] + 1  # 신규 보정
        r["adj_score"] = 1
        r["adj_reasons"] = ["🆕신규"]
        r["is_new_entry"] = True
        r["signals"] = ", ".join(r["signals"]) if isinstance(r["signals"], list) else r["signals"]
        r["reasons"] = []
        if r.get("short_pct", 0) <= -30:
            r["reasons"].append(f"공매도 평균 감소 ({r['short_pct']}%) [{r.get('short_detail','')}]")
        top10.append(r)

    # 6. JSON 저장 (보스 PC 형식과 동일)
    output = {
        "date": KST_DATE_FMT,
        "count": len(top10),
        "saved_at": kst_now().isoformat(),
        "signals_version": "v3_cloud_5signals",
        "phase2_done": HAS_PYKRX,  # pykrx 작동 시 True
        "scanner": "GitHub Actions Cloud",
        "total_scanned": len(all_codes),
        "top10": top10,
    }

    # docs/scan_result.json (자비스가 fetch할 파일)
    out_file = OUTPUT_DIR / "scan_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # docs/scan_YYYYMMDD.json (날짜별 아카이브)
    archive_file = OUTPUT_DIR / f"scan_{KST_TODAY}.json"
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}", flush=True)
    print(f"✅ 스캔 완료!", flush=True)
    print(f"📊 후보 발견: {len(results)}종목 → TOP {len(top10)} 선정", flush=True)
    print(f"💾 저장: {out_file}, {archive_file}", flush=True)
    print(f"\n🏆 TOP 10:", flush=True)
    for r in top10:
        print(f"  {r['rank']}. {r['name']} ({r['code']}) - {r['final_score']}점 - {r['signals']}", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"❌ 오류: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
