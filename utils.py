"""
Fonctions utilitaires
"""
from datetime import timedelta


def is_business_day(date):
    """Vérifie si une date est un jour ouvrable (lundi-vendredi)"""
    return date.weekday() < 5


def add_business_days(start_date, days):
    """Ajoute un nombre de jours ouvrables à une date"""
    current = start_date
    while days > 0:
        current += timedelta(days=1)
        if is_business_day(current):
            days -= 1
    return current
