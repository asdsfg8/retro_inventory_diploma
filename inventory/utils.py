import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import logging

# Створюємо логер для цього файлу
logger = logging.getLogger('inventory.utils')

def fetch_pricecharting_data(raw_title, item_region=""):
    try:
        logger.info(f" СТАРТ ПОШУКУ: '{raw_title}' | Регіон: '{item_region}'")

        # Нормалізуємо регіон з бази (перетворюємо ntsc_j на NTSC-J)
        norm_region = item_region.upper().replace("_", "-").strip()
        logger.debug(f"Нормалізований регіон: '{norm_region}'")

        # 1. ПІДГОТОВКА ПЛАТФОРМИ
        target_platform = ""
        plat_match = re.search(r'\[(.*?)\]', raw_title)
        if plat_match: 
            target_platform = plat_match.group(1).lower().strip()
            logger.debug(f"Знайдено платформу в дужках: '{target_platform}'")
        else:
            logger.warning("Платформу в дужках НЕ ЗНАЙДЕНО!")

        aliases = {
            "ps1": "playstation", "psx": "playstation", "ps2": "playstation 2",
            "snes": "super nintendo", "sfc": "super famicom", "genesis": "sega genesis",
            "megadrive": "sega mega drive", "n64": "nintendo 64", "famicom": "nes", "fc": "nes"
        }
        base_platform = aliases.get(target_platform, target_platform)
        logger.debug(f"Базова платформа (після словника): '{base_platform}'")

        # 2. ФОРМУЄМО ЦІЛЬОВИЙ "SET"
        target_set_name = base_platform
        if norm_region == 'PAL':
            if base_platform == "super famicom": base_platform = "super nintendo"
            if base_platform == "sega genesis": base_platform = "sega mega drive"
            target_set_name = f"pal {base_platform}"
        elif norm_region == 'NTSC-J':
            if base_platform == "super nintendo": target_set_name = "super famicom"
            elif base_platform == "nes": target_set_name = "famicom"
            elif "genesis" in base_platform or "mega drive" in base_platform: target_set_name = "jp sega mega drive"
            elif base_platform not in ["super famicom", "famicom", ""]:
                target_set_name = f"jp {base_platform}"
        elif norm_region == 'NTSC-U' or norm_region == '':
            if base_platform == "super famicom": target_set_name = "super nintendo"
            if base_platform == "famicom": target_set_name = "nes"
            if base_platform == "sega mega drive": target_set_name = "sega genesis"

        # Нормалізуємо для надійності
        target_set_name = " ".join(target_set_name.split()).lower()
        logger.info(f" ЦІЛЬОВИЙ 'SET' ДЛЯ ПОШУКУ: '{target_set_name}'")

        # 3. ПОШУКОВИЙ ЗАПИТ
        clean_name = re.sub(r'\(\d{4}\)', '', raw_title)
        clean_name = re.sub(r'\[.*?\]', '', clean_name).strip()
        
        search_query = f"{clean_name} {base_platform}".strip()
        logger.debug(f"Відправляємо запит: '{search_query}'")
        
        url = f"https://www.pricecharting.com/search-products?q={urllib.parse.quote_plus(search_query)}&type=videogames"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        
        response = requests.get(url, headers=headers, timeout=10)
        logger.debug(f"Статус відповіді: {response.status_code}")
        
        if response.status_code != 200: 
            logger.error(f"СЕРВЕР ВІДХИЛИВ ЗАПИТ! Код: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')

        def extract_direct_page(page_soup, page_url):
            def get_val(pid):
                box = page_soup.find(id=pid)
                if box and box.find(class_="price"): 
                    return box.find(class_="price").get_text(strip=True).replace("$", "").replace(",", "")
                return "N/A"
            game_title = "Невідома гра"
            h1 = page_soup.find("h1", {"id": "product_name"})
            if h1: game_title = h1.get_text(strip=True)
            return {
                "title": game_title, "loose": get_val("used_price"), "cib": get_val("cib_price"),
                "new": get_val("new_price"), "console": target_set_name.title(), "url": page_url
            }

        # СЦЕНАРІЙ А: АВТО-РЕДІРЕКТ
        if soup.find("h1", {"id": "product_name"}):
            logger.debug("Сайт примусово перекинув на сторінку гри (Авто-редірект).")
            page_console = ""
            title_tag = soup.find("title")
            if title_tag and " Prices " in title_tag.text:
                try: page_console = title_tag.text.split(" Prices ")[1].split(" | ")[0].strip().lower()
                except: pass
            
            logger.debug(f"'Set' цієї сторінки: '{page_console}'")
            if page_console == target_set_name:
                logger.info(" Ідеальний збіг! Забираємо ціни (Авто-редірект).")
                return extract_direct_page(soup, response.url)
            else:
                logger.debug("'Set' не збігається. Пробуємо форсувати правильний URL...")
                game_slug = response.url.rstrip('/').split('/')[-1]
                forced_slug = target_set_name.replace(" ", "-")
                forced_url = f"https://www.pricecharting.com/game/{forced_slug}/{game_slug}"
                
                f_resp = requests.get(forced_url, headers=headers, timeout=5)
                if f_resp.status_code == 200:
                    f_soup = BeautifulSoup(f_resp.text, 'html.parser')
                    if f_soup.find(id="used_price"):
                        logger.info(" Форсування успішне!")
                        return extract_direct_page(f_soup, forced_url)
                logger.warning(" Форсування не вдалося.")
                return None

        # СЦЕНАРІЙ Б: ТАБЛИЦЯ
        table = soup.find("table", {"id": "games_table"})
        if table and table.find("tbody"):
            rows = table.find("tbody").find_all("tr")
            logger.debug(f"Отримано таблицю. Кількість результатів: {len(rows)}")
            
            for index, row in enumerate(rows):
                title_td = row.find("td", class_="title")
                if not title_td: continue
                
                title_a = title_td.find("a")
                row_title = title_a.get_text(strip=True) if title_a else "Невідомо"
                
                row_console = ""
                console_div = title_td.find("div", class_="console-in-title")
                if console_div and console_div.find("a"):
                    row_console = console_div.find("a").get_text(strip=True).lower()
                else:
                    console_td = row.find("td", class_="console")
                    if console_td: row_console = console_td.get_text(strip=True).lower()
                
                row_console_clean = " ".join(row_console.split())
                
                logger.debug(f"[{index+1}] Гра: '{row_title}' | Знадено: '{row_console_clean}' | Очікується: '{target_set_name}'")
                
                if row_console_clean == target_set_name:
                    logger.info(" БІНГО! Ідеальний збіг в таблиці. Забираємо дані.")
                    link = title_a['href'] if title_a else ""
                    g_url = "https://www.pricecharting.com" + link if link and not link.startswith("http") else link
                    
                    def get_td_price(class_name):
                        td = row.find("td", class_=class_name)
                        if td and td.find("span", class_="js-price"):
                            val = td.find("span", class_="js-price").get_text(strip=True).replace("$", "").replace(",", "")
                            return val if val else "N/A"
                        return "N/A"

                    return {
                        "title": row_title, "loose": get_td_price("used_price"),
                        "cib": get_td_price("cib_price"), "new": get_td_price("new_price"),
                        "console": target_set_name.title(), "url": g_url
                    }
                else:
                    logger.debug(" Відхилено (не збігається Set).")
            
            logger.warning(" В таблиці не знайдено потрібного 'Set'.")
        else:
            logger.warning(" Таблиці результатів немає на сторінці.")
            
        return None
    except requests.RequestException as e:
        logger.error(f"Помилка мережі при зверненні до PriceCharting: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.critical(f" КРИТИЧНА ПОМИЛКА: {e}", exc_info=True)
        return None