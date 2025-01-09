import telebot
import config
from pybit.unified_trading import HTTP

# Reemplaza "BOT_TOKEN" con tu token de acceso proporcionado por BotFather en Telegram
bot_token = config.token_telegram

# Inicializa el bot
bot = telebot.TeleBot(bot_token)

# Ruta del archivo donde se guardarán los mensajes
archivo_mensajes = "symbols_targets.txt"

# Inicializa la sesión de Bybit en testnet
session = HTTP(testnet=False)

# Función para obtener la lista de símbolos desde Bybit
def obtener_lista_simbolos():
    try:
        response = session.get_tickers(category="linear")
        if response["retCode"] == 0:
            return [item["symbol"] for item in response["result"]["list"]]
    except Exception as e:
        print(f"Error al obtener la lista de símbolos: {e}")
    return []

# Función para manejar el comando /point
@bot.message_handler(commands=['point'])
def handle_point_command(message):
    try:
        # Extraer los argumentos del mensaje (formato: /point BTCUSDT 35400.14)
        _, symbol, price = message.text.split()
        mensaje = f"{symbol} {price}"
        
        # Verificar si el símbolo está en la lista de Bybit
        lista_simbolos = obtener_lista_simbolos()
        if symbol in lista_simbolos:
            try:
                # Guardar el mensaje en el archivo
                guardar_mensaje_en_archivo(mensaje)
                # Confirmar al usuario que se ha guardado correctamente
                bot.reply_to(message, f"Guardado: {mensaje}")
            except Exception as e:
                bot.reply_to(message, f"Error al guardar el mensaje: {e}")
        else:
            # Informar al usuario que el símbolo no está listado en Bybit
            bot.reply_to(message, "Esta moneda no se encuentra enlistada en Bybit.")
    except ValueError:
        bot.reply_to(message, "Formato incorrecto. Uso esperado: /point <symbol> <price>")
    except Exception as e:
        bot.reply_to(message, f"Ocurrió un error: {e}")

# Función para manejar el comando /borrar
@bot.message_handler(commands=['borrar'])
def handle_borrar_command(message):
    try:
        # Borrar el contenido del archivo
        with open(archivo_mensajes, "w") as file:
            file.write("")
        # Confirmar al usuario que el archivo se ha borrado
        bot.reply_to(message, "El archivo ha sido borrado.")
    except Exception as e:
        bot.reply_to(message, f"Error al borrar el archivo: {e}")

# Función para guardar el mensaje en el archivo
def guardar_mensaje_en_archivo(mensaje):
    with open(archivo_mensajes, "a") as file:
        file.write(mensaje + "\n")

# Iniciar el bot y esperar mensajes
bot.polling()
