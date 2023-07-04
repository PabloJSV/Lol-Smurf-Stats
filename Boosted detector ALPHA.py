import threading
import time
from tqdm import tqdm
from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()  # toma las variables de entorno desde .env

API_KEY = os.getenv('API_KEY')
USER = os.getenv('USER')

lol_watcher = LolWatcher(API_KEY)

my_region = 'euw1'  # Cambia esto a la región del invocador.

# Variable global que controla si el hilo de la barra de progreso debe seguir ejecutándose.
running = True

def progress_updater(bar):
    global running
    while running:
        # Imprime la barra de progreso cada 30 segundos.
        print(str(bar))
        time.sleep(30)

def calculate_kda(participant):
    kills = participant['kills']
    deaths = participant['deaths']
    assists = participant['assists']

    if deaths == 0:
        kda = (kills + assists)
    else:
        kda = (kills + assists) / deaths

    return kda

def analyze_matches(summoner_name, queue_type):
    me = lol_watcher.summoner.by_name(my_region, summoner_name)
    print(f"Analizando partidas para el invocador: {summoner_name}")

    all_matches = lol_watcher.match.matchlist_by_puuid(my_region, me['puuid'], count=5, queue=queue_type)  # Obtenemos las últimas 100 partidas

    # Creamos la barra de progreso
    progress_bar = tqdm(total=len(all_matches))
    
    # Inicia el hilo que actualizará la barra de progreso.
    thread = threading.Thread(target=progress_updater, args=(progress_bar,))
    thread.start()

    # Lista de invocadores analizados
    analyzed_summoners = []

    boosted_counter = 0
    boosted_list = []
    days_of_week = [0, 0, 0, 0, 0, 0, 0]  # Contador para cada día de la semana
    for match_id in all_matches:
        # Actualizamos la barra de progreso
        progress_bar.update(1)
        
        match = lol_watcher.match.by_id(my_region, match_id)
        game_date = datetime.fromtimestamp(match['info']['gameStartTimestamp'] / 1000)
        days_of_week[game_date.weekday()] += 1
        boosted_found = False
        for participant in match['info']['participants']:
            summoner_name = participant['summonerName']

            if summoner_name in analyzed_summoners:
                print(f"El invocador {summoner_name} ya fue analizado. Saltando...")
                continue

            analyzed_summoners.append(summoner_name)

            try:
                player = lol_watcher.summoner.by_name(my_region, summoner_name)
                time.sleep(1.2)  # Pause between each API call
            except ApiError as e:
                if e.response.status_code == 404:  # No se encontró el invocador.
                    print(f"El invocador {summoner_name} no se encontró. Saltando...")
                    continue
                else:
                    raise e  # Si es otro tipo de error, lo lanzamos.
                
            print(f"Analizando partidas para el jugador: {summoner_name}")
            
            # Analizamos las últimas 10 y 50 partidas del jugador.
            player_matches_10 = lol_watcher.match.matchlist_by_puuid(my_region, player['puuid'], count=10, queue=queue_type)
            player_matches_50 = lol_watcher.match.matchlist_by_puuid(my_region, player['puuid'], count=50, queue=queue_type)

            # Calculamos el KDA para las últimas 10 y 50 partidas.
            kda_10 = calculate_average_kda(player, player_matches_10)
            kda_50 = calculate_average_kda(player, player_matches_50)

            # Verificamos si el jugador ha sido boosteado.
            if kda_10 >= 2 * kda_50:
                boosted_found = True
                boosted_list.append(summoner_name)
                break  # Salimos del bucle ya que ya encontramos un jugador boosteado.

        if boosted_found:
            boosted_counter += 1

    global running
    running = False
    thread.join()

    progress_bar.close()

    boosted_percentage = (boosted_counter / len(all_matches)) * 100

    week_days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    percentages_days = [ (i / len(all_matches)) * 100 for i in days_of_week]
    
    # Lista de tuplas con días y porcentajes 
    days_percentages = list(zip(week_days, percentages_days))
    # Ordenamos la lista por porcentaje descendiente
    days_percentages.sort(key=lambda x: x[1], reverse=True)

    # Devuelve la lista de jugadores boosteados, su conteo, porcentajes, y los 3 peores días para jugar partidas con sus correspondientes porcentajes
    return boosted_list, boosted_counter, boosted_percentage, days_percentages[:3]

def calculate_average_kda(player, player_matches):
    kdas = []
    for player_match_id in player_matches:
        print(f"Calculando KDA para la partida: {player_match_id}")
        player_match = lol_watcher.match.by_id(my_region, player_match_id)
        for player_participant in player_match['info']['participants']:
            if player_participant['puuid'] == player['puuid']:
                kdas.append(calculate_kda(player_participant))
    # Calculamos el KDA promedio del jugador.
    avg_kda = sum(kdas) / len(kdas)
    print(f"KDA promedio para el jugador {player['name']} es: {avg_kda}")
    return avg_kda

queue_id_soloq = 420
queue_id_flex = 440

boosted_list_soloq, boosted_counter_soloq, boosted_percentage_soloq, worst_days_soloq = analyze_matches(USER, queue_id_soloq)

boosted_list_flex, boosted_counter_flex, boosted_percentage_flex, worst_days_flex = analyze_matches(USER, queue_id_flex)

print("Jugadores boosteados encontrados en SoloQ: ", boosted_list_soloq)
print("Número de partidas con jugadores boosteados en SoloQ: ", boosted_counter_soloq)
print("Porcentaje de partidas con jugadores boosteados en SoloQ: ", boosted_percentage_soloq)
print("Los peores días para jugar en SoloQ son: ", worst_days_soloq)

print("Jugadores boosteados encontrados en Flex: ", boosted_list_flex)
print("Número de partidas con jugadores boosteados en Flex: ", boosted_counter_flex)
print("Porcentaje de partidas con jugadores boosteados en Flex: ", boosted_percentage_flex)
print("Los peores días para jugar en Flex son: ", worst_days_flex)
