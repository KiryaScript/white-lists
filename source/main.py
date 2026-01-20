from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import defaultdict
from github import GithubException
from github import Github, Auth
from datetime import datetime
import concurrent.futures
import urllib.parse
import threading
import zoneinfo
import requests
import urllib3
import base64
import time
import html
import json
import re
import os
import math

# -------------------- ЛОГИРОВАНИЕ --------------------
LOGS_BY_FILE: dict[int, list[str]] = defaultdict(list)
_LOG_LOCK = threading.Lock()
_UPDATED_FILES_LOCK = threading.Lock()

_GITHUBMIRROR_INDEX_RE = re.compile(r"githubmirror/(\d+)\.txt")
updated_files = set()

def _extract_index(msg: str) -> int:
    m = _GITHUBMIRROR_INDEX_RE.search(msg)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0

def log(message: str):
    idx = _extract_index(message)
    with _LOG_LOCK:
        LOGS_BY_FILE[idx].append(message)

# Часовой пояс
try:
    zone = zoneinfo.ZoneInfo("Europe/Moscow")
except Exception:
    zone = None

thistime = datetime.now(zone) if zone else datetime.now()
offset = thistime.strftime("%H:%M | %d.%m.%Y")

# -------------------- НАСТРОЙКИ --------------------
GITHUB_TOKEN = os.environ.get("MY_TOKEN")
REPO_NAME = "KiryaScript/white-lists" # Убедись, что тут твой репозиторий

if GITHUB_TOKEN:
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
else:
    print("❌ ОШИБКА: Токен не найден.")
    g = Github()

try:
    REPO = g.get_repo(REPO_NAME)
except Exception as e:
    print(f"❌ ОШИБКА доступа: {e}")
    REPO = None

# Проверка лимитов
try:
    remaining, limit = g.rate_limiting
    if remaining < 100:
        log(f"⚠️ Лимиты API: {remaining}/{limit}")
    else:
        log(f"ℹ️ Лимиты API: {remaining}/{limit}")
except:
    pass

if not os.path.exists("githubmirror"):
    os.mkdir("githubmirror")

# Основные источники (1-25)
URLS = [
    "https://github.com/sakha1370/OpenRay/raw/refs/heads/main/output/all_valid_proxies.txt", #1
    "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vl.txt", #2
    "https://raw.githubusercontent.com/yitong2333/proxy-minging/refs/heads/main/v2ray.txt", #3
    "https://raw.githubusercontent.com/acymz/AutoVPN/refs/heads/main/data/V2.txt", #4
    "https://raw.githubusercontent.com/miladtahanian/V2RayCFGDumper/refs/heads/main/config.txt", #5
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt", #6
    "https://github.com/Epodonios/v2ray-configs/raw/main/Splitted-By-Protocol/trojan.txt", #7
    "https://raw.githubusercontent.com/YasserDivaR/pr0xy/refs/heads/main/ShadowSocks2021.txt", #8
    "https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/vless.txt", #9
    "https://raw.githubusercontent.com/mheidari98/.proxy/refs/heads/main/vless", #10
    "https://raw.githubusercontent.com/youfoundamin/V2rayCollector/main/mixed_iran.txt", #11
    "https://raw.githubusercontent.com/mheidari98/.proxy/refs/heads/main/all", #12
    "https://github.com/Kwinshadow/TelegramV2rayCollector/raw/refs/heads/main/sublinks/mix.txt", #13
    "https://github.com/LalatinaHub/Mineral/raw/refs/heads/master/result/nodes", #14
    "https://raw.githubusercontent.com/miladtahanian/multi-proxy-config-fetcher/refs/heads/main/configs/proxy_configs.txt", #15
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/refs/heads/main/sub", #16
    "https://github.com/MhdiTaheri/V2rayCollector_Py/raw/refs/heads/main/sub/Mix/mix.txt", #17
    "https://github.com/Epodonios/v2ray-configs/raw/main/Splitted-By-Protocol/vmess.txt", #18
    "https://github.com/MhdiTaheri/V2rayCollector/raw/refs/heads/main/sub/mix", #19
    "https://github.com/Argh94/Proxy-List/raw/refs/heads/main/All_Config.txt", #20
    "https://raw.githubusercontent.com/shabane/kamaji/master/hub/merged.txt", #21
    "https://raw.githubusercontent.com/wuqb2i4f/xray-config-toolkit/main/output/base64/mix-uri", #22
    "https://raw.githubusercontent.com/AzadNetCH/Clash/refs/heads/main/AzadNet.txt", #23
    "https://raw.githubusercontent.com/STR97/STRUGOV/refs/heads/main/STR.BYPASS#STR.BYPASS%F0%9F%91%BE", #24
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt", #25
]

# Источники для спец-конфигов (26, 27, 28)
EXTRA_URLS_FOR_SPLIT = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_nolite.txt",
    "https://raw.githubusercontent.com/EtoNeYaProject/etoneyaproject.github.io/refs/heads/main/2",
    "https://s3c3.001.gpucloud.ru/dixsm/htxml",
]

# Формируем пути для 1-25
REMOTE_PATHS = [f"githubmirror/{i+1}.txt" for i in range(len(URLS))]
LOCAL_PATHS = [f"githubmirror/{i+1}.txt" for i in range(len(URLS))]

# Добавляем пути для 26, 27, 28 (Разбитые части)
for i in range(26, 29):
    REMOTE_PATHS.append(f"githubmirror/{i}.txt")
    LOCAL_PATHS.append(f"githubmirror/{i}.txt")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def _build_session(max_pool_size: int) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=max_pool_size,
        pool_maxsize=max_pool_size,
        max_retries=Retry(total=1, backoff_factor=0.2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("HEAD", "GET", "OPTIONS")),
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": CHROME_UA})
    return session

REQUESTS_SESSION = _build_session(max_pool_size=16)

def fetch_data(url: str, timeout: int = 10, max_attempts: int = 3) -> str:
    for attempt in range(1, max_attempts + 1):
        try:
            modified_url = url
            verify = True
            if attempt == 2: verify = False
            elif attempt == 3:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme == "https": modified_url = parsed._replace(scheme="http").geturl()
                verify = False
            
            response = REQUESTS_SESSION.get(modified_url, timeout=timeout, verify=verify)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as exc:
            if attempt < max_attempts: continue
            raise exc

def save_to_local_file(path, content):
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)

def extract_source_name(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        path_parts = parsed.path.split('/')
        if len(path_parts) > 2: return f"{path_parts[1]}/{path_parts[2]}"
        return parsed.netloc
    except: return "Источник"

def update_readme_table():
    if REPO is None: return
    try:
        try:
            readme_file = REPO.get_contents("README.md")
            old_content = readme_file.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404: return
            log(f"⚠️ Ошибка чтения README.md: {e}")
            return

        time_part, date_part = offset.split(" | ")
        table_header = "| № | Файл | Источник | Время | Дата |\n|--|--|--|--|--|"
        table_rows = []
        
        # Проходим по всем файлам (теперь их 28)
        for i, remote_path in enumerate(REMOTE_PATHS, 1):
            filename = f"{i}.txt"
            raw_file_url = f"https://github.com/{REPO_NAME}/raw/refs/heads/main/githubmirror/{i}.txt"
            
            # Логика определения источника
            if i <= 25:
                url = URLS[i-1]
                source_name = extract_source_name(url)
                source_column = f"[{source_name}]({url})"
            else:
                # Для 26, 27, 28
                part_num = i - 25
                source_name = f"Обход блокировок (Часть {part_num})"
                source_column = f"[{source_name}]({raw_file_url})"
            
            if i in updated_files:
                update_time = time_part
                update_date = date_part
            else:
                pattern = rf"\|\s*{i}\s*\|\s*\[`{filename}`\].*?\|.*?\|\s*(.*?)\s*\|\s*(.*?)\s*\|"
                match = re.search(pattern, old_content)
                if match:
                    update_time = match.group(1).strip()
                    update_date = match.group(2).strip()
                else:
                    update_time = "Никогда"
                    update_date = "Никогда"
            
            table_rows.append(f"| {i} | [`{filename}`]({raw_file_url}) | {source_column} | {update_time} | {update_date} |")

        new_table = table_header + "\n" + "\n".join(table_rows)
        # Обновленный паттерн поиска таблицы
        table_pattern = r"\| № \| Файл \| Источник \| Время \| Дата \|[\s\S]*?\|--\|--\|--\|--\|--\|[\s\S]*?(\n\n## |$)"
        new_content = re.sub(table_pattern, new_table + r"\1", old_content)

        if new_content != old_content:
            REPO.update_file(path="README.md", message=f"📝 Table Update: {offset}", content=new_content, sha=readme_file.sha)
            log("📝 README.md обновлен")
    except Exception as e:
        log(f"⚠️ Ошибка README: {e}")

def upload_to_github(local_path, remote_path):
    if REPO is None: return
    if not os.path.exists(local_path): return

    with open(local_path, "r", encoding="utf-8") as file:
        content = file.read()

    try:
        file_in_repo = REPO.get_contents(remote_path)
        remote_content = file_in_repo.decoded_content.decode("utf-8", errors="replace")
        
        if content == remote_content:
            log(f"🔄 Нет изменений в конфигах для {remote_path}")
            return

        REPO.update_file(path=remote_path, message=f"🚀 Update {os.path.basename(remote_path)}: {offset}", content=content, sha=file_in_repo.sha)
        log(f"🚀 Обновлен {remote_path}")
        with _UPDATED_FILES_LOCK: updated_files.add(int(remote_path.split('/')[1].split('.')[0]))

    except GithubException as e:
        if e.status == 404:
            REPO.create_file(path=remote_path, message=f"🆕 Create {os.path.basename(remote_path)}: {offset}", content=content)
            log(f"🆕 Создан {remote_path}")
            with _UPDATED_FILES_LOCK: updated_files.add(int(remote_path.split('/')[1].split('.')[0]))
        else:
            log(f"⚠️ Ошибка GitHub: {e}")

def download_and_save(idx):
    url = URLS[idx]
    local_path = LOCAL_PATHS[idx]
    try:
        data = fetch_data(url)
        data, _ = filter_insecure_configs(local_path, data)
        save_to_local_file(local_path, data)
        return local_path, REMOTE_PATHS[idx]
    except Exception as e:
        log(f"⚠️ Ошибка {url}: {e}")
        return None

INSECURE_PATTERN = re.compile(r'(?:[?&;]|3%[Bb])(allowinsecure|allow_insecure|insecure)=(?:1|true|yes)(?:[&;#]|$|(?=\s|$))', re.IGNORECASE)

def filter_insecure_configs(local_path, data, log_enabled=True):
    result = []
    lines = data.splitlines()
    for line in lines:
        processed = urllib.parse.unquote(html.unescape(line.strip()))
        if not INSECURE_PATTERN.search(processed):
            result.append(line)
    return "\n".join(result), len(lines) - len(result)

def create_split_configs():
    """
    Генерирует файлы 26, 27, 28 путем сбора конфигов, фильтрации и разбиения на 3 части.
    """
    sni_domains = [
        "gosuslugi.ru", "vk.com", "vk.ru", "yandex.ru", "ya.ru", "mail.ru", 
        "sberbank.ru", "tbank.ru", "ozon.ru", "wildberries.ru", "avito.ru", 
        "rutube.ru", "dzen.ru", "2gis.ru", "mos.ru", "fssp.gov.ru", "nalog.ru", 
        "cbr.ru", "kremlin.ru", "government.ru", "pfr.gov.ru", "mvd.ru",
        # Сюда можно вернуть полный список доменов, который был раньше
    ]
    
    all_configs = []
    
    # 1. Собираем конфиги из файлов 1-25
    for i in range(len(URLS)):
        path = LOCAL_PATHS[i]
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                all_configs.extend([line.strip() for line in f if line.strip()])

    # 2. Добавляем конфиги из EXTRA_URLS
    for url in EXTRA_URLS_FOR_SPLIT:
        try:
            data = fetch_data(url)
            filtered, _ = filter_insecure_configs("extra", data, log_enabled=False)
            all_configs.extend([line.strip() for line in filtered.splitlines() if line.strip()])
        except:
            pass
            
    # 3. Фильтрация и дедупликация
    unique_configs = set()
    filtered_configs = []
    
    for config in all_configs:
        if config in unique_configs: continue
        
        is_valid = False
        try:
            decoded = urllib.parse.unquote(config)
            for domain in sni_domains:
                if domain in decoded:
                    is_valid = True
                    break
        except:
            pass
            
        if is_valid:
            unique_configs.add(config)
            filtered_configs.append(config)
            
    # 4. Разбиение на 3 части (26, 27, 28)
    if filtered_configs:
        total = len(filtered_configs)
        chunk_size = math.ceil(total / 3)
        
        # Разбиваем список на чанки
        chunks = [filtered_configs[i:i + chunk_size] for i in range(0, total, chunk_size)]
        
        # Убедимся, что у нас ровно 3 части (даже если данных мало)
        while len(chunks) < 3:
            chunks.append([])

        # Сохраняем части
        for i, chunk in enumerate(chunks):
            file_num = 26 + i  # 26, 27, 28
            filename = f"githubmirror/{file_num}.txt"
            content = "\n".join(chunk)
            save_to_local_file(filename, content)
            log(f"✅ Сгенерирован {file_num}.txt (Часть {i+1}): {len(chunk)} конфигов")
    else:
        log("⚠️ Не удалось найти конфиги для разбиения (26-28)")
        # Создаем пустые файлы, чтобы не ломать логику
        for i in range(26, 29):
            save_to_local_file(f"githubmirror/{i}.txt", "")

def main():
    log(f"⏰ Запуск: {offset}")
    
    # 1. Скачиваем 1-25
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(download_and_save, i): i for i in range(len(URLS))}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            
    # 2. Генерируем 26, 27, 28
    create_split_configs()
    
    # 3. Загружаем ВСЕ (1-28) на GitHub
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for i in range(len(LOCAL_PATHS)):
            futures.append(executor.submit(upload_to_github, LOCAL_PATHS[i], REMOTE_PATHS[i]))
        concurrent.futures.wait(futures)

    # 4. Обновляем таблицу
    update_readme_table()
    
    # Вывод логов
    sorted_logs = []
    sorted_logs.extend(LOGS_BY_FILE[0])
    for i in range(1, 30): # С запасом
        if i in LOGS_BY_FILE:
            sorted_logs.extend(LOGS_BY_FILE[i])
            
    print("\n".join(sorted_logs))

if __name__ == "__main__":
    main()
