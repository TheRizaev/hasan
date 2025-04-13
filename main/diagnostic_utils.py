import logging
from .gcs_storage import get_bucket, BUCKET_NAME
import json
import os
from django.conf import settings
import datetime

logger = logging.getLogger(__name__)

def inspect_gcs_storage():
    """
    Исследует содержимое GCS бакета и выводит информацию о структуре
    """
    try:
        bucket = get_bucket(BUCKET_NAME)
        if not bucket:
            logger.error(f"Не удалось получить доступ к бакету {BUCKET_NAME}")
            return None
            
        # Получаем все блобы в бакете
        blobs = list(bucket.list_blobs())
        
        # Словарь для хранения структуры папок
        folder_structure = {}
        
        # Анализируем пути файлов
        for blob in blobs:
            path_parts = blob.name.split('/')
            
            # Пропускаем слишком короткие пути
            if len(path_parts) < 2:
                continue
                
            # Получаем имя пользователя (первая часть пути)
            username = path_parts[0]
            
            # Инициализируем структуру для пользователя
            if username not in folder_structure:
                folder_structure[username] = {
                    'videos': [],
                    'previews': [],
                    'metadata': [],
                    'comments': [],
                    'bio': []
                }
            
            # Определяем тип файла
            if len(path_parts) >= 3:
                folder_type = path_parts[1]
                filename = path_parts[2]
                
                if folder_type in folder_structure[username]:
                    folder_structure[username][folder_type].append(filename)
        
        # Выводим информацию о структуре хранилища
        logger.info(f"=== Структура GCS хранилища ===")
        logger.info(f"Найдено пользователей: {len(folder_structure)}")
        
        for username, folders in folder_structure.items():
            logger.info(f"Пользователь: {username}")
            for folder_type, files in folders.items():
                logger.info(f"  - {folder_type}: {len(files)} файлов")
                # Выводим несколько первых файлов для примера
                for i, file in enumerate(files[:3]):
                    logger.info(f"    * {file}")
                if len(files) > 3:
                    logger.info(f"    * ... и еще {len(files) - 3} файлов")
        
        return folder_structure
        
    except Exception as e:
        logger.error(f"Ошибка при инспектировании GCS: {e}")
        return None

def fix_user_folder_structure(username):
    """
    Исправляет структуру папок пользователя в GCS
    
    Args:
        username (str): Имя пользователя (с префиксом @)
    """
    try:
        from .gcs_storage import create_user_folder_structure
        result = create_user_folder_structure(username)
        
        if result:
            logger.info(f"Структура папок для пользователя {username} успешно создана/исправлена")
        else:
            logger.error(f"Не удалось создать/исправить структуру папок для пользователя {username}")
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при исправлении структуры папок: {e}")
        return False

def get_video_details(username, video_id):
    """
    Получает подробную информацию о видео из GCS
    
    Args:
        username (str): Имя пользователя (с префиксом @)
        video_id (str): ID видео
    """
    try:
        from .gcs_storage import get_video_metadata, get_video_comments, generate_video_url
        
        # Получаем метаданные видео
        metadata = get_video_metadata(username, video_id)
        if not metadata:
            logger.error(f"Не удалось найти метаданные для видео {video_id}")
            return None
            
        # Получаем комментарии к видео
        comments = get_video_comments(username, video_id)
        
        # Генерируем временный URL для видео
        video_url = generate_video_url(username, video_id, expiration_time=3600)
        
        # Генерируем URL для миниатюры, если она существует
        thumbnail_url = None
        if "thumbnail_path" in metadata:
            thumbnail_url = generate_video_url(
                username, 
                video_id, 
                file_path=metadata["thumbnail_path"], 
                expiration_time=3600
            )
        
        # Объединяем информацию
        video_info = {
            "metadata": metadata,
            "comments": comments,
            "urls": {
                "video": video_url,
                "thumbnail": thumbnail_url
            }
        }
        
        return video_info
    
    except Exception as e:
        logger.error(f"Ошибка при получении информации о видео: {e}")
        return None

def create_debug_log(info=None):
    """
    Создает подробный лог-файл с диагностической информацией
    
    Args:
        info (dict, optional): Дополнительная информация для включения в лог
    """
    try:
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"gcs_debug_{timestamp}.log")
        
        # Собираем диагностическую информацию
        debug_info = {
            "timestamp": timestamp,
            "bucket_name": BUCKET_NAME,
            "gcs_structure": inspect_gcs_storage()
        }
        
        # Добавляем пользовательскую информацию, если она предоставлена
        if info:
            debug_info["additional_info"] = info
        
        # Сохраняем в файл
        with open(log_path, 'w') as f:
            f.write(json.dumps(debug_info, indent=2))
            
        logger.info(f"Файл отладки создан: {log_path}")
        return log_path
    
    except Exception as e:
        logger.error(f"Ошибка при создании файла отладки: {e}")
        return None

# Функция для запуска из командной строки Django
def run_diagnostics():
    print("Запуск диагностики GCS хранилища...")
    structure = inspect_gcs_storage()
    
    if structure:
        # Проверяем наличие каталогов пользователей
        user_count = len(structure)
        print(f"Найдено {user_count} пользователей в GCS")
        
        # Проверяем структуру каждого пользователя
        for username, folders in structure.items():
            print(f"\nПроверка структуры папок пользователя {username}:")
            
            # Проверяем наличие всех необходимых папок
            missing_folders = []
            for folder_type in ['videos', 'previews', 'metadata', 'comments', 'bio']:
                if folder_type not in folders or not folders[folder_type]:
                    missing_folders.append(folder_type)
                    
            if missing_folders:
                print(f"ВНИМАНИЕ: Отсутствуют или пусты следующие папки: {', '.join(missing_folders)}")
                answer = input(f"Хотите исправить структуру папок для пользователя {username}? (y/n): ")
                if answer.lower() == 'y':
                    if fix_user_folder_structure(username):
                        print(f"Структура папок для пользователя {username} исправлена")
                    else:
                        print(f"Не удалось исправить структуру папок для пользователя {username}")
            else:
                print(f"Структура папок для пользователя {username} в порядке")
                
            # Проверяем наличие видео
            if 'videos' in folders and folders['videos']:
                print(f"Найдено {len(folders['videos'])} видео")
                
                # Проверяем соответствие видео и метаданных
                if 'metadata' in folders:
                    metadata_count = len(folders['metadata'])
                    print(f"Метаданных: {metadata_count}")
                    
                    if metadata_count != len(folders['videos']):
                        print(f"ВНИМАНИЕ: Количество метаданных не соответствует количеству видео")
    else:
        print("Не удалось получить информацию о структуре GCS")
    
    print("\nДиагностика завершена")