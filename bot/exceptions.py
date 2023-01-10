class ApiRequestError(Exception):
    """Не удалось отправить запрос на api эндпоинт."""
    pass


class MessageNotSentError(Exception):
    """Не удалось отправить сообщение в телеграмм."""
    pass
