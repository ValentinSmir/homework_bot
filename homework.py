import logging
import os
import requests
import time
from dotenv import load_dotenv
from telebot import TeleBot


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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено в Telegram')
    except Exception as error:
        logger.error(f'сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            logger.error(
                f'Эндпоинт {ENDPOINT} недоступен.'
                'Код ответа API: {response.status_code}')
            raise requests.RequestException(
                f'Код ответа API: {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
        raise RuntimeError(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        logger.error('Ключ "homeworks" отсутствует в ответе API')
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа "homeworks" не является списком')
    if len(response['homeworks']) == 0:
        logger.debug('Отсутствие новых статусов')
    return response['homeworks']


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


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют необходимые переменные окружения')
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
