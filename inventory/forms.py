from django import forms
from .models import CollectionItem, ItemImage, Location, Room, StorageUnit
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

# ДОДАЄМО ЦЕЙ КЛАС:
class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            # Якщо це список файлів - перевіряємо кожен окремо
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class CollectionItemForm(forms.ModelForm):
    game_title = forms.CharField(
        max_length=255, required=True, label="Назва гри (з бази IGDB)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_game_title'})
    )
    
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(), required=False, label="Локація (Будівля)",
        empty_label="Виберіть локацію...",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_location'})
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.none(), required=False, label="Кімната",
        empty_label="Спочатку виберіть локацію",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_room'})
    )

    #Використовуємо ClearableFileInput з multiple: True
    additional_photos = MultipleFileField(
        widget=MultipleFileInput(attrs={'multiple': True, 'class': 'form-control', 'id': 'id_additional_photos'}),
        required=False, label="Додаткові фотографії"
    )

    # 1. ТУТ НЕМАЄ inventory_code
    field_order = [
        'item_name', 'game_title', 'acquired_date', 'purchase_price',
        'edition', 'completeness', 'region', 'is_reproduction',
        'condition', 'location', 'room', 'storage', 'photo', 'additional_photos', 'notes'
    ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and hasattr(self.instance, 'game'):
            self.fields['game_title'].initial = self.instance.game.title
            self.fields['item_name'].initial = self.instance.item_name

        if self.user:
            self.fields['location'].queryset = Location.objects.filter(user=self.user)

        self.fields['room'].queryset = Room.objects.none()
        self.fields['storage'].queryset = StorageUnit.objects.none()

        if 'location' in self.data:
            try:
                location_id = int(self.data.get('location'))
                self.fields['room'].queryset = Room.objects.filter(location_id=location_id)
            except (ValueError, TypeError):
                pass
            if 'room' in self.data:
                try:
                    room_id = int(self.data.get('room'))
                    self.fields['storage'].queryset = StorageUnit.objects.filter(room_id=room_id)
                except (ValueError, TypeError):
                    pass
        elif self.instance.pk and self.instance.storage:
            room = self.instance.storage.room
            self.fields['location'].initial = room.location
            self.fields['room'].queryset = room.location.rooms.all()
            self.fields['room'].initial = room
            self.fields['storage'].queryset = room.storage_units.all()

    class Meta:
        model = CollectionItem
        # 2. ТУТ НЕМАЄ inventory_code
        fields = [
            'item_name', 'game_title', 'acquired_date', 'purchase_price',
            'edition', 'completeness', 'region', 'is_reproduction',
            'condition', 'storage', 'photo', 'notes'
        ]
        
        # 3. Є НОВИЙ ВІДЖЕТ ДЛЯ edition
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control form-control-lg fw-bold', 'placeholder': 'Ваша власна назва (напр. Sakura Wars Японська)'}),
            'edition': forms.Select(attrs={'class': 'form-select'}),
            'acquired_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'completeness': forms.Select(attrs={'class': 'form-select'}),
            'region': forms.Select(attrs={'class': 'form-select'}),
            'is_reproduction': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'condition': forms.TextInput(attrs={'class': 'form-control'}),
            'storage': forms.Select(attrs={'class': 'form-select', 'id': 'id_storage'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'mainPhotoInput'}),
        }

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Напр., Моя квартира, Дача, Гараж'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Опціонально (можна залишити пустим)'}),
        }

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['location', 'name']
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Напр., Спальня, Кабінет'}),
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['location'].queryset = Location.objects.filter(user=user)

class StorageUnitForm(forms.ModelForm):
    class Meta:
        model = StorageUnit
        # Додали 'is_public' в кінець списку полів
        fields = ['room', 'name', 'is_box', 'is_public'] 
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Напр., Верхня полиця, Коробка з кабелями'}),
            'is_box': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}), # Додано віджет для чекбоксу
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # Показуємо тільки ті кімнати, які належать локаціям цього користувача
            self.fields['room'].queryset = Room.objects.filter(location__user=user)

# Форма для реєстрації
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Змінюємо назви полів (Label)
        self.fields['username'].label = "Логін"
        self.fields['password1'].label = "Пароль"
        self.fields['password2'].label = "Підтвердження пароля"
        
        # Прибираємо набридливі підказки (Help text)
        self.fields['username'].help_text = ''
        self.fields['password2'].help_text = ''

# Форма для входу
class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Змінюємо назви полів (Label)
        self.fields['username'].label = "Логін"
        self.fields['password'].label = "Пароль"