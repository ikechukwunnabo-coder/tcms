from django.contrib import admin

from .models import Company, ContactType, Nationality, Position, State, Title

for _model in (Company, Nationality, State, Position, Title, ContactType):
    admin.site.register(_model)
