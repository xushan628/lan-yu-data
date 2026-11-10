# -*- coding: utf-8 -*-
"""
一次性采集：抖音 7 赛道 + 亚马逊 4 类目 → data/latest.json
在 GitHub Actions 里跑（需要外网）。

环境变量：
    TIKHUB_API_KEY   抖音数据（必需，没配就只跑亚马逊）

用法：
    python scripts/scrape_all.py
    python scripts/scrape_all.py --skip-amazon     # 只跑抖音
    python scripts/scrape_all.py --skip-douyin     # 只跑亚马逊
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

DOUYIN_API = 'https://api.tikhub.io/api/v1/douyin/billboard/fetch_hot_total_video_list'
OUT = 'data/latest.json'

TRACKS = [
    ('情感语录', '情感语录'),
    ('不露脸', '沉浸式'),
    ('打赏 / 直播', '直播'),
    ('拆书 / 知识', '读书'),
    ('服饰推荐', '穿搭'),
    ('历史类', '历史'),
    ('抖音小店', '带货'),
]
PER_TRACK = 5
AMZ_CATS = [
    ('宠物用品', 'pet-supplies'),
    ('厨房用品', 'kitchen'),
    ('家居收纳', 'home-garden'),
    ('运动户外', 'sporting-goods'),
]
AMZ_TOP = 20

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


# ============ 抖音 ============
def douyin_call(keyword, key):
    body = json.dumps({
        'keyword': keyword, 'page': 1, 'page_size': PER_TRACK,
        'date_window': 24, 'sub_type': 1001,
    }).encode('utf-8')
    req = urllib.request.Request(
        DOUYIN_API, data=body, method='POST',
        headers={
            'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'lan-yu-workbench/1.0',
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def pick_objs(d):
    for path in (('data', 'data', 'objs'), ('data', 'objs')):
        cur, ok = d, True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return cur
    return []


def douyin_item(o, i):
    aid = str(o.get('item_id') or '')
    title = (o.get('item_title') or '').replace('\n', ' ').strip()
    if len(title) > 90:
        title = title[:90] + '…'
    return {
        'rank': i + 1, 'title': title,
        'author': (o.get('nick_name') or '').strip(),
        'plays': o.get('play_cnt'), 'likes': o.get('like_cnt'),
        'fansGain': o.get('follow_cnt'), 'fans': o.get('fans_cnt'),
        'likeRate': round((o.get('like_rate') or 0) * 100, 2),
        'awemeId': aid,
        'url': ('https://www.douyin.com/video/' + aid) if aid else '',
    }


def scrape_douyin():
    key = os.environ.get('TIKHUB_API_KEY')
    if not key:
        print('⚠️ 没有 TIKHUB_API_KEY，跳过抖音')
        return None
    tracks, pending = [], []
    for name, kw in TRACKS:
        try:
            objs = pick_objs(douyin_call(kw, key))
            if not objs:
                pending.append(name)
                print('  ⚠️ %-12s 无数据' % name)
                continue
            items = [douyin_item(o, i) for i, o in enumerate(objs[:PER_TRACK])]
            tracks.append({'track': name, 'keyword': kw, 'items': items})
            print('  ✅ %-12s %d 条 · 榜首 %s（%s 播放）'
                  % (name, len(items), items[0]['author'], items[0]['plays']))
        except urllib.error.HTTPError as e:
            pending.append(name)
            print('  ❌ %-12s HTTP %s' % (name, e.code))
        except Exception as e:
            pending.append(name)
            print('  ❌ %-12s %s' % (name, type(e).__name__))
        time.sleep(0.6)
    if not tracks:
        return None
    return {
        'date': time.strftime('%Y-%m-%d'),
        'fetchedAt': time.strftime('%Y-%m-%d %H:%M'),
        'source': 'TikHub 抖音视频热榜（近 24 小时，按赛道关键词过滤）',
        'note': '排序为平台热度分（综合播放、互动、涨粉），不是单纯按播放量。',
        'tracks': tracks, 'pending': pending,
    }


# ============ 亚马逊 ============
def parse_price(text):
    if not text:
        return None
    t = text.strip().replace(',', '')
    t = re.sub(r'[^\d.]', '', t) if '.' in t else re.sub(r'[^\d]', '', t)
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    if '.' not in text and v > 1000:
        v = v / 100
    return round(v, 2)


def parse_int(text):
    if not text:
        return None
    t = re.sub(r'[^\d]', '', text)
    return int(t) if t else None


def scrape_amazon():
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print('⚠️ 缺 requests / beautifulsoup4，跳过亚马逊')
        return None

    prev = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding='utf-8') as f:
                od = json.load(f).get('amazon') or {}
            prev = {c['slug']: c for c in od.get('categories', [])}
        except Exception:
            prev = {}

    headers = {'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'}
    cats = []
    for name, slug in AMZ_CATS:
        url = 'https://www.amazon.com/gp/bestsellers/%s/' % slug
        try:
            r = requests.get(url, headers=headers, timeout=45)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            cards = soup.select('div[id^="gridItemRoot"]')
            items = []
            for card in cards[:AMZ_TOP]:
                bdg = card.select_one('.zg-bdg-text')
                rank = parse_int(bdg.get_text()) if bdg else None
                tel = card.select_one('div[class*="line-clamp"]') or card.select_one('.p13n-sc-truncate')
                title = tel.get_text(strip=True) if tel else ''
                if not title:
                    continue
                pel = card.select_one('span[class*="p13n-sc-price"]') or card.select_one('span.a-offscreen')
                price = parse_price(pel.get_text()) if pel else None
                rel = card.select_one('span.a-icon-alt')
                rating = None
                if rel:
                    m = re.search(r'([\d.]+)', rel.get_text())
                    rating = float(m.group(1)) if m else None
                vel = card.select_one('span.a-size-small')
                reviews = parse_int(vel.get_text()) if vel else None
                a = card.select_one('a[href*="/dp/"]')
                asin = ''
                if a:
                    m = re.search(r'/dp/([A-Z0-9]{10})', a.get('href', ''))
                    asin = m.group(1) if m else ''
                items.append({'rank': rank or len(items) + 1, 'title': title[:80],
                              'asin': asin, 'price': price,
                              'rating': rating, 'reviews': reviews})
            if not items:
                raise ValueError('没解析到商品（可能被反爬拦）')
            cats.append({'cat': name, 'slug': slug, 'items': items})
            print('  ✅ %-10s %d 条' % (name, len(items)))
        except Exception as e:
            print('  ❌ %-10s %s' % (name, type(e).__name__))
            if prev.get(slug, {}).get('items'):
                cats.append(prev[slug])
                print('     ↳ 沿用上次 %d 条' % len(prev[slug]['items']))
        time.sleep(1.5)

    if not cats:
        return None
    return {
        'date': time.strftime('%Y-%m-%d'),
        'fetchedAt': time.strftime('%Y-%m-%d %H:%M'),
        'source': 'Amazon Best Sellers（公开页面解析）',
        'note': 'Actions 是机房 IP，可能被反爬；失败会沿用上次数据。',
        'categories': cats,
    }


def main():
    skip_amz = '--skip-amazon' in sys.argv
    skip_dy = '--skip-douyin' in sys.argv

    print('== 抖音 ==')
    dy = None if skip_dy else scrape_douyin()
    print('== 亚马逊 ==')
    amz = None if skip_amz else scrape_amazon()

    if not dy and not amz:
        print('\n❌ 两个源都没抓到，不写文件（保留上次数据）')
        return 1

    os.makedirs('data', exist_ok=True)
    payload = {
        'version': 1,
        'generatedAt': time.strftime('%Y-%m-%d %H:%M'),
        'generatedDate': time.strftime('%Y-%m-%d'),
        'douyin': dy,
        'amazon': amz,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print('\n写入 %s' % OUT)
    if dy:
        print('  抖音 %d 赛道 %d 条' % (len(dy['tracks']), sum(len(t['items']) for t in dy['tracks'])))
        if dy.get('pending'):
            print('  未取到：%s' % '、'.join(dy['pending']))
    if amz:
        print('  亚马逊 %d 类目 %d 条'
              % (len(amz['categories']), sum(len(c['items']) for c in amz['categories'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
