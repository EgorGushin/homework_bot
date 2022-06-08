import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
handler = RotatingFileHandler('bot.log',
                              maxBytes=50000000,
                              backupCount=5
                              )
logger.addHandler(handler)
logger.addHandler(stdout_handler)
formatter = logging.Formatter(
    '%(asctime)s, %(lineno)s, %(levelname)s, %(funcName)s, %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Проверь переменные')
        raise sys.exit('Проверь переменные')
    current_timestamp = int(time.time())
    error_message = ''
    current_report = dict()
    prev_report = dict()
    logger.info('Бот запущен. Работаем!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get(
                'current_date',
                current_timestamp
            )
            all_homeworks = check_response(response)
            if all_homeworks:
                homework = all_homeworks[0]
                message = parse_status(homework)
                current_report[
                    homework['homework_name']
                ] = homework['status']
                if current_report != prev_report:
                    send_message(bot, message)
                    prev_report = current_report.copy()
        except Exception as error:
            logger.error(error)
            message_e = f'Сбой в работе программы: {error}'
            if message_e != error_message:
                send_message(bot, message_e)
                error_message = message_e
        finally:
            time.sleep(RETRY_TIME)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено в чат')
    except Exception as error:
        raise Exception(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Отправлен запрос на сервер Я.П.')
        http_response = requests.get(url=ENDPOINT,
                                     headers=HEADERS,
                                     params=params)
    except Exception as error:
        raise Exception(f'Ошибко {error} при запросе к API')
    if http_response.status_code != HTTPStatus.OK:
        status_code = http_response.status_code
        raise Exception(f'Ошибка доступа к API - {status_code}'
                        f'{ENDPOINT}'
                        f'{HEADERS}'
                        f'{params}')
    return http_response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    try:
        works = response['homeworks']
        logger.info(f'Получен ответ {works}')
    except KeyError:
        raise KeyError('Ошибка словаря по ключу homeworks')
    if not isinstance(works, list):
        raise TypeError('Список работ не список')
    return works


def parse_status(homework):
    """Извлечение информации о статус конкретной работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API.')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API.')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    """
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


if __name__ == '__main__':
    main()
