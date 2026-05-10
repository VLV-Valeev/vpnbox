"""Shared rate limiter instance — вынесен в отдельный модуль, чтобы
роуты могли импортировать его без циркулярной зависимости с main.py."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
