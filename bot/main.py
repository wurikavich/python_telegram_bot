import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ApiRequestError, CurrentDateError, MessageNotSentError

load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'}


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError(message) as error:
        raise MessageNotSentError(f'Ошибка отправки сообщения:{message}.'
                                  f'Информация об ошибке: {error}')
    else:
        logger.info(f'Отправлено сообщение в чат {TELEGRAM_CHAT_ID}:{message}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    api_params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': current_timestamp})
    try:
        homework = requests.get(**api_params)
        if homework.status_code != HTTPStatus.OK:
            raise Exception(f'Ошибка {homework.status_code}')
        return homework.json()
    except Exception:
        raise ApiRequestError(f'Ошибка при получении ответа с сервера. '
                              f'Парамметры запроса - {api_params}.')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('В ответе API нет словаря с домашками')
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise CurrentDateError('В ответе API нет данных о времени')
    if not isinstance(homeworks, list):
        raise TypeError('Ответ API отличен от списка')
    logging.info(f"Проверка API успешно пройдена."
                 f"Время последнего запроса к серверу: {current_date}")
    return homeworks


def parse_status(homework):
    """Извлекает информацию о статусе домашней работе статус."""
    homework_name = homework.get('homework_name')
    logger.info(f'Начинаю извлекать информация о проекте {homework_name}.')
    if homework_name is None:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.info(f'Изменился статус проверки работы - "{verdict}".')
    homeworks_comment = homework.get('reviewer_comment')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if verdict == HOMEWORK_VERDICTS['approved']:
        info_message = (f'Молодец! Очень горжусь тобой! Ты успешно справился с'
                        f' этим проектом.\nРевьер оставил тебе комментарий:'
                        f' "{homeworks_comment}" \n'
                        f'Впереди ждут новые трудности и новые победы.')
        send_message(bot, info_message)
    if verdict == HOMEWORK_VERDICTS['rejected']:
        info_message = (f'Не буду томить ожиданием. Ревьер вернул проект на '
                        f'доработку с комментарием "{homeworks_comment}"\nЭто'
                        f' не повод расстраиваться и всё бросить, прежде всего'
                        f' это новый опыт, ведь дальше будет сложнее. Отдохни,'
                        f' потом преступи к работе над ошибками. Удачи!')
        send_message(bot, info_message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        sys.exit('Отсутствуют одна или несколько переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logger.info('Запуск программы')
    info_message = ('Привет, я твой личный ассистент.\n'
                    'Я буду сообщать когда проект взят на проверку и есть ли '
                    'замечания.\nЕсли у меня возникнут трудности, я напишу.')
    send_message(bot, info_message)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_list = check_response(response)
            if len(homework_list) > 0:
                send_message(bot, parse_status(homework_list[0]))
            current_timestamp = response.get('current_date', current_timestamp)
        except (CurrentDateError, MessageNotSentError) as error:
            logger.error(error, exc_info=True)
        except Exception as error:
            logger.error(error, exc_info=True)
            send_message(bot, f'Сбой в работе программы: {error}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=('%(asctime)s,'
                ' %(levelname)s,'
                ' %(message)s,'
                ' %(funcName)s,'
                ' %(lineno)d'),
        encoding='UTF-8',
        handlers=[logging.FileHandler(
            'logging/main.log',
            mode='w',
            encoding='UTF-8'),
            logging.StreamHandler(sys.stdout)])
    main()
