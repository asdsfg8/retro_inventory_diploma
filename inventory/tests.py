from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, Mock
from decimal import Decimal

# Імпортуємо твої моделі та утиліти
from .models import Game, Location, Room, StorageUnit, CollectionItem
from .utils import fetch_pricecharting_data

class InventoryModelsTest(TestCase):
    def setUp(self):
        """Цей метод запускається ПЕРЕД кожним тестом. Створюємо тестові дані."""
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        
        self.game = Game.objects.create(title="Super Mario 64")
        
        self.location = Location.objects.create(
            user=self.user, 
            name="Моя квартира"
        )
        
        self.room = Room.objects.create(
            location=self.location, 
            name="Вітальня"
        )
        
        self.storage = StorageUnit.objects.create(
            room=self.room, 
            name="Полиця 1",
            is_public=True
        )
        
        self.item = CollectionItem.objects.create(
            user=self.user,
            game=self.game,
            item_name="Super Mario 64 (Loose)",
            storage=self.storage,
            completeness=CollectionItem.Completeness.LOOSE,
            region=CollectionItem.Region.NTSC_U,
            purchase_price=Decimal('25.50')
        )

    def test_model_string_representations(self):
        """Тестуємо, чи правильно моделі повертають свої назви (__str__)"""
        self.assertEqual(str(self.game), "Super Mario 64")
        self.assertEqual(str(self.location), "Моя квартира")
        self.assertEqual(str(self.room), "Моя квартира -> Вітальня")
        self.assertEqual(str(self.storage), "Моя квартира -> Вітальня -> Полиця 1")
        self.assertEqual(str(self.item), "Super Mario 64 - Тільки картридж/диск (Loose)")

    def test_storage_unit_defaults(self):
        """Тестуємо логіку полів за замовчуванням"""
        # is_box має бути False за замовчуванням
        self.assertFalse(self.storage.is_box)
        # is_public ми задали True в setUp
        self.assertTrue(self.storage.is_public)

    def test_collection_item_hierarchy(self):
        """Тестуємо ієрархічні зв'язки БД"""
        # Перевіряємо, чи предмет дійсно лежить у "Моїй квартирі"
        item_location = self.item.storage.room.location.name
        self.assertEqual(item_location, "Моя квартира")


class PriceChartingScraperTest(TestCase):
    
    @patch('inventory.utils.requests.get')
    def test_fetch_pricecharting_success_direct_page(self, mock_get):
        """
        Тестуємо СЦЕНАРІЙ А: Успішний парсинг, коли сайт видає сторінку гри.
        Ми використовуємо @patch, щоб перехопити requests.get і не йти в інтернет.
        """
        # 1. Створюємо фейкову відповідь від сервера (HTML)
        mock_html = """
        <html>
            <title>Super Mario 64 Prices | Nintendo 64</title>
            <h1 id="product_name">Super Mario 64</h1>
            <div id="used_price"><span class="price">$25.00</span></div>
            <div id="cib_price"><span class="price">$75.00</span></div>
            <div id="new_price"><span class="price">$250.00</span></div>
        </html>
        """
        # Налаштовуємо наш Mock-об'єкт
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_html
        mock_response.url = "https://www.pricecharting.com/game/nintendo-64/super-mario-64"
        mock_get.return_value = mock_response

        # 2. Викликаємо нашу функцію
        result = fetch_pricecharting_data("Super Mario 64 [N64]", "ntsc_u")

        # 3. Перевіряємо результати
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Super Mario 64")
        self.assertEqual(result['loose'], "25.00")
        self.assertEqual(result['cib'], "75.00")
        self.assertEqual(result['new'], "250.00")
        self.assertEqual(result['console'], "Nintendo 64")

    @patch('inventory.utils.requests.get')
    def test_fetch_pricecharting_server_error(self, mock_get):
        """Тестуємо поведінку скрапера, якщо сервер PriceCharting впав (помилка 500)"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = fetch_pricecharting_data("Some Game [PS1]", "pal")
        
        # Функція має обробити помилку і повернути None, а не зламати програму
        self.assertIsNone(result)

    @patch('inventory.utils.requests.get')
    def test_fetch_pricecharting_not_found(self, mock_get):
        """Тестуємо поведінку, якщо гра не знайдена (немає потрібних тегів)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>Page Not Found</h1></body></html>"
        mock_response.url = "https://www.pricecharting.com/search-products?q=unknown"
        mock_get.return_value = mock_response

        result = fetch_pricecharting_data("Unknown Game 999 [PS5]", "pal")
        self.assertIsNone(result)


from django.urls import reverse

class InventoryViewsSecurityTest(TestCase):
    def setUp(self):
        """Налаштування для тестів безпеки та доступу"""
        #self.client = Client() # Емулятор браузера
        
        # Створюємо Власника
        self.owner = User.objects.create_user(username='owner', password='password123')
        # Створюємо Іншого користувача
        self.other_user = User.objects.create_user(username='guest', password='password123')
        
        self.location = Location.objects.create(user=self.owner, name="Дім")
        self.room = Room.objects.create(location=self.location, name="Кімната")
        
        # Створюємо ДВА сховища: одне публічне, одне приватне
        self.public_storage = StorageUnit.objects.create(room=self.room, name="Вітрина", is_public=True)
        self.private_storage = StorageUnit.objects.create(room=self.room, name="Сейф", is_public=False)

    def test_collection_list_requires_login(self):
        """Перевіряємо, чи перенаправляє анонімного користувача на сторінку входу"""
        response = self.client.get(reverse('inventory:collection_list'))
        # Має бути перенаправлення (код 302) на сторінку /login/?next=/
        self.assertRedirects(response, f"{reverse('inventory:login')}?next={reverse('inventory:collection_list')}")

    def test_public_storage_dashboard_anonymous_access(self):
        """Перевіряємо, чи може анонім зайти на ПУБЛІЧНЕ сховище (QR код)"""
        url = reverse('inventory:storage_unit_dashboard', kwargs={'pk': self.public_storage.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) # Доступ дозволено

    def test_private_storage_dashboard_anonymous_redirect(self):
        """Перевіряємо, чи ПРИВАТНЕ сховище відправляє аноніма на логін"""
        url = reverse('inventory:storage_unit_dashboard', kwargs={'pk': self.private_storage.pk})
        response = self.client.get(url)
        self.assertRedirects(response, reverse('login')) # Згідно з твоєю логікою у views.py

    def test_private_storage_dashboard_wrong_user(self):
        """Перевіряємо, чи чужий користувач отримає помилку 403 при спробі зайти в ПРИВАТНЕ сховище"""
        self.client.login(username='guest', password='password123') # Логінимося як інший юзер
        url = reverse('inventory:storage_unit_dashboard', kwargs={'pk': self.private_storage.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403) # 403 Forbidden
        self.assertIn("Це приватне сховище", response.content.decode('utf-8'))

    def test_private_storage_dashboard_owner_access(self):
        """Перевіряємо, чи ВЛАСНИК має доступ до свого ПРИВАТНОГО сховища"""
        self.client.login(username='owner', password='password123') # Логінимося як власник
        url = reverse('inventory:storage_unit_dashboard', kwargs={'pk': self.private_storage.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) # Доступ дозволено