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
handlers = [handler, stdout_handler]
logger.addHandler(handlers)
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
    logger.info('Бот запущен')
    current_timestamp = int(time.time())
    ERROR_MESSAGE = ''
    current_report = {}
    prev_report = {}
    if not check_tokens():
        logger.critical('Проверь переменные')
        raise sys.exit('Проверь переменные')
    while True:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get(
                'current_date'
            ) or int(time.time())
            if check_response(response) != []:
                message = parse_status(check_response(response))
                current_report[
                    check_response(response)['homework_name']
                ] = check_response(response)['status']
                if current_report != prev_report:
                    send_message(bot, message)
                else:
                    prev_report = current_report.copy()
            else:
                time.sleep(RETRY_TIME)
        except Exception as error:
            logger.error(error)
            message_e = f'Сбой в работе программы: {error}'
            if message_e != ERROR_MESSAGE:
                send_message(bot, message_e)
                ERROR_MESSAGE = message_e
            time.sleep(RETRY_TIME)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logger.info('Сообщение отправлено в чат')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        raise Exception(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Отправлен запрос на сервер Я.П.')
        homework_obj = requests.get(url=ENDPOINT,
                                    headers=HEADERS,
                                    params=params)
    except Exception as error:
        raise Exception(f'Ошибко {error} при запросе к API')
    if homework_obj.status_code != HTTPStatus.OK:
        status_code = homework_obj.status_code
        raise Exception(f'Ошибка доступа к API - {status_code}'
                        f'{ENDPOINT}'
                        f'{HEADERS}'
                        f'{params}')
    return homework_obj.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if isinstance(response, list):
        raise TypeError('Ответ API отличен от словаря')
    try:
        works = response['homeworks']
    except KeyError:
        raise KeyError('Ошибка словаря по ключу homeworks')
    if works != []:
        homework = works[0]
        return homework
    else:
        return works


def parse_status(homework):
    """Извлечение информации о статус конкретной работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


if __name__ == '__main__':
    main()
