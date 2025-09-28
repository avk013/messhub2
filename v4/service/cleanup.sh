#!/bin/bash
# cleanup.sh - Принудительная очистка процессов Chrome (для обычного пользователя)

PROFILE_PATH="/home/alexova/chrome_profile"

echo "Остановка процессов Chrome для текущего пользователя..."

# Находим и убиваем процессы Chrome с нашим профилем
pkill -f "chrome.*user-data-dir.*chrome_profile" 2>/dev/null
pkill -f "chromedriver" 2>/dev/null
pkill -f "Chrome.*user-data-dir.*chrome_profile" 2>/dev/null

sleep 2

# Принудительно убиваем если остались
pkill -9 -f "chrome.*user-data-dir.*chrome_profile" 2>/dev/null
pkill -9 -f "chromedriver" 2>/dev/null
pkill -9 -f "Chrome.*user-data-dir.*chrome_profile" 2>/dev/null

echo "Очистка завершена"

# Показываем оставшиеся процессы
echo "Оставшиеся Chrome процессы текущего пользователя:"
ps -u $(whoami) | grep -i chrome | grep -v grep | grep -v cleanup.sh || echo "Нет активных Chrome процессов"

# Проверяем заблокированные порты (если есть права)
echo "Проверяем порты Chrome..."
ss -tulpn 2>/dev/null | grep chrome || echo "Chrome не использует порты"
