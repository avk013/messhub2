import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
#from config import CONTACT_NAME, FILE_PATH, CAPTION_TEXT
from config import CONTACT_NAME

def login():
    """
    Запускает браузер Google Chrome и открывает WhatsApp Web.
    Использует постоянный профиль для сохранения сессии.
    """
    chrome_options = Options()
    chrome_options.add_argument("user-data-dir=/home/alexova/chrome_profile")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (iPad; CPU OS 13_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Mobile/15E148 Safari/604.1"
    )
    # Убедитесь, что вы авторизовались хотя бы один раз, прежде чем включать headless
    chrome_options.add_argument("--headless=new")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get("https://web.whatsapp.com/")
    
    try:
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="side"]'))
        )
        print("Вход выполнен успешно!")
        return driver
    except TimeoutException:
        print("Время на вход истекло или произошла ошибка.")
        driver.quit()
        return None

def find_element_with_fallback(driver, selectors, timeout=5):
    """
    Ищет элемент по списку селекторов с fallback
    """
    for selector_data in selectors:
        try:
            by_type, selector = selector_data
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by_type, selector))
            )
            return element
        except TimeoutException:
            continue
    return None

def find_clickable_element_with_fallback(driver, selectors, timeout=5):
    """
    Ищет кликабельный элемент по списку селекторов с fallback
    """
    for selector_data in selectors:
        try:
            by_type, selector = selector_data
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by_type, selector))
            )
            return element
        except TimeoutException:
            continue
    return None

def send_file(driver, contact_name, file_path, caption=None):
    """
    Отправляет файл (фото/видео) с подписью или без нее указанному контакту.
    """
    try:
        # 1. Проверяем, открыт ли уже нужный чат
        try:
            current_chat = driver.find_element(By.XPATH, f'//span[@title="{contact_name}"]//ancestor::div[contains(@class, "selected") or contains(@style, "background")]')
            if current_chat:
                print(f"Чат '{contact_name}' уже открыт.")
        except:
            # Чат не открыт, ищем и открываем
#            print(f"Открываем чат с '{contact_name}'...")
            
            search_selectors = [
                (By.CSS_SELECTOR, '[aria-label="Поиск контактов или групп"]'),  # Русский
                (By.CSS_SELECTOR, '[aria-label="Search contacts or groups"]'),   # Английский
                (By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]'),  # Универсальный
                (By.CSS_SELECTOR, '[data-testid="chat-list-search"]'),           # Альтернативный
            ]
            
            search_box = find_element_with_fallback(driver, search_selectors)
            if not search_box:
                print("Не удалось найти поле поиска")
                return False
                
            search_box.clear()
            search_box.send_keys(contact_name)
            time.sleep(1)
            
            # Открываем чат с контактом
            contact = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f'//span[@title="{contact_name}"]'))
            )
            contact.click()
#            print("Чат открыт.")
#            time.sleep(1)
        
        # 2. Нажимаем на кнопку "Прикрепить" с fallback
        attach_selectors = [
            (By.CSS_SELECTOR, 'button[title="Прикрепить"]'),      # Русский
            (By.CSS_SELECTOR, 'button[title="Attach"]'),          # Английский
            (By.CSS_SELECTOR, 'span[data-icon="clip"]'),          # Универсальный
            (By.CSS_SELECTOR, '[data-testid="clip"]'),            # Альтернативный
        ]
        
        attach_btn = find_clickable_element_with_fallback(driver, attach_selectors)
        if not attach_btn:
            print("Не удалось найти кнопку прикрепления")
            return False
            
        attach_btn.click()
        
        # 3. Находим input для файлов
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"][accept*="image"]'))
        )
        
        absolute_file_path = os.path.abspath(file_path)
        file_input.send_keys(absolute_file_path)
#        time.sleep(1)  # Сокращенная задержка
        
        # Ждем появления окна предпросмотра с fallback
        preview_selectors = [
            (By.CSS_SELECTOR, 'div[aria-label="Окно предварительного просмотра"]'),  # Русский
            (By.CSS_SELECTOR, 'div[aria-label="Preview window"]'),                   # Английский
            (By.CSS_SELECTOR, '[data-testid="media-viewer"]'),                       # Универсальный
            (By.CSS_SELECTOR, '.media-viewer'),                                      # Альтернативный
        ]
        
        preview_element = find_element_with_fallback(driver, preview_selectors, timeout=3)
        if not preview_element:
            print("Окно предпросмотра не появилось. Возможно, файл уже загружен.")
        
        # 4. Добавляем подпись с fallback селекторами
        if caption:
#            print("Добавляем подпись...")
            
            caption_selectors = [
                (By.CSS_SELECTOR, 'div[aria-label="Введите сообщение"]'),     # Русский
                (By.CSS_SELECTOR, 'div[aria-label="Type a message"]'),        # Английский  
                (By.XPATH, '//div[@contenteditable="true" and @data-tab="10"]'), # Универсальный
                (By.CSS_SELECTOR, '[data-testid="media-caption-input"]'),     # Альтернативный
            ]
            
            caption_box = find_element_with_fallback(driver, caption_selectors)
            if caption_box:
                caption_box.send_keys(caption)
                print("Подпись добавлена.")
            else:
                print("Не удалось найти поле для подписи")
        
        # 5. Кликаем на кнопку отправки с fallback
        print("Ищем и нажимаем кнопку отправки...")
        
        send_selectors = [
            (By.CSS_SELECTOR, 'div[aria-label="Отправить"]'),              # Русский
            (By.CSS_SELECTOR, 'div[aria-label="Send"]'),                   # Английский
            (By.CSS_SELECTOR, 'div[data-icon="wds-ic-send-filled"]'),      # Универсальный
            (By.CSS_SELECTOR, 'span[data-icon="send"]'),                   # Альтернативный
            (By.CSS_SELECTOR, '[data-testid="send"]'),                     # Новый интерфейс
        ]
        
        send_btn = find_clickable_element_with_fallback(driver, send_selectors)
        if send_btn:
            send_btn.click()
            print("✓ Файл успешно отправлен.")
            return True
        else:
            print("✗ НЕ УДАЛОСЬ НАЙТИ КНОПКУ ОТПРАВКИ!")
            return False
            
    except Exception as e:
        print(f"Критическая ошибка при отправке файла: {e}")
        return False

def send_message(driver, contact_name, message):
    """
    Отправляет текстовое сообщение с fallback селекторами
    """
    try:
        # Проверяем, открыт ли уже нужный чат
        try:
            current_chat = driver.find_element(By.XPATH, f'//span[@title="{contact_name}"]//ancestor::div[contains(@class, "selected") or contains(@style, "background")]')
            if current_chat:
                print(f"Чат '{contact_name}' уже открыт.")
        except:
            # Чат не открыт, ищем и открываем
            search_selectors = [
                (By.CSS_SELECTOR, '[aria-label="Поиск контактов или групп"]'),  # Русский
                (By.CSS_SELECTOR, '[aria-label="Search contacts or groups"]'),   # Английский
                (By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]'),  # Универсальный
            ]
            
            search_box = find_element_with_fallback(driver, search_selectors)
            if not search_box:
                print("Не удалось найти поле поиска")
                return False
                
            search_box.clear()
            search_box.send_keys(contact_name)
            time.sleep(1)
            
            # Ждем, пока появится нужный контакт
            contact = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f'//span[@title="{contact_name}"]'))
            )
            contact.click()
#            time.sleep(1)
        
        # Находим поле для ввода сообщения с fallback
        message_selectors = [
            (By.CSS_SELECTOR, 'div[aria-label="Введите сообщение"]'),        # Русский
            (By.CSS_SELECTOR, 'div[aria-label="Type a message"]'),           # Английский
            (By.XPATH, '//div[@contenteditable="true" and @data-tab="10"]'), # Универсальный
        ]
        
        message_box = find_element_with_fallback(driver, message_selectors)
        if not message_box:
            print("Не удалось найти поле для сообщения")
            return False
            
        message_box.send_keys(message)
        message_box.send_keys(Keys.ENTER)
        
        print(f"Сообщение '{message}' успешно отправлено контакту '{contact_name}'.")
        return True
        
    except TimeoutException:
        print("Не удалось найти необходимые элементы. Время ожидания истекло.")
        return False
    except Exception as e:
        print(f"Не удалось отправить сообщение. Ошибка: {e}")

if __name__ == "__main__":
    driver = login()
    if driver:
        send_message(driver, CONTACT_NAME, "TopTop")
        time.sleep(1)
        send_file(driver, CONTACT_NAME, "1.jpg", "text")
        time.sleep(3)
        # Эта команда критически важна для закрытия браузера
        driver.quit()