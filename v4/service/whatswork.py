# whatsapp_worker.py
import os
import json
import time
import glob
import signal
import sys
import atexit
import psutil
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.keys import Keys

class WhatsAppWorker:
    def __init__(self, queue_dir="queue", profile_path="/home/alexova/chrome_profile"):
        self.queue_dir = queue_dir
        self.pending_dir = os.path.join(queue_dir, "whatsapp", "pending")
        self.processing_dir = os.path.join(queue_dir, "whatsapp", "processing")
        self.failed_dir = os.path.join(queue_dir, "whatsapp", "failed")
        self.profile_path = profile_path
        self.driver = None
        self.service = None
        self.operation_count = 0
        self.max_operations = 100
        self.running = True
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Регистрируем cleanup при выходе
        atexit.register(self.cleanup)

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        print(f"\nПолучен сигнал {signum}. Завершение работы...")
        self.running = False

    def start(self):
        """Запускает воркер"""
        print("Запуск WhatsApp Worker...")
        
        try:
            self.init_browser()
            
            while self.running:
                try:
                    tasks = self.scan_pending_tasks()
                    if not tasks:
                        time.sleep(5)
                        continue
                    
                    grouped_tasks = self.group_tasks_by_chat(tasks)
                    self.process_grouped_tasks(grouped_tasks)
                    
                except KeyboardInterrupt:
                    print("Получен SIGINT, остановка...")
                    break
                except Exception as e:
                    print(f"Ошибка в основном цикле: {e}")
                    time.sleep(10)
                    
        except Exception as e:
            print(f"Критическая ошибка: {e}")
        finally:
            self.cleanup()

    def init_browser(self):
        """Инициализирует браузер"""
        # Закрываем предыдущий браузер если есть
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            
        if self.service:
            try:
                self.service.stop()
            except:
                pass
            self.service = None
            
        # Убиваем зависшие процессы Chrome
        self._kill_chrome_processes()
        
        try:
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--remote-debugging-port=0")  # Случайный порт
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (iPad; CPU OS 13_6 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Mobile/15E148 Safari/604.1"
            )
            
            # Убрать после первого входа в сессию и необходимости оконного режима
            chrome_options.add_argument("--headless=new")
            
            self.service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=self.service, options=chrome_options)
            self.driver.implicitly_wait(10)
            
            self.driver.get("https://web.whatsapp.com/")
            
            try:
                WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="side"]'))
                )
                print("WhatsApp Web загружен успешно!")
                self.operation_count = 0
                return True
                
            except TimeoutException:
                print("Ошибка загрузки WhatsApp Web")
                raise
                
        except Exception as e:
            print(f"Ошибка инициализации браузера: {e}")
            self.cleanup()
            raise

    def _kill_chrome_processes(self):
        """Убивает зависшие процессы Chrome"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        if proc.info['cmdline'] and any('user-data-dir' in arg for arg in proc.info['cmdline']):
                            if any(self.profile_path in arg for arg in proc.info['cmdline']):
                                print(f"Убиваем процесс Chrome: {proc.info['pid']}")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=5)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            print(f"Ошибка при завершении процессов Chrome: {e}")

    def scan_pending_tasks(self):
        """Сканирует папку pending на наличие задач"""
        pattern = os.path.join(self.pending_dir, "*.json")
        task_files = glob.glob(pattern)
        tasks = []
        
        for file_path in task_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    task = json.load(f)
                task['_filepath'] = file_path
                tasks.append(task)
            except Exception as e:
                print(f"Ошибка чтения файла {file_path}: {e}")
                
        return tasks

    def group_tasks_by_chat(self, tasks):
        """Группирует задачи по чатам"""
        grouped = defaultdict(list)
        for task in tasks:
            grouped[task['target']].append(task)
        return dict(grouped)

    def process_grouped_tasks(self, grouped_tasks):
        """Обрабатывает сгруппированные задачи"""
        # Проверяем, что мы всё ещё работаем
        if not self.running:
            return
            
        # Сортируем чаты по количеству задач (больше задач = выше приоритет)
        sorted_chats = sorted(grouped_tasks.items(), key=lambda x: len(x[1]), reverse=True)
        
        for chat_name, tasks in sorted_chats:
            if not self.running:
                break
                
            print(f"Обработка чата '{chat_name}' ({len(tasks)} задач)")
            
            # Открываем чат один раз
            if self.open_chat(chat_name):
                # Обрабатываем все задачи этого чата
                for task in tasks:
                    if not self.running:
                        break
                    self.process_single_task(task)
                    time.sleep(2)  # Пауза между сообщениями
                    
            # Проверяем, нужен ли перезапуск браузера
            if self.operation_count > self.max_operations and self.running:
                print("Перезапуск браузера...")
                self.init_browser()

    def open_chat(self, contact_name):
        """Открывает чат"""
        try:
            if not self.driver:
                return False
                
            # Поиск чата
            search_selectors = [
                (By.CSS_SELECTOR, '[aria-label="Поиск контактов или групп"]'),
                (By.CSS_SELECTOR, '[aria-label="Search contacts or groups"]'),
                (By.XPATH, '//div[@contenteditable="true" and @data-tab="3"]'),
            ]
            
            search_box = None
            for by_type, selector in search_selectors:
                try:
                    search_box = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    break
                except TimeoutException:
                    continue
                    
            if not search_box:
                print("Не удалось найти поле поиска")
                return False
                
            search_box.clear()
            search_box.send_keys(contact_name)
            time.sleep(1)
            
            # Открываем чат
            contact = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f'//span[@title="{contact_name}"]'))
            )
            contact.click()
            time.sleep(1)
            
            print(f"Чат '{contact_name}' открыт")
            return True
            
        except Exception as e:
            print(f"Ошибка открытия чата '{contact_name}': {e}")
            return False

    def process_single_task(self, task):
        """Обрабатывает одну задачу"""
        try:
            # Перемещаем в processing
            processing_path = os.path.join(self.processing_dir, os.path.basename(task['_filepath']))
            os.rename(task['_filepath'], processing_path)
            
            # Обрабатываем в зависимости от типа
            if task['content_type'] == 'text':
                success = self.send_message(task['message'])
            elif task['content_type'] == 'image':
                success = self.send_file(task['file_path'], task['message'])
            else:
                print(f"Неизвестный тип контента: {task['content_type']}")
                success = False
                
            if success:
                # Удаляем при успехе
                os.remove(processing_path)
                print(f"Задача {task['id']} выполнена успешно")
                self.operation_count += 1
            else:
                # Перемещаем в failed
                self.move_to_failed(processing_path, task, "Ошибка отправки")
                
        except Exception as e:
            print(f"Критическая ошибка обработки задачи {task['id']}: {e}")
            try:
                self.move_to_failed(processing_path, task, str(e))
            except:
                pass

    def send_message(self, message):
        """Отправляет текстовое сообщение"""
        try:
            if not self.driver:
                return False
                
            message_selectors = [
                (By.CSS_SELECTOR, 'div[aria-label="Введите сообщение"]'),
                (By.CSS_SELECTOR, 'div[aria-label="Type a message"]'),
                (By.XPATH, '//div[@contenteditable="true" and @data-tab="10"]'),
            ]
            
            message_box = None
            for by_type, selector in message_selectors:
                try:
                    message_box = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                    break
                except TimeoutException:
                    continue
                    
            if not message_box:
                print("Не удалось найти поле для сообщения")
                return False
                
            message_box.send_keys(message)
            message_box.send_keys(Keys.ENTER)
            return True
            
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
            return False

    def send_file(self, file_path, caption):
        """Отправляет файл"""
        try:
            if not self.driver:
                return False
                
            # Нажимаем на кнопку "Прикрепить"
            attach_selectors = [
                (By.CSS_SELECTOR, 'button[title="Прикрепить"]'),
                (By.CSS_SELECTOR, 'button[title="Attach"]'),
                (By.CSS_SELECTOR, 'span[data-icon="clip"]'),
            ]
            
            attach_btn = None
            for by_type, selector in attach_selectors:
                try:
                    attach_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    break
                except TimeoutException:
                    continue
                    
            if not attach_btn:
                print("Не удалось найти кнопку прикрепления")
                return False
                
            attach_btn.click()
            
            # Находим input для файлов
            file_input = WebDriverWait(self.driver, 4).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"][accept*="image"]'))
            )
            
            absolute_file_path = os.path.abspath(file_path)
            file_input.send_keys(absolute_file_path)
            time.sleep(3)
            
            # Добавляем подпись, если есть
            if caption:
                caption_selectors = [
                    (By.CSS_SELECTOR, 'div[aria-label="Введите сообщение"]'),
                    (By.CSS_SELECTOR, 'div[aria-label="Type a message"]'),
                ]
                
                caption_box = None
                for by_type, selector in caption_selectors:
                    try:
                        caption_box = WebDriverWait(self.driver, 1).until(
                            EC.presence_of_element_located((by_type, selector))
                        )
                        break
                    except TimeoutException:
                        continue
                        
                if caption_box:
                    caption_box.send_keys(caption)
                    
            # Кликаем на кнопку отправки
            send_selectors = [
                'div[aria-label="Отправить"]',
                'div[aria-label="Send"]',
                'div[data-icon="wds-ic-send-filled"]',
                '[data-icon="wds-ic-send-filled"]'
            ]
            
            for selector in send_selectors:
                try:
                    send_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    send_btn.click()
                    return True
                except TimeoutException:
                    continue
                    
            print("Не удалось найти кнопку отправки")
            return False
            
        except Exception as e:
            print(f"Ошибка отправки файла: {e}")
            return False

    def move_to_failed(self, processing_path, task, error_message):
        """Перемещает задачу в папку failed с логом ошибки"""
        if 'attempts' not in task:
            task['attempts'] = 0
        task['attempts'] += 1
        task['last_error'] = error_message
        task['failed_time'] = time.time()
        
        failed_path = os.path.join(self.failed_dir, os.path.basename(processing_path))
        
        try:
            with open(failed_path, 'w', encoding='utf-8') as f:
                json.dump(task, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка записи в failed: {e}")
            
        try:
            os.remove(processing_path)
        except Exception as e:
            print(f"Ошибка удаления файла из processing: {e}")

    def cleanup(self):
        """Очистка ресурсов"""
        print("Выполняется cleanup...")
        
        if self.driver:
            try:
                self.driver.quit()
                print("Драйвер закрыт")
            except Exception as e:
                print(f"Ошибка при закрытии драйвера: {e}")
            finally:
                self.driver = None
                
        if self.service:
            try:
                self.service.stop()
                print("Сервис остановлен")
            except Exception as e:
                print(f"Ошибка при остановке сервиса: {e}")
            finally:
                self.service = None
                
        # Убиваем процессы Chrome
        self._kill_chrome_processes()
        
        print("Cleanup завершён")

    def __del__(self):
        """Деструктор для гарантии cleanup"""
        self.cleanup()
