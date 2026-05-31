"""
SocPublic Bot — отдельный бот для мониторинга VK страницы smm.studia
и автоматического создания заданий на SocPublic при появлении новых постов.
"""

import requests
import random
import time
import os
import re
import json
import threading
from datetime import datetime, date

# ══════════════════════════════════════
#  VKONTAKTE
# ══════════════════════════════════════
VK_TOKEN          = "vk1.a.3l-M4WzpxupxkQ1LO5QEJKxhXtlyzgP6m9f7UnUXmtmOCGTp8Pj26J5cdb_hPqB8-wSrFsRTgUVIwcwZQK6iL-cx8p23NQnt65AcdJ1yWNnqj21ZKOWnSrPyKiUudvEjdCQjzBNoDSF2vq6AjPKbPtvP-kOGAo28Uhiet66MoYaXUU9UktA3zGcZfrf7V0nKu7eUkOqnHAU9a-GcfGIW0Q"
VK_API_URL        = "https://api.vk.com/method"
VK_VERSION        = "5.131"

# ══════════════════════════════════════
#  SOCPUBLIC
# ══════════════════════════════════════
SP_PAGE              = "smm.studia"       # VK страница для мониторинга
SP_CHECK_INTERVAL    = 60                 # проверка каждую минуту
SP_QTY_MIN           = 7                  # мин кол-во выполнений
SP_QTY_MAX           = 14                 # макс кол-во выполнений
SP_PRICE_PER_EXEC    = 1.3                # цена за 1 выполнение (с комиссией)

# Cookies SocPublic (можно переопределить через env при желании)
SP_SECRET     = os.environ.get("SP_SECRET",     "A4CBBC4D-1985-61D1-1705-2F9BBDDA8D6C")
SP_SESSION_ID = os.environ.get("SP_SESSION_ID", "EBAC23FB-6539-7F2A-0D8A-EA7D09CC3714")
SP_PARENT_ID  = os.environ.get("SP_PARENT_ID",  "3032573")

# ══════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════

def log(tag, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)

def load_state(filename, default=""):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return f.read().strip()
    return default

def save_state(filename, value):
    with open(filename, "w") as f:
        f.write(str(value))

# ══════════════════════════════════════
#  VK
# ══════════════════════════════════════

def get_vk_post(page):
    """Получает последний пост со страницы VK.
    Возвращает (post_id, post_url) или (None, None) при ошибке."""
    try:
        params = {
            "domain": page,
            "count": 1,
            "filter": "owner",
            "access_token": VK_TOKEN,
            "v": VK_VERSION,
        }
        resp = requests.get(f"{VK_API_URL}/wall.get", params=params, timeout=15)
        data = resp.json()
        
        if "error" in data:
            log("VK", f"❌ @{page}: {data['error'].get('error_msg', 'unknown')}")
            return None, None
        
        items = data.get("response", {}).get("items", [])
        if not items:
            return None, None
        
        post = items[0]
        owner_id = post["owner_id"]
        post_id  = post["id"]
        full_id  = f"{owner_id}_{post_id}"
        post_url = f"https://vk.com/wall{owner_id}_{post_id}"
        
        log("VK", f"✅ Последний пост @{page}: {post_url}")
        return full_id, post_url
    except Exception as e:
        log("VK", f"❌ @{page}: {e}")
        return None, None

# ══════════════════════════════════════
#  SOCPUBLIC
# ══════════════════════════════════════

def sp_create_task(post_url):
    """Создаёт задание на SocPublic для конкретного поста VK.
    Возвращает True/False."""
    
    # Описание задания (HTML) — точно как в шаблоне cURL, только подставлена ссылка
    description = (
        '<pre style="font-family: SFMono-Regular, Menlo, Monaco, Consolas, &quot;Liberation Mono&quot;, &quot;Courier New&quot;, monospace; '
        'font-size: 14.4px; margin-top: 0px; color: rgb(33, 37, 41); background-color: rgb(240, 240, 240);">\r\n'
        '<strong style="color: rgb(51, 51, 51); font-family: sans-serif, Arial, Verdana, &quot;Trebuchet MS&quot;; font-size: 13px;">'
        '<span style="color: rgb(84, 84, 84); font-family: Tahoma, Arial, &quot;Times New Roman&quot;, &quot;Trebuchet MS&quot;, Impact, sans-serif; '
        'font-size: 12px; background-color: rgb(249, 249, 249);">1. Написать  коммент &nbsp;к  посту   &nbsp; ( минимум 7 слов)</span></strong>\r\n'
        '</pre>\r\n\r\n'
        '<pre style="font-family: SFMono-Regular, Menlo, Monaco, Consolas, &quot;Liberation Mono&quot;, &quot;Courier New&quot;, monospace; '
        'font-size: 14.4px; margin-top: 0px; color: rgb(33, 37, 41); background-color: rgb(240, 240, 240);">\r\n'
        f'{post_url}</pre>\r\n'
        '<u><strong style="color: rgb(84, 84, 84); font-family: Tahoma, Arial, &quot;Times New Roman&quot;, &quot;Trebuchet MS&quot;, Impact, sans-serif; '
        'font-size: 12px; background-color: rgb(249, 249, 249);">'
        'Пожалуйста пишите интересно и строго по теме поста, можете использовать ChatGpt :)</strong></u><br />\r\n'
        '<br />\r\n<br />\r\n'
        '2. Поставить реакцию на пост и подписаться<br />\r\n'
        '3. Поделиться постом<br />\r\n'
        '4. Лайкуть пару других комментов'
    )
    
    approve_text = (
        '<strong><span style="color: rgb(200, 0, 0); font-family: Tahoma, Arial, &quot;Times New Roman&quot;, &quot;Trebuchet MS&quot;, Impact, sans-serif; '
        'font-size: 12px; background-color: rgb(249, 249, 249);">'
        '1. Скрин&nbsp; коммента<br />\r\n'
        '2. Ваше имя в Вк</span></strong>'
    )
    
    # Хвост из ссылки для названия (напр. wall426046437_1692)
    tail = post_url.rstrip("/").split("/")[-1]
    
    # Form data — точно как в cURL
    data = {
        'session': '',
        'name': f'Написать   в  Вконтакте  {tail}',
        'url': 'https://vk.com/',
        'url_count': '',
        'type': 'social',
        'description': description,
        'approve_type': 'hand',
        'approve_count': '1',
        'approve_text': approve_text,
        'approve_quest_0': '',
        'approve_answer_0_1': '',
        'approve_answer_0_count': '1',
        'approve_quest_1': '',
        'approve_answer_1_1': '',
        'approve_answer_1_count': '1',
        'day_1': '1', 'day_2': '1', 'day_3': '1', 'day_4': '1',
        'day_5': '1', 'day_6': '1', 'day_7': '1',
        'time_6_9_flag':  '1', 'time_6_9':   'неогр.',
        'time_9_12_flag': '1', 'time_9_12':  'неогр.',
        'time_12_15_flag':'1', 'time_12_15': 'неогр.',
        'time_15_18_flag':'1', 'time_15_18': 'неогр.',
        'time_18_21_flag':'1', 'time_18_21': 'неогр.',
        'time_21_24_flag':'1', 'time_21_24': 'неогр.',
        'time_0_3_flag':  '1', 'time_0_3':   'неогр.',
        'time_3_6_flag':  '1', 'time_3_6':   'неогр.',
        'timeout': '0',
        'work_filter': 'null',
        'family_filter': 'null',
        'gender_filter': 'null',
        'age_from': '0',
        'age_to': '999',
        'geo_filter': '0',
        'per_24': '0',
        'repeat_value': '-1',
        'work_time': '3600',
        'user_xp': '0',
        'ip_filter': 'all',
        'captcha_type': 'no',
        'ref_filter': '0',
        'price_user': '1',
        'auto_funds': '0',
    }
    
    cookies = {
        'secret':     SP_SECRET,
        'parent_id':  SP_PARENT_ID,
        'session_id': SP_SESSION_ID,
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,hy;q=0.8,ru;q=0.7',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://socpublic.com',
        'Referer': 'https://socpublic.com/account/task_adv_add.html',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        log("SP", f"📤 Создаю задание для {post_url}")
        resp = requests.post(
            'https://socpublic.com/account/task_adv_add.html',
            headers=headers,
            cookies=cookies,
            data=data,
            timeout=30,
            allow_redirects=False,
        )
        log("SP", f"📥 Status: {resp.status_code} | размер ответа: {len(resp.text)}")
        
        # Успех: 302 редирект на task_view.html?id=NNNN или task_adv_list
        if resp.status_code in (302, 303):
            location = resp.headers.get("Location", "")
            log("SP", f"✅ Задание создано! Redirect → {location}")
            # Пытаемся вытащить id из Location
            m = re.search(r'id=(\d+)', location)
            if m:
                return m.group(1)
            return "created"  # создано, но id не в редиректе — найдём в списке
        
        # 200 с возможной ошибкой
        if resp.status_code == 200:
            body = resp.text
            body_lower = body.lower()
            
            if 'войти' in body_lower[:5000] or 'авторизац' in body_lower[:5000]:
                log("SP", f"❌ Cookies устарели — обнови SP_SESSION_ID и SP_SECRET в Railway")
                return None
            
            # Ищем сообщения об ошибках в ответе
            error_patterns = [
                r'<div[^>]*class="[^"]*alert[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*danger[^"]*"[^>]*>(.*?)</div>',
                r'<span[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</span>',
                r'<li[^>]*class="[^"]*error[^"]*"[^>]*>(.*?)</li>',
            ]
            found_errors = []
            for pat in error_patterns:
                for m in re.finditer(pat, body, re.DOTALL | re.IGNORECASE):
                    txt = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                    txt = re.sub(r'\s+', ' ', txt)
                    if txt and len(txt) > 2:
                        found_errors.append(txt[:200])
            
            if found_errors:
                log("SP", f"❌ Ошибки формы: {' | '.join(found_errors[:5])}")
            else:
                log("SP", f"⚠️  Status 200, но явных ошибок не найдено. Задание НЕ создано (вернулась форма).")
            
            return None
        
        log("SP", f"❌ Неожиданный статус: {resp.status_code}")
        return None
    except Exception as e:
        log("SP", f"❌ Ошибка: {e}")
        return None

def sp_cookies():
    return {
        'secret':     SP_SECRET,
        'parent_id':  SP_PARENT_ID,
        'session_id': SP_SESSION_ID,
    }

def sp_get_latest_task_id():
    """Запрашивает список заданий и возвращает id самого верхнего (свежесозданного).
    Ищет id ТОЛЬКО в ссылках 'включить' (act=yes) — это надёжный паттерн."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://socpublic.com/account/task_adv_list.html',
    }
    try:
        resp = requests.get(
            'https://socpublic.com/account/task_adv_list.html?task_type=&folder_id=0&page=1',
            headers=headers, cookies=sp_cookies(), timeout=30,
        )
        if resp.status_code != 200:
            log("SP", f"⚠️  Список заданий: status {resp.status_code}")
            return None
        # Ищем id ТОЛЬКО в ссылках "включить" (act=yes&id=NNN)
        # Это кнопки запуска у неактивных заданий — именно они нам нужны
        ids = re.findall(r'act=yes&id=(\d+)', resp.text)
        if not ids:
            log("SP", f"⚠️  Не нашёл заданий с кнопкой 'включить' (act=yes)")
            return None
        # Самый большой id = самое новое задание
        latest = max(ids, key=lambda x: int(x))
        log("SP", f"🔍 Найдено заданий к запуску: {len(ids)}, новейшее id={latest}")
        return latest
    except Exception as e:
        log("SP", f"❌ Ошибка получения списка: {e}")
        return None

def sp_make_fund(task_id, quantity):
    """Пополняет баланс задания. fund_value = quantity * цена."""
    fund_value = round(quantity * SP_PRICE_PER_EXEC, 1)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://socpublic.com',
        'Referer': 'https://socpublic.com/account/task_adv_list.html',
        'X-Requested-With': 'XMLHttpRequest',
    }
    data = {
        'task_id': str(task_id),
        'fund_value': str(fund_value),
        'fund_action': 'credit',
        'session': '',
    }
    try:
        log("SP", f"💰 Пополняю задание {task_id} на {fund_value} руб ({quantity} вып.)")
        resp = requests.post(
            'https://socpublic.com/task.ajax?act=make_fund',
            headers=headers, cookies=sp_cookies(), data=data, timeout=30,
        )
        log("SP", f"📥 Пополнение: status {resp.status_code} | {resp.text[:200]}")
        
        if resp.status_code != 200:
            return False
        
        # SocPublic отвечает 200 даже при ошибке — проверяем тело
        # Успех: {"status":"success"...}, ошибка: {"status":"fail","text":"..."}
        try:
            j = resp.json()
            if j.get("status") == "fail":
                log("SP", f"❌ Пополнение отклонено: {j.get('text', 'неизвестно')}")
                return False
        except Exception:
            pass  # не JSON — считаем по статусу
        
        return True
    except Exception as e:
        log("SP", f"❌ Ошибка пополнения: {e}")
        return False

def sp_start_task(task_id):
    """Запускает задание (act=yes)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://socpublic.com/account/task_adv_list.html',
    }
    url = f'https://socpublic.com/account/task_adv_list.html?task_type=&act=yes&id={task_id}&page=1&folder_id=0&session='
    try:
        log("SP", f"▶️  Запускаю задание {task_id}")
        resp = requests.get(
            url, headers=headers, cookies=sp_cookies(), timeout=30, allow_redirects=False,
        )
        log("SP", f"📥 Старт: status {resp.status_code}")
        # 302 = успешный редирект после старта
        if resp.status_code in (200, 302, 303):
            return True
        return False
    except Exception as e:
        log("SP", f"❌ Ошибка старта: {e}")
        return False

def sp_full_pipeline(post_url):
    """Полный цикл: создать → найти id → пополнить → запустить.
    Возвращает True если задание успешно создано (даже если старт не удался)."""
    # 1. Создать
    result = sp_create_task(post_url)
    if not result:
        return False
    
    # 2. Определить task_id
    if result.isdigit():
        task_id = result
    else:
        # id не пришёл в редиректе — берём верхнее из списка
        time.sleep(2)
        task_id = sp_get_latest_task_id()
        if not task_id:
            log("SP", f"⚠️  Задание создано, но не смог определить task_id — пополни/запусти вручную")
            return True  # создано, дальше вручную
    
    log("SP", f"🆔 task_id = {task_id}")
    
    # ЗАЩИТА: task_id не должен совпадать с parent_id (это была бы ошибка парсинга)
    if str(task_id) == str(SP_PARENT_ID):
        log("SP", f"🛑 task_id совпал с parent_id ({SP_PARENT_ID}) — это ошибка! Пополни/запусти вручную")
        return True
    
    # 3. Пополнить
    quantity = random.randint(SP_QTY_MIN, SP_QTY_MAX)
    time.sleep(2)
    funded = sp_make_fund(task_id, quantity)
    if not funded:
        log("SP", f"⚠️  Пополнение не удалось — пополни/запусти задание {task_id} вручную")
        return True
    
    # 4. Запустить
    time.sleep(2)
    started = sp_start_task(task_id)
    if started:
        log("SP", f"🎉 Задание {task_id} создано, пополнено ({quantity} вып.) и запущено!")
    else:
        log("SP", f"⚠️  Задание {task_id} пополнено, но старт не удался — запусти вручную")
    return True

# ══════════════════════════════════════
#  ПОТОК SOCPUBLIC
# ══════════════════════════════════════

def socpublic_bot():
    log("SocPublic", f"💬 Запущен | Страница: vk.com/{SP_PAGE} | Интервал: {SP_CHECK_INTERVAL} сек")
    
    state_file = "sp_last_post.txt"
    last_id = load_state(state_file)
    
    # Первый запуск — запомнить последний пост
    if not last_id:
        post_id, _ = get_vk_post(SP_PAGE)
        if post_id:
            last_id = post_id
            save_state(state_file, last_id)
            log("SocPublic", f"📌 @{SP_PAGE} — последний пост: #{post_id}. Жду новые...")
    else:
        log("SocPublic", f"📋 Последний обработанный пост: #{last_id}")
    
    while True:
        time.sleep(SP_CHECK_INTERVAL)
        try:
            latest_id, post_url = get_vk_post(SP_PAGE)
            if not latest_id:
                continue
            
            if latest_id != last_id:
                log("SocPublic", f"🆕 Новый пост: {post_url}")
                ok = sp_full_pipeline(post_url)
                if ok:
                    last_id = latest_id
                    save_state(state_file, last_id)
                    log("SocPublic", f"💾 Запомнил пост #{last_id}")
                else:
                    log("SocPublic", f"⏸️  Задание не создалось — попробую снова через минуту")
            else:
                log("SocPublic", f"🔍 @{SP_PAGE} — нет новых постов (последний: #{last_id})")
        except Exception as e:
            log("SocPublic", f"❌ Ошибка: {e}")

# ══════════════════════════════════════
#  MAIN
# ══════════════════════════════════════

def main():
    log("MAIN", "🚀 SocPublic бот запущен!")
    
    threads = [
        threading.Thread(target=socpublic_bot, daemon=True),
    ]
    for t in threads:
        t.start()
    
    # Держим главный поток живым
    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
