from django.db import models
from django.contrib.auth.models import User

# --- 1. БАЗОВА МОДЕЛЬ ГРИ (Із зовнішньої БД) ---
class Game(models.Model):
    title = models.CharField(max_length=255, verbose_name="Назва гри")
    # Тут можуть бути інші твої поля для гри, наприклад, дата виходу чи опис
    
    def __str__(self):
        return self.title

# --- 2. МОДЕЛІ СИСТЕМИ ЗБЕРІГАННЯ (Ієрархія) ---
class Location(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=100, verbose_name="Назва локації (напр., Моя квартира)")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Адреса (необов'язково)")

    def __str__(self):
        return self.name

class Room(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100, verbose_name="Кімната (напр., Вітальня)")

    def __str__(self):
        return f"{self.location.name} -> {self.name}"

class StorageUnit(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='storage_units')
    name = models.CharField(max_length=100, verbose_name="Місце (напр., Стелаж 1, Коробка А)")
    is_box = models.BooleanField(default=False, verbose_name="Це закрита коробка?")
    
    # Твоє нове поле:
    is_public = models.BooleanField(default=False, verbose_name="Зробити дашборд публічним (доступ за QR-кодом без логіну)")

    def __str__(self):
        return f"{self.room} -> {self.name}"

# --- 3. ГОЛОВНА МОДЕЛЬ: ОДИНИЦЯ КОЛЕКЦІЇ ---
class CollectionItem(models.Model):
    # Допоміжні класи для випадаючих списків
    class Completeness(models.TextChoices):
        LOOSE = 'loose', 'Тільки картридж/диск (Loose)'
        CIB = 'cib', 'Повний комплект (CIB)'
        BOXED = 'boxed', 'Картридж + Коробка'
        MANUAL = 'manual', 'Картридж + Мануал'
        SEALED = 'sealed', 'Запакована (Sealed)'
       


    class Region(models.TextChoices):
        NTSC_U = 'ntsc_u', 'NTSC-U (Північна Америка)'
        NTSC_J = 'ntsc_j', 'NTSC-J (Японія)'
        PAL = 'pal', 'PAL (Європа / Австралія)'
        UNKNOWN = 'unknown', 'Невідомо / Інше'

    # Головні зв'язки
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    # 1. Власна назва 
    item_name = models.CharField(max_length=255, verbose_name="Назва вашої копії", help_text="Наприклад: 'Doom (Big Box)'", default="Нова гра")
    
    # ВИДАЛЕННЯ: Повністю видали рядок inventory_code = models.CharField(...) звідси!

    # 2. Створюємо список варіантів для видання
    EDITION_CHOICES = [
        ('', 'Не вказано / Стандартне'),
        ('Big Box', 'Big Box (Велика картонна коробка)'),
        ('Jewel Case', 'Jewel Case (Стандартна CD коробка)'),
        ('Keep Case', 'Keep Case (Пластикова DVD/Blu-ray коробка)'),
        ('SteelBook', 'SteelBook (Металевий кейс)'),
        ('Limited Edition', 'Лімітоване видання (Limited)'),
        ('Collector Edition', 'Колекційне видання (Collector\'s)'),
        ('Greatest Hits', 'Greatest Hits / Platinum / Player\'s Choice'),
        ('Other', 'Інше'),
    ]

    # 3. Оновлюємо поле edition
    edition = models.CharField(
        max_length=50, 
        choices=EDITION_CHOICES, 
        blank=True, 
        null=True, 
        verbose_name="Видання"
    )

    # Інформація про придбання (тепер необов'язкові)
    acquired_date = models.DateField(null=True, blank=True, verbose_name="Дата придбання")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Ціна покупки")
    
    # Специфіка ретро-колекціонування
    completeness = models.CharField(max_length=20, choices=Completeness.choices, default=Completeness.LOOSE, verbose_name="Комплектація")
    region = models.CharField(max_length=20, choices=Region.choices, default=Region.UNKNOWN, verbose_name="Регіон")
    is_reproduction = models.BooleanField(default=False, verbose_name="Це репродукція (не оригінал)")
    condition = models.CharField(max_length=50, blank=True, null=True, verbose_name="Стан (опис)")
    
    market_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Ринкова ціна ($)")
    last_updated_market = models.DateTimeField(null=True, blank=True, verbose_name="Дата оновлення ціни")

    # Зв'язок із системою зберігання
    storage = models.ForeignKey(
        StorageUnit, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Місцезнаходження"
    )
    
    # Медіа та інше
    photo = models.ImageField(upload_to='items_photos/', blank=True, null=True, verbose_name="Головне фото")
    notes = models.TextField(blank=True, null=True, verbose_name="Нотатки")

    def __str__(self):
        return f"{self.game.title} - {self.get_completeness_display()}"
    
class ItemImage(models.Model):
    item = models.ForeignKey(CollectionItem, on_delete=models.CASCADE, related_name='additional_photos')
    image = models.ImageField(upload_to='items_photos/gallery/', verbose_name='Додаткове фото')

    def __str__(self):
        return f"Фото для {self.item.game.title}"