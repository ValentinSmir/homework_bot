import logging
import os
import sys
import time
from dotenv import load_dotenv
from http import HTTPStatus
from telebot import TeleBot

import requests
from telebot.apihelper import ApiException


load_dotenv()


PRACTICUM_TOKEN = os.getenv('P_TOKEN')
TELEGRAM_TOKEN = os.getenv('T_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('T_CHAT')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
handlers = logging.StreamHandler(sys.stdout)
handlers.setLevel(logging.DEBUG)
logger.addHandler(handlers)


class ErrorRequestingAPI(Exception):
    """Кастомная ошибка кода ответа API."""
    pass


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    no_tokens = []
    for name, token in tokens_dict.items():
        if token is None:
            logger.critical(
                f'Отсутствуют необходимые переменные окружения: {name}')
            no_tokens.append(name)
    if no_tokens:
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение."""
    logger.debug('Попытка отправить сообщение')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено в Telegram')
        return True
    except (ApiException, requests.RequestException) as error:
        logger.error(f'сбой при отправке сообщения в Telegram: {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API сервиса."""
    params = {'from_date': timestamp}
    logger.debug('Начинается запрос к API')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise ErrorRequestingAPI(
            f'Код ответа API: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем: получили'
                        f'{type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" не является списком')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'status' not in homework or 'homework_name' not in homework:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Неожиданный статус домашней работы: {status}')
        raise ValueError(f'Неожиданный статус домашней работы: {status}')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def error_handing(bot, error, last_message):
    """Обработка ошибок и обновление сообщения."""
    message = f'Сбой в работе программы: {error}'
    logger.error(message)
    if last_message != message:
        try:
            if send_message(bot, message):
                last_message = message
        except Exception as error:
            logger.error(f'Ошибка при отправке сообщения: {error}')
    return last_message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Отсутствуют необходимые переменные окружения')

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
        except Exception as error:
            error_handing(bot, error, last_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format='%(asctime)s, %(module)s, %(name)s'
        '%(levelname)s, %(message)s')
    main()
