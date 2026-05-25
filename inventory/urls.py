from django.urls import path
from . import views
from django.urls import include
from django.contrib.auth import views as auth_views
from inventory.forms import CustomLoginForm # Імпортуємо форму входу

app_name = 'inventory'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('delete/<int:pk>/', views.item_delete, name='item_delete'),
    path('', views.collection_list, name='collection_list'),
    path('add/', views.item_create, name='item_create'),
    path('edit/<int:pk>/', views.item_update, name='item_update'),
    path('api/search-games/', views.search_games, name='search_games'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=CustomLoginForm # Вказуємо використовувати нашу форму!
    ), name='login'),

    # --- СИСТЕМА ЗБЕРІГАННЯ ---
    path('storage/', views.storage_manager, name='storage_manager'),
    path('storage/location/add/', views.location_create, name='location_create'),
    path('storage/room/add/', views.room_create, name='room_create'),
    path('storage/unit/add/', views.storage_unit_create, name='storage_unit_create'),
    path('storage/unit/<int:pk>/', views.storage_unit_detail, name='storage_unit_detail'),
    
    path('ajax/load-rooms/', views.load_rooms, name='ajax_load_rooms'),
    path('ajax/load-storage-units/', views.load_storage_units, name='ajax_load_storage_units'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('item/<int:pk>/', views.item_detail, name='item_detail'),
    path('api/market-price/<int:pk>/', views.api_market_price, name='api_market_price'),
    path('storage/<int:pk>/dashboard/', views.storage_unit_dashboard, name='storage_unit_dashboard'),
]