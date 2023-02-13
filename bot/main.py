import sys
import time
from http import HTTPStatus

import requests
import telegram

import config
import logging
from exceptions import ApiRequestError, MessageNotSentError

logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(config.TELEGRAM_ID, text=message)
    except telegram.error.TelegramError(message) as error:
        raise MessageNotSentError(
            f'Сообщение "{message}" не удалось отправить! Ошибка: {error}.'
        )
    else:
        logger.info(
            f'Сообщение "{message}", успешно отправлено '
            f'пользователю с ID={config.TELEGRAM_ID}'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    api_params = dict(
        url=config.ENDPOINT,
        headers=config.HEADERS,
        params={'from_date': current_timestamp}
    )
    try:
        homework = requests.get(**api_params)
        if homework.status_code != HTTPStatus.OK:
            raise Exception(
                'Не удалось получить данные от сервера! '
                f'Код ответа сервера - {homework.status_code}.'
            )
        return homework.json()
    except Exception as error:
        raise ApiRequestError(
            f'Не удалось отправить запрос - {api_params}! Ошибка - {error}.'
        )


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Получен неверный формат данных!')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('В данных нет информации о проектах!')
    current_date = response.get('current_date')
    if not isinstance(current_date, int) or not isinstance(homeworks, list):
        raise TypeError('Получен неверный формат данных!')
    logging.info(f'Время последнего запроса к серверу: {current_date}.')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о статусе домашней работе статус."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('В данных нет информации о проекте!')
    homework_status = homework.get('status')
    if homework_status not in config.HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус работы: {homework_status}')
    homeworks_comment = homework.get('reviewer_comment')
    verdict = config.HOMEWORK_VERDICTS[homework_status]
    logger.info(f'Статус проверки "{homework_name}" изменился - {verdict}')
    if verdict == config.HOMEWORK_VERDICTS["approved"]:
        return (
            f'Молодец! Ты успешно справился этим проектом.\n'
            f'Ревьер оставил тебе комментарий: "{homeworks_comment}".\n'
            f'Впереди ждут новые трудности и новые победы.'
        )
    elif verdict == config.HOMEWORK_VERDICTS["rejected"]:
        return (
            f'Не буду томить ожиданием. Ревьюер вернул проект на доработку'
            f' с комментарием: "{homeworks_comment}".\n'
            f'Это не повод расстраиваться и всё бросать, прежде всего это '
            f'новый опыт, ведь дальше будет сложнее. '
            f'Отдохни, потом преступи к работе над ошибками. Удачи!'
        )
    return f'Статус проверки "{homework_name}" изменился - {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all(
        [config.YANDEX_TOKEN, config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_ID]
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения!')
        sys.exit('Отсутствуют одна или несколько переменных окружения!')
    bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
    current_timestamp = int(time.time())
    logger.info('Telegram bot запущен.')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_list = check_response(response)
            if len(homework_list) > 0:
                send_message(bot, parse_status(homework_list[0]))
            current_timestamp = response.get('current_date', current_timestamp)
        except MessageNotSentError as error:
            logger.error(error, exc_info=True)
        except Exception as error:
            logger.error(error, exc_info=True)
            send_message(bot, f'Сбой в работе программы: "{error}".')
        finally:
            time.sleep(config.REQUEST_RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=(
            '%(asctime)s,'
            ' %(levelname)s,'
            ' %(message)s,'
            ' %(funcName)s,'
            ' %(lineno)d'
        ),
        encoding='UTF-8',
        handlers=[
            logging.FileHandler('logging/log.log', mode='w', encoding='UTF-8'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    main()
