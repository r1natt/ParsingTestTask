import requests
from bs4 import BeautifulSoup
from typing import TypeAlias
import json
import re
from prettytable import PrettyTable
from pprint import pprint
import logging

from logger import setup_logger
from config import USER, PASSWORD
from errors import AuthError, BadResponse

setup_logger()

logger = logging.getLogger(__name__)

Token: TypeAlias = str
phpMyAdminType: TypeAlias = str

SESSION = requests.Session()

BASE_URL = "http://185.244.219.162/phpmyadmin/"


def get_login_page() -> (Token, phpMyAdminType):
    """
    Данный запрос нужен для получения токена и значения куки phpMyAdmin формы
    авторизации.

    phpMyAdmin сохраняется в куки сессии session
    """

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }

    response = SESSION.get(
        BASE_URL,
        headers=headers
    )

    return get_token(response.text)

def post_auth(token: Token, phpMyAdmin: phpMyAdminType):
    """
    Имитация авторизации в админке. Данная функция нужна для того, чтобы админка
    выслала мне в куках pmaUser-1 и pmaAuth-1, которые SESSION сохраняет
    самостоятельно, поэтому функция ничего не возвращает
    """

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }

    payload = {
        "set_session": phpMyAdmin,
        "pma_username": USER,
        "pma_password": PASSWORD,
        "server": "1",
        "route": "/",
        "lang": "ru",
        "token": token
    }

    response = SESSION.post(
        BASE_URL + "index.php",
        headers=headers,
        data=payload
    )

    if response.cookies.get("pmaUser-1") is None or \
        response.cookies.get("pmaAuth-1") is None:
        raise AuthError("Не удалось авторизоваться")
    else:
        logger.info("Успешный логин")

    if not response.ok:
        raise BadResponse("Плохой ответ")

def get_token(html_page) -> (Token, phpMyAdminType):
    """
    На странице логина ищу форму, из которой получаю токен и phpMyAdmin значение
    сессии
    """
    soup = BeautifulSoup(html_page, "html.parser")

    try:
        form = soup.find("form", {"id": "login_form"})

        token = form.find("input", {"name": "token"})["value"]
        phpMyAdmin = form.find("input", {"name": "set_session"})["value"]
    except Exception as e:
        logger.exception(e)
        raise e

    return (token, phpMyAdmin)

def get_table_sql(token):
    """
    Запрос на получение таблицы users. Не указаваю куки явно, так как они
    сохранены в сессии и отправляются автоматически
    """

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    }

    payload = {
        "route": "/sql",
        "server": "1",
        "db": "testDB",
        "table": "users",
        "pos": "0",
        "ajax_request": "true",
        "ajax_page_request": "true",
        "token": token
    }

    response = SESSION.get(
        BASE_URL + "index.php",
        headers=headers,
        params=payload
    )

    json_response_text = json.loads(response.text)

    html_page = json_response_text['message']

    return html_page

def parse_users_table(html_page) -> (list[str], list[list[str | int]]):
    """
    Парсинг данных из таблицы users. Отдельно headers, отдельно данные
    """
    soup = BeautifulSoup(html_page, "html.parser")

    table = soup.find("table", {"class": "data"})

    try:
        thead = table.find("thead")
        header_row = parse_table_headers(thead)

        tbody = table.find("tbody")
        data_rows = parse_table_divs(tbody)
    except Exception as e:
        logger.exception(e)
        raise e

    logger.info("Успешный парсинг таблицы, headers: %s, data: %s", header_row, data_rows)

    return (header_row, data_rows)

def parse_table_headers(thead_part):
    """
    Парсинг header`ов из таблицы
    """
    column_headers = thead_part.find_all("th", class_="column_heading")

    header_row = []

    for header in column_headers:
        header_object = header.find("a", class_="sortlink")

        for child in header_object.children:

            # Проверка ниже нужна, если в теге будет содержаться текст в тегах
            # <small> или <span>, текст которых функция get_text() тоже примет
            # как текст
            if isinstance(child, str):
                header_row.append(child)
                break

    return header_row

def parse_table_divs(tbody_part):
    """
    Парсинг данных из таблицы
    """
    data_rows = []

    raw_rows = tbody_part.find_all("tr")

    for row in raw_rows:
        parsed_row = []

        table_divs = row.find_all("td", {"class": "data"})
        for item in table_divs:
            parsed_row.append(item.get_text())

        data_rows.append(parsed_row)

    return data_rows

def print_table(header_row: list[str], data_rows: list[list[str | int]]):
    """
    Выводит таблицу в красивом виде
    """
    table = PrettyTable()

    table.field_names = header_row

    for row in data_rows:
        table.add_row(row)

    print(table)

def hide_string_part(s: str):
    """Сокращает значения"""
    if not isinstance(s, str):
        raise TypeError("входная строка должна быть строкой :|")
    if len(s) < 11:
        return f"{s[:1]}...{s[-1:]}"
    return f"{s[:5]}...{s[-5:]}"


if __name__ == "__main__":
    token, phpMyAdmin = get_login_page()
    logger.info(
        "token: %s, phpMyAdmin: %s",
        hide_string_part(token),
        hide_string_part(phpMyAdmin)
    )
    post_auth(token, phpMyAdmin)

    html_page = get_table_sql(token)

    header_row, data_rows = parse_users_table(html_page)

    print("Таблица users:")

    print_table(header_row, data_rows)
