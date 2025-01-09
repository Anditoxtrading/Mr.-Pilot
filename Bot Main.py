import config
import time
from pybit.unified_trading import HTTP
from decimal import Decimal, ROUND_DOWN, ROUND_FLOOR
import threading
import telebot

session = HTTP(
    testnet=False,
    api_key=config.api_key,
    api_secret=config.api_secret,
)

# DEFINIR PARAMETROS PARA OPERAR
amount_usdt = Decimal(10)
factor_multiplicador_cantidad = Decimal(40) / Decimal('100')
numero_recompras = int(6)
factor_multiplicador_distancia = Decimal(2)
distancia_porcentaje_tp = Decimal(1.5) / Decimal('100')
distancia_porcentaje_sl = Decimal(numero_recompras * factor_multiplicador_distancia / 100) + Decimal("0.006")

bot_token = config.token_telegram
bot = telebot.TeleBot(bot_token)
chat_id = config.chat_id

def enviar_mensaje_telegram(chat_id, mensaje):
    try:
        bot.send_message(chat_id, mensaje, parse_mode='HTML')
    except Exception as e:
        print(f"No se pudo enviar el mensaje a Telegram: {e}")

def get_current_position(symbol):
    try:
        response_positions = session.get_positions(category="linear", symbol=symbol)
        if response_positions['retCode'] == 0:
            return response_positions['result']['list']
        else:
            print(f"Error al obtener la posición: {response_positions}")
            return None
    except Exception as e:
        print(f"Error al obtener la posición: {e}")
        return None


def get_open_positions_count():
    try:
        response_positions = session.get_positions(category="linear", settleCoin="USDT")
        if response_positions['retCode'] == 0:
            positions = response_positions['result']['list']
            open_positions = [position for position in positions if Decimal(position['size']) != 0]
            return len(open_positions)
        else:
            print(f"Error al obtener el conteo de posiciones abiertas: {response_positions}")
            return 0
    except Exception as e:
        print(f"Error al obtener el conteo de posiciones abiertas: {e}")
        return 0
def get_pnl(symbol):
    closed_orders_response = session.get_closed_pnl(category="linear", symbol=symbol, limit=1)
    closed_orders_list = closed_orders_response['result']['list']

    for order in closed_orders_list:
        pnl_cerrada = float(order['closedPnl'])
        titulo = f"<b>🎉 Posición ganada {symbol} 🎉</b>\n\n"
        subtitule = f"💰 PNL realizado 💰: {pnl_cerrada:.2f}$ USDT."
        mensaje_pnl = titulo + subtitule
        enviar_mensaje_telegram(chat_id=chat_id, mensaje=mensaje_pnl) 
        print(mensaje_pnl)
        

def take_profit(symbol):
    positions_list = get_current_position(symbol)
    if positions_list:
        current_price = Decimal(positions_list[0]['avgPrice'])
        distancia_porcentaje_tp_decimal = Decimal(str(distancia_porcentaje_tp))
        price_tp = adjust_price(symbol, current_price * (Decimal(1) + distancia_porcentaje_tp_decimal))
        response_limit_tp = session.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            orderType="Limit",
            qty="0",
            price=str(price_tp),
            reduceOnly=True,
        )
        Mensaje_tp = f"Take Profit para {symbol} colocado con éxito: {response_limit_tp}"
        enviar_mensaje_telegram(chat_id=chat_id, mensaje=Mensaje_tp)
        print(Mensaje_tp)

def abrir_posicion_largo(symbol, base_asset_qty_final, distancia_porcentaje_sl):
    try:
        if get_open_positions_count() >= 3:
            mensaje_count =("Se alcanzó el máximo de 3 posiciones abiertas. No se abrirá una nueva posición.")
            enviar_mensaje_telegram(chat_id=chat_id, mensaje=mensaje_count)
            print (mensaje_count)
            return

        positions_list = get_current_position(symbol)
        if positions_list and any(Decimal(position['size']) != 0 for position in positions_list):
            print("Ya hay una posición abierta. No se abrirá otra posición.")
            return

        response_market_order = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=base_asset_qty_final,
        )
        Mensaje_market = f"Orden Market Long en {symbol} abierta con éxito: {response_market_order}"
        enviar_mensaje_telegram(chat_id=chat_id, mensaje=Mensaje_market)
        print(Mensaje_market)

        time.sleep(5)
        take_profit(symbol)
        if response_market_order['retCode'] != 0:
            print("Error al abrir la posición: La orden de mercado no se completó correctamente.")
            return

        positions_list = get_current_position(symbol)
        current_price = Decimal(positions_list[0]['avgPrice'])

        price_sl = adjust_price(symbol, current_price * Decimal(1 - distancia_porcentaje_sl))
        stop_loss_order = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            stopLoss=price_sl,
            slTriggerB="IndexPrice",
            tpslMode="Full",
            slOrderType="Market",
        )
        mensaje_sl = f"Stop Loss para {symbol} colocado con éxito: {stop_loss_order}"
        enviar_mensaje_telegram(chat_id=chat_id, mensaje=mensaje_sl)
        print(mensaje_sl)

        size_nuevo = base_asset_qty_final
        for i in range(1, numero_recompras + 1):
            porcentaje_distancia = Decimal('0.01') * i * factor_multiplicador_distancia
            cantidad_orden = size_nuevo * (1 + factor_multiplicador_cantidad)

            if isinstance(size_nuevo, int):
                cantidad_orden = int(cantidad_orden)
            else:
                cantidad_orden = round(cantidad_orden, len(str(size_nuevo).split('.')[1]))

            size_nuevo = cantidad_orden
            precio_orden_limite = adjust_price(symbol, current_price - (current_price * porcentaje_distancia))

            response_limit_order = session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy",
                orderType="Limit",
                qty=str(cantidad_orden),
                price=str(precio_orden_limite),
            )
            mensaje_recompras2 = f"{symbol}: Orden Límite de compra {i} colocada con exito:{response_limit_order}"
            enviar_mensaje_telegram(chat_id=chat_id, mensaje=mensaje_recompras2)
            print(mensaje_recompras2)

    except Exception as e:
        print(f"Error al abrir la posición: {e}")

def qty_step(symbol, amount_usdt):
    try:
        tickers = session.get_tickers(symbol=symbol, category="linear")
        for ticker_data in tickers["result"]["list"]:
            last_price = float(ticker_data["lastPrice"])

        last_price_decimal = Decimal(last_price)

        step_info = session.get_instruments_info(category="linear", symbol=symbol)
        qty_step = Decimal(step_info['result']['list'][0]['lotSizeFilter']['qtyStep'])

        base_asset_qty = amount_usdt / last_price_decimal

        qty_step_str = str(qty_step)
        if '.' in qty_step_str:
            decimals = len(qty_step_str.split('.')[1])
            base_asset_qty_final = round(base_asset_qty, decimals)
        else:
            base_asset_qty_final = int(base_asset_qty)

        return base_asset_qty_final
    except Exception as e:
        print(f"Error al calcular la cantidad del activo base: {e}")
        return None

def adjust_price(symbol, price):
    try:
        instrument_info = session.get_instruments_info(category="linear", symbol=symbol)
        tick_size = float(instrument_info['result']['list'][0]['priceFilter']['tickSize'])
        price_scale = int(instrument_info['result']['list'][0]['priceScale'])

        tick_dec = Decimal(f"{tick_size}")
        precision = Decimal(f"{10**price_scale}")
        price_decimal = Decimal(f"{price}")
        adjusted_price = (price_decimal * precision) / precision
        adjusted_price = (adjusted_price / tick_dec).quantize(Decimal('1'), rounding=ROUND_FLOOR) * tick_dec

        return float(adjusted_price)
    except Exception as e:
        print(f"Error al ajustar el precio: {e}")
        return None

def read_symbols_targets(file_path):
    symbols_targets = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) == 2:
                    symbol = parts[0]
                    target_price = Decimal(parts[1])
                    symbols_targets[symbol] = target_price
    except Exception as e:
        print(f"Error al leer el archivo de símbolos y targets: {e}")
    return symbols_targets

def tomar_decision(file_path):
    monitoreados = set()
    while True:
        symbols_targets = read_symbols_targets(file_path)
        for symbol, target_price in symbols_targets.items():
            if symbol not in monitoreados:
                try:
                    tickers = session.get_tickers(symbol=symbol, category="linear")
                    for ticker_data in tickers["result"]["list"]:
                        last_price = Decimal(ticker_data["lastPrice"])

                    if last_price <= target_price:
                        base_asset_qty_final = qty_step(symbol, amount_usdt)
                        abrir_posicion_largo(symbol, base_asset_qty_final, distancia_porcentaje_sl)
                        monitoreados.add(symbol)
                        mensaje_monitor = f"Dejando de monitorear {symbol} ya que ha alcanzado su precio objetivo."
                        enviar_mensaje_telegram(chat_id=chat_id, mensaje=mensaje_monitor)
                        print(mensaje_monitor)
                    else:
                        print(f"{symbol} Precio actual: {last_price}, Punto target: {target_price} ")
                except Exception as e:
                    print(f"Error al tomar decisión para {symbol}: {e}")
        time.sleep(5)

def cancelar_ordenes():
    symbols_monitored = set()  # Conjunto para almacenar los símbolos monitoreados
    last_entry_prices = {}  # Diccionario para almacenar el último precio de entrada por símbolo

    while True:
        try:
            # Obtener todas las posiciones abiertas
            positions = session.get_positions(category="linear", settleCoin="USDT")['result']['list']

            # Verificar cada posición
            for position in positions:
                symbol = position['symbol']
                current_price = Decimal(position['avgPrice'])
                 # Verificar si el precio de entrada ha cambiado desde la última revisión
                if symbol in last_entry_prices and last_entry_prices[symbol] != current_price:
                    # Cancelar la orden de take profit existente
                    open_orders = session.get_open_orders(category="linear", symbol=symbol)['result']['list']
                    tp_limit_orders = [order for order in open_orders
                                       if order.get('orderType') == "Limit" and order.get('side') == "Sell"]

                    for order in tp_limit_orders:
                        cancel_response = session.cancel_order(category="linear", symbol=symbol, orderId=order['orderId'])
                        if 'result' in cancel_response and cancel_response['result']:
                            print(f"Orden de take profit cancelada con éxito en {symbol}: {cancel_response}")

                    # Volver a colocar el take profit
                    take_profit(symbol)

                # Actualizar el precio de entrada anterior
                last_entry_prices[symbol] = current_price

                # Agregar el símbolo al conjunto de monitoreo si no está presente
                if symbol not in symbols_monitored:
                    symbols_monitored.add(symbol)

            # Cancelar todas las órdenes limit abiertas para los símbolos no monitoreados
            for symbol in symbols_monitored.copy():
                if symbol not in [pos['symbol'] for pos in positions]:
                    session.cancel_all_orders(category="linear", symbol=symbol)
                    get_pnl (symbol)
                    symbols_monitored.remove(symbol)
                    

        except Exception as e:
            print(f"Error en la cancelación de órdenes: {e}")

        time.sleep(5)  # Esperar 5 segundos antes de la próxima iteración


if __name__ == "__main__":
    file_path = 'symbols_targets.txt'

    tomar_decision_thread = threading.Thread(target=tomar_decision, args=(file_path,))
    tomar_decision_thread.start()

    cancelar_ordenes_thread = threading.Thread(target=cancelar_ordenes)
    cancelar_ordenes_thread.start()
