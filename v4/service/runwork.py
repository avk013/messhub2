# run_worker.py - Запуск воркера
import sys
import os

def main():
    try:
        # Создаём необходимые директории
        dirs = [
            "queue/whatsapp/pending",
            "queue/whatsapp/processing", 
            "queue/whatsapp/failed"
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
            
        from whatswork import WhatsAppWorker
        worker = WhatsAppWorker()
        worker.start()
        
    except KeyboardInterrupt:
        print("\nОстановка по Ctrl+C")
        sys.exit(0)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        print("Программа завершена")

if __name__ == "__main__":
    main()
