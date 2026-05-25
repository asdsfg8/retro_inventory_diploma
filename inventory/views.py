import requests
import re
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.http import JsonResponse, HttpResponseForbidden
from django.core.cache import cache
from django.db.models import Sum, Count, Avg
from django.utils import timezone  # Обов'язково для збереження часу!

from .models import CollectionItem, Game, Location, Room, StorageUnit, ItemImage
from .forms import CollectionItemForm, LocationForm, RoomForm, StorageUnitForm
from .utils import fetch_pricecharting_data

from .forms import CustomUserCreationForm, CollectionItemForm, LocationForm, RoomForm, StorageUnitForm

# --- НАЛАШТУВАННЯ ЛОГЕРА ---
logger = logging.getLogger('inventory.views')

# --- РЕЄСТРАЦІЯ ---
def register(request):
    if request.user.is_authenticated:
        return redirect('inventory:collection_list')

    if request.method == 'POST':
        # Використовуємо нашу кастомну форму
        form = CustomUserCreationForm(request.POST) 
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info(f" Новий користувач зареєструвався: {user.username}")
            return redirect('inventory:collection_list')
    else:
        # Використовуємо нашу кастомну форму
        form = CustomUserCreationForm() 
    
    return render(request, 'registration/register.html', {'form': form})

# --- ГОЛОВНА СТОРІНКА КОЛЕКЦІЇ ---
@login_required
def collection_list(request):
    items = CollectionItem.objects.filter(user=request.user).select_related('game', 'storage')
    return render(request, 'inventory/collection_list.html', {'items': items})

def get_igdb_token(client_id, client_secret):
    token = cache.get('igdb_access_token')
    if token:
        return token
    auth_url = f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials"
    try:
        response = requests.post(auth_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            cache.set('igdb_access_token', token, timeout=expires_in - 300)
            return token
    except Exception as e:
        # ЗАМІНА PRINT НА LOGGER
        logger.error(f" Помилка підключення до Twitch: {e}", exc_info=True)
    return None

# --- AJAX ПОШУК ІГОР ЧЕРЕЗ API ---
@login_required
def search_games(request):
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse([], safe=False)

    local_games = Game.objects.filter(title__icontains=query)[:5]
    results = [{"value": game.title, "text": game.title} for game in local_games]

    #API ключі до IGDB детальніше: https://api-docs.igdb.com/#getting-started
    CLIENT_ID = 'Введіть сюди свій CLIENT_ID IGDB' 
    CLIENT_SECRET = 'Введіть сюди свій CLIENT_SECRET від IGDB'
    
    token = get_igdb_token(CLIENT_ID, CLIENT_SECRET)
    
    if token:
        url = "https://api.igdb.com/v4/games"
        headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        body = f'search "{query}"; fields name, release_dates.y, release_dates.platform.name, release_dates.region; limit 100;'
        try:
            response = requests.post(url, headers=headers, data=body.encode('utf-8'), timeout=5)
            if response.status_code == 200:
                data = response.json()
                igdb_regions = {1: 'Europe', 2: 'North America', 3: 'Australia', 4: 'New Zealand', 5: 'Japan', 6: 'China', 7: 'Asia', 8: 'Worldwide', 9: 'Korea', 10: 'Brazil'}
                modern_platforms = ['PlayStation 3', 'PlayStation 4', 'PlayStation 5', 'Xbox 360', 'Xbox One', 'Xbox Series', 'Nintendo Switch', 'Wii', 'Wii U', 'PlayStation Vita', 'Nintendo 3DS', 'New Nintendo 3DS', 'iOS', 'Android', 'Java ME', 'macOS', 'Linux', 'Web browser']
                allowed_late_consoles = ['PlayStation 2', 'Xbox', 'Nintendo DS', 'PlayStation Portable']

                for game in data:
                    game_name = game.get('name')
                    release_dates = game.get('release_dates', [])
                    for rd in release_dates:
                        year = rd.get('y')
                        if not year: continue
                        platform_data = rd.get('platform', {})
                        platform_name = platform_data.get('name', 'Unknown') if isinstance(platform_data, dict) else 'Unknown'
                        region_code = rd.get('region')
                        region_str = ""
                        if region_code is not None:
                            try:
                                region_name = igdb_regions.get(int(region_code))
                                if region_name: region_str = f" - {region_name}"
                            except (ValueError, TypeError): pass
                        if any(modern in platform_name for modern in modern_platforms): continue
                        if 'PC' in platform_name or 'Windows' in platform_name:
                            if year > 2000: continue
                        if year > 2005 and platform_name not in allowed_late_consoles: continue
                        
                        display_text = f"{game_name} ({year}) [{platform_name}{region_str}]"
                        if not any(r['text'] == display_text for r in results):
                            results.append({"value": display_text, "text": display_text})
        except Exception as e:
            # ЗАМІНА PRINT НА LOGGER
            logger.error(f" Помилка IGDB API при пошуку '{query}': {e}", exc_info=True)
    return JsonResponse(results, safe=False)

# --- ДОДАВАННЯ ГРИ ---
@login_required
def item_create(request):
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            title = form.cleaned_data['game_title']
            game, _ = Game.objects.get_or_create(title=title)
            item.game = game
            item.save()
            for f in request.FILES.getlist('additional_photos'):
                ItemImage.objects.create(item=item, image=f)
            
            logger.info(f" Користувач {request.user.username} додав нову гру: {title}")
            return redirect('inventory:collection_list')
    else:
        form = CollectionItemForm(user=request.user)
    return render(request, 'inventory/item_form.html', {'form': form, 'title': 'Додати гру'})

# --- РЕДАГУВАННЯ ГРИ ---
@login_required
def item_update(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, request.FILES, instance=item, user=request.user)
        if form.is_valid():
            if request.POST.get('delete_main_photo') == 'on' and not request.FILES.get('photo'):
                if item.photo:
                    item.photo.delete(save=False)
                    item.photo = None
            title = form.cleaned_data['game_title']
            game, _ = Game.objects.get_or_create(title=title)
            item.game = game
            item = form.save()
            photos_to_delete = request.POST.getlist('delete_additional_photos')
            if photos_to_delete:
                ItemImage.objects.filter(id__in=photos_to_delete, item=item).delete()
            for f in request.FILES.getlist('additional_photos'):
                ItemImage.objects.create(item=item, image=f)
                
            logger.info(f" Користувач {request.user.username} оновив гру ID {pk}")
            return redirect('inventory:collection_list')
    else:
        form = CollectionItemForm(instance=item, user=request.user)
    return render(request, 'inventory/item_form.html', {'form': form, 'title': 'Редагувати гру'})

# --- ВИДАЛЕННЯ ГРИ ---
@login_required
def item_delete(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, user=request.user)
    if request.method == 'POST':
        item_name = item.item_name
        item.delete()
        logger.info(f" Користувач {request.user.username} видалив гру '{item_name}' (ID {pk})")
        return redirect('inventory:collection_list')
    return render(request, 'inventory/item_confirm_delete.html', {'item': item})

# --- AJAX ДЛЯ СИСТЕМИ ЗБЕРІГАННЯ ---
@login_required
def load_rooms(request):
    location_id = request.GET.get('location')
    if location_id:
        rooms = Room.objects.filter(location_id=location_id).order_by('name')
        return JsonResponse(list(rooms.values('id', 'name')), safe=False)
    return JsonResponse([], safe=False)

@login_required
def load_storage_units(request):
    room_id = request.GET.get('room')
    if room_id:
        units = StorageUnit.objects.filter(room_id=room_id).order_by('name', 'is_box')
        return JsonResponse(list(units.values('id', 'name', 'is_box')), safe=False)
    return JsonResponse([], safe=False)

# --- МЕНЕДЖЕР СХОВИЩ ---
@login_required
def storage_manager(request):
    locations = Location.objects.filter(user=request.user).prefetch_related('rooms__storage_units')
    return render(request, 'inventory/storage_manager.html', {'locations': locations})

@login_required
def location_create(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save(commit=False)
            location.user = request.user
            location.save()
            logger.info(f" Користувач {request.user.username} створив локацію '{location.name}'")
            return redirect('inventory:storage_manager')
    else:
        form = LocationForm()
    return render(request, 'inventory/form_generic.html', {'form': form, 'title': 'Додати нову локацію'})

@login_required
def room_create(request):
    if request.method == 'POST':
        form = RoomForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('inventory:storage_manager')
    else:
        initial_loc = request.GET.get('location')
        form = RoomForm(user=request.user, initial={'location': initial_loc})
    return render(request, 'inventory/form_generic.html', {'form': form, 'title': 'Додати кімнату'})

@login_required
def storage_unit_create(request):
    if request.method == 'POST':
        form = StorageUnitForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('inventory:storage_manager')
    else:
        initial_room = request.GET.get('room')
        form = StorageUnitForm(user=request.user, initial={'room': initial_room})
    return render(request, 'inventory/form_generic.html', {'form': form, 'title': 'Додати місце зберігання'})

@login_required
def storage_unit_detail(request, pk):
    unit = get_object_or_404(StorageUnit, pk=pk, room__location__user=request.user)
    items = CollectionItem.objects.filter(storage=unit, user=request.user).select_related('game')
    return render(request, 'inventory/storage_unit_detail.html', {'unit': unit, 'items': items})

# --- ДЕТАЛІ ГРИ ТА API ОЦІНКИ ---
@login_required
def item_detail(request, pk):
    item = get_object_or_404(CollectionItem.objects.prefetch_related('additional_photos'), pk=pk, user=request.user)
    return render(request, 'inventory/item_detail.html', {'item': item})

@login_required
def api_market_price(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, user=request.user)
    
    # 1. Твоя ідеальна логіка: ОФІЦІЙНА назва гри з бази IGDB
    search_query = item.game.title
    
    # 2. Твоя ідеальна логіка: Платформа з дужок
    if "[" in item.item_name and "]" in item.item_name:
        plat_match = re.search(r'\[(.*?)\]', item.item_name)
        if plat_match:
            search_query += f" [{plat_match.group(1)}]"
            
    # 3. Регіон
    item_region = item.region if item.region else ""
    
    data = fetch_pricecharting_data(search_query, item_region)
    
    if data:
        # --- ДОДАНО: Збереження в базу ---
        market_val = "N/A"
        comp = (item.completeness or "").lower()
        if any(x in comp for x in ["loose", "картридж", "диск"]):
            market_val = data.get('loose', "N/A")
        elif any(x in comp for x in ["sealed", "новий", "запечатаний"]):
            market_val = data.get('new', "N/A")
        else:
            market_val = data.get('cib', "N/A")

        if market_val != "N/A" and market_val != "":
            try:
                item.market_price = float(str(market_val).replace(',', ''))
                item.last_updated_market = timezone.now()
                item.save()
            except (ValueError, TypeError):
                pass
        # ---------------------------------
        return JsonResponse({"success": True, "prices": data})
    else:
        logger.warning(f" Не вдалося знайти ціну для '{search_query}' (ID {pk})")
        return JsonResponse({"success": False, "error": "Не вдалося знайти ціни."})

# --- ДАШБОРД ТА АНАЛІТИКА ---
@login_required
def dashboard(request):
    items = CollectionItem.objects.filter(user=request.user)
    
    # 1. ЗАГАЛЬНІ ПОКАЗНИКИ
    total_items = items.count()
    priced_items = items.filter(purchase_price__gt=0)
    unpriced_items = items.exclude(purchase_price__gt=0)
    
    priced_count = priced_items.count()
    total_investment = priced_items.aggregate(Sum('purchase_price'))['purchase_price__sum'] or 0
    
    # Ринкова вартість тільки тих ігор, де вказана ціна покупки (для ROI)
    market_val_priced = priced_items.aggregate(Sum('market_price'))['market_price__sum'] or 0
    profit_total = market_val_priced - total_investment
    
    # Ринкова вартість ігор без ціни придбання
    market_val_unpriced = unpriced_items.aggregate(Sum('market_price'))['market_price__sum'] or 0
    total_market_value_all = items.aggregate(Sum('market_price'))['market_price__sum'] or 0

    # Повертаємо "Перлину" та середню ціну
    avg_price = round(priced_items.aggregate(Avg('purchase_price'))['purchase_price__avg'] or 0, 2)
    most_expensive = priced_items.order_by('-purchase_price').first()

    # Словники для назв
    reg_dict = dict(CollectionItem._meta.get_field('region').choices)
    comp_dict = dict(CollectionItem._meta.get_field('completeness').choices)

    # --- СТАТИСТИКА ПЛАТФОРМ (РОЗШИРЕНА) ---
    platform_fin_data = {}
    # Розширений список для кращого розпізнавання
    known_platforms = [
        'playstation 5', 'playstation 4', 'playstation 3', 'playstation 2', 'playstation 1', 'playstation', 'ps5', 'ps4', 'ps3', 'ps2', 'ps1',
        'nintendo switch', 'nintendo 64', 'nintendo ds', 'nintendo 3ds', 'nes', 'snes', 'gamecube', 'wii u', 'wii',
        'game boy advance', 'game boy color', 'game boy', 'gba', 'gbc', 'gb',
        'sega mega drive', 'sega genesis', 'sega saturn', 'dreamcast', 'game gear',
        'xbox series', 'xbox one', 'xbox 360', 'xbox', 'psp', 'ps vita', 'atari', 'famicom'
    ]

    for item in items:
        # Пріоритет 1: Шукаємо в квадратних дужках лоту
        match = re.search(r'\[(.*?)\]', item.item_name)
        plat = None
        if match:
            plat = match.group(1).split('-')[0].strip().upper()
        
        # Пріоритет 2: Шукаємо ключові слова в назві лоту або гри
        if not plat or plat == "":
            search_text = (item.item_name + " " + item.game.title).lower()
            for kp in known_platforms:
                if kp in search_text:
                    plat = kp.upper()
                    break
        
        plat = plat or "ІНШЕ"
        if plat not in platform_fin_data:
            platform_fin_data[plat] = {'inv': 0, 'mkt_p': 0, 'mkt_t': 0}
        
        p_price = float(item.purchase_price or 0)
        m_price = float(item.market_price or 0)
        
        platform_fin_data[plat]['mkt_t'] += m_price
        if p_price > 0:
            platform_fin_data[plat]['inv'] += p_price
            platform_fin_data[plat]['mkt_p'] += m_price

    platform_fin_list = []
    for p_name, s in platform_fin_data.items():
        if s['inv'] > 0 or s['mkt_t'] > 0:
            platform_fin_list.append({
                'name': p_name,
                'invested': round(s['inv'], 2),
                'market_priced': round(s['mkt_p'], 2),
                'market_total': round(s['mkt_t'], 2),
                'profit': round(s['mkt_p'] - s['inv'], 2)
            })

    # Масиви для головного графіка
    plat_labels = [p['name'] for p in platform_fin_list]
    plat_inv = [p['invested'] for p in platform_fin_list]
    plat_mkt_p = [p['market_priced'] for p in platform_fin_list]
    plat_mkt_t = [p['market_total'] for p in platform_fin_list]

    # --- ФІНАНСИ ЗА РЕГІОНАМИ ---
    region_fin_data = {}
    for item in items:
        r_label = reg_dict.get(item.region, 'Інше')
        if r_label not in region_fin_data:
            region_fin_data[r_label] = {'inv': 0, 'mkt_p': 0, 'mkt_t': 0}
        
        p_price = float(item.purchase_price or 0)
        m_price = float(item.market_price or 0)
        
        region_fin_data[r_label]['mkt_t'] += m_price
        if p_price > 0:
            region_fin_data[r_label]['inv'] += p_price
            region_fin_data[r_label]['mkt_p'] += m_price

    region_fin_list = []
    for r_name, s in region_fin_data.items():
        if s['inv'] > 0 or s['mkt_t'] > 0:
            region_fin_list.append({
                'name': r_name,
                'invested': round(s['inv'], 2),
                'market_priced': round(s['mkt_p'], 2),
                'market_total': round(s['mkt_t'], 2),
                'profit': round(s['mkt_p'] - s['inv'], 2)
            })

    reg_fin_labels = [r['name'] for r in region_fin_list]
    reg_fin_inv = [r['invested'] for r in region_fin_list]
    reg_fin_mkt_p = [r['market_priced'] for r in region_fin_list]
    reg_fin_mkt_t = [r['market_total'] for r in region_fin_list]

    # Кругові графіки (Комплектація та Регіони)
    comp_data = items.values('completeness').annotate(count=Count('id'))
    comp_labels = [comp_dict.get(c['completeness'], 'Не вказано') for c in comp_data]
    comp_counts = [c['count'] for c in comp_data]

    reg_summary_data = items.values('region').annotate(count=Count('id'))
    reg_labels = [reg_dict.get(r['region'], 'Не вказано') for r in reg_summary_data]
    reg_counts = [r['count'] for r in reg_summary_data]

    context = {
        'total_items': total_items,
        'total_investment': round(total_investment, 2),
        'market_val_priced': round(market_val_priced, 2),
        'market_val_unpriced': round(market_val_unpriced, 2),
        'total_market_value_all': round(total_market_value_all, 2),
        'profit_total': round(profit_total, 2),
        'avg_price': avg_price,
        'priced_count': priced_count,
        'most_expensive': most_expensive,
        
        'platform_fin_list': platform_fin_list,
        'plat_labels': json.dumps(plat_labels),
        'plat_inv': json.dumps(plat_inv),
        'plat_mkt_p': json.dumps(plat_mkt_p),
        'plat_mkt_t': json.dumps(plat_mkt_t),
        
        'region_fin_list': region_fin_list,
        'reg_fin_labels': json.dumps(reg_fin_labels),
        'reg_fin_inv': json.dumps(reg_fin_inv),
        'reg_fin_mkt_p': json.dumps(reg_fin_mkt_p),
        'reg_fin_mkt_t': json.dumps(reg_fin_mkt_t),

        'comp_labels': json.dumps(comp_labels),
        'comp_counts': json.dumps(comp_counts),
        'reg_labels': json.dumps(reg_labels),
        'reg_counts': json.dumps(reg_counts),
        'recent_items': items.order_by('-id')[:5]
    }
    return render(request, 'inventory/dashboard.html', context)


def storage_unit_dashboard(request, pk):
    unit = get_object_or_404(StorageUnit, pk=pk)
    
    # --- ЛОГІКА ДОСТУПУ (Без @login_required!) ---
    if not unit.is_public:
        # Якщо сховище приватне, але юзер не в системі — відправляємо на логін
        if not request.user.is_authenticated:
            logger.debug(f"  Анонім намагався отримати доступ до приватного сховища ID {pk}.")
            return redirect('login')
        # Якщо юзер в системі, але це не його локація — блокуємо
        if unit.room.location.user != request.user:
            logger.warning(f" Користувач {request.user.username} намагався отримати доступ до чужого сховища ID {pk}.")
            return HttpResponseForbidden(" Це приватне сховище. У вас немає доступу.")

    # Беремо ігри ТІЛЬКИ з цього сховища
    items = CollectionItem.objects.filter(storage=unit)
    total_items = items.count()
    
    # --- НАДІЙНИЙ ПІДРАХУНОК ФІНАНСІВ ---
    total_investment = 0.0
    market_val_priced = 0.0
    total_market_value_all = 0.0

    for item in items:
        # Безпечно конвертуємо ціни у числа (навіть якщо там None)
        p_price = float(item.purchase_price or 0)
        m_price = float(item.market_price or 0)

        # Додаємо ринкову ціну до загального капіталу полиці
        total_market_value_all += m_price

        # Якщо ми купували цю гру (ціна > 0), рахуємо інвестиції та прибуток
        if p_price > 0:
            total_investment += p_price
            market_val_priced += m_price

    # Чистий прибуток (тільки для куплених ігор)
    profit_total = market_val_priced - total_investment

    context = {
        'unit': unit,
        'total_items': total_items,
        'total_investment': round(total_investment, 2),
        'profit_total': round(profit_total, 2),
        'total_market_value_all': round(total_market_value_all, 2),
        'items': items.order_by('-id')[:20] # Показуємо останні 20 ігор у списку знизу
    }
    
    return render(request, 'inventory/storage_dashboard.html', context)