from django.contrib import admin
from .models import Location, Room, StorageUnit, CollectionItem, Game

admin.site.register(Location)
admin.site.register(Room)
admin.site.register(StorageUnit)
admin.site.register(CollectionItem)
admin.site.register(Game)