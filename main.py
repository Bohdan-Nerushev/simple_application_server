import mimetypes
import urllib.parse
import json
import logging
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

# Define base directory and static files directory
# Визначаємо базову директорію та директорію статичних файлів
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
DATA_DIR = BASE_DIR / 'data'

# Constants for buffer size, HTTP and socket server ports
# Константи для розміру буфера, портів HTTP та сокет сервера
BUFFER_SIZE = 1024
HTTP_PORT = 3000
HTTP_HOST = '127.0.0.1'
SOCKET_HOST = '127.0.0.1'
SOCKET_PORT = 5000

# Initialize Jinja environment for HTML templating
# Ініціалізуємо середовище Jinja для HTML шаблонів
jinja = Environment(loader=FileSystemLoader(STATIC_DIR))


class FrameWork(BaseHTTPRequestHandler):

    def do_GET(self):
        # Handle GET requests
        # Обробляємо GET запити
        route = urllib.parse.urlparse(self.path)
        match route.path:
            case '/':
                self.send_html('index.html')
            case '/message':
                self.send_html('message.html')
            case _:
                # Serve static files if exists, otherwise return error page
                # Сервіруємо статичні файли, якщо вони існують, інакше повертаємо сторінку помилки
                file = STATIC_DIR.joinpath(route.path[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html('error.html', 404)

    def do_POST(self):
        # Handle POST requests (form submissions)
        # Обробляємо POST запити (відправлення форм)
        size = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(size)

        # Send data to socket server for further processing
        # Відправляємо дані на сокет сервер для подальшої обробки
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(data, (SOCKET_HOST, SOCKET_PORT))
        client_socket.close()

        # Redirect to /message after form submission
        # Перенаправляємо на /message після відправлення форми
        self.send_response(302)
        self.send_header('Location', '/message')
        self.end_headers()

    def send_html(self, filename, status_code=200):
        # Helper method to send HTML responses
        # Допоміжний метод для відправки HTML відповідей
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        with open(STATIC_DIR / filename, 'rb') as file:
            self.wfile.write(file.read())

    def render_template(self, filename, status_code=200):
        # Helper method to render HTML templates using Jinja
        # Допоміжний метод для рендерингу HTML шаблонів з використанням Jinja
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()

        # Load data from data.json for rendering templates
        # Завантажуємо дані з data.json для рендерингу шаблонів
        with open(DATA_DIR / 'data.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        template = jinja.get_template(filename)
        message = None  # "Hello Sergiy!"
        html = template.render(blogs=data, message=message)
        self.wfile.write(html.encode())

    def send_static(self, filename, status_code=200):
        # Helper method to serve static files
        # Допоміжний метод для сервірування статичних файлів
        self.send_response(status_code)
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            self.send_header('Content-Type', mime_type)
        else:
            self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        with open(filename, 'rb') as file:
            self.wfile.write(file.read())


def save_data_from_form(data):
    # Save form data received to data.json
    # Зберігаємо отримані дані з форми у data.json
    parse_data = urllib.parse.unquote_plus(data.decode())
    try:
        parse_dict = {key: value for key, value in [el.split('=') for el in parse_data.split('&')]}
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        new_data = {
            timestamp: parse_dict
        }

        # Load existing data from data.json
        # Завантажуємо існуючі дані з data.json
        data_path = DATA_DIR / 'data.json'
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
        else:
            existing_data = {}

        # Update existing data with new data
        # Оновлюємо існуючі дані новими даними
        existing_data.update(new_data)

        # Save updated data back to file
        # Зберігаємо оновлені дані назад у файл
        with open(data_path, 'w', encoding='utf-8') as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=4)
    except ValueError as err:
        logging.error(err)
    except OSError as err:
        logging.error(err)


def run_socket_server(host, port):
    # Function to run UDP socket server
    # Функція для запуску UDP сокет сервера
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((host, port))
    logging.info("Starting socket server")
    try:
        while True:
            msg, address = server_socket.recvfrom(BUFFER_SIZE)
            logging.info(f"Socket received {address}: {msg}")
            save_data_from_form(msg)
    except KeyboardInterrupt:
        pass
    finally:
        server_socket.close()


def run_http_server(host, port):
    # Function to run HTTP server using BaseHTTPRequestHandler
    # Функція для запуску HTTP сервера за допомогою BaseHTTPRequestHandler
    address = (host, port)
    http_server = HTTPServer(address, FrameWork)
    logging.info(f"Starting http server at {host}:{port}")
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()


if __name__ == '__main__':
    # Set up logging configuration
    # Налаштування конфігурації логування
    logging.basicConfig(level=logging.DEBUG, format='%(threadName)s %(message)s')

    # Create directories if they don't exist
    # Створюємо директорії, якщо вони не існують
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Start HTTP server and socket server in separate threads
    # Запускаємо HTTP сервер та сокет сервер у різних потоках
    server = Thread(target=run_http_server, args=(HTTP_HOST, HTTP_PORT))
    server.start()

    server_socket = Thread(target=run_socket_server, args=(SOCKET_HOST, SOCKET_PORT))
    server_socket.start()
