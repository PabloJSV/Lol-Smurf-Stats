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

    all_matches = lol_watcher.match.matchlist_by_puuid(my_region, me['puuid'], count=20, queue=queue_type)  # Obtenemos las últimas 20 partidas

    # Creamos la barra de progreso
    progress_bar = tqdm(total=len(all_matches))
    
    # Inicia el hilo que actualizará la barra de progreso.
    thread = threading.Thread(target=progress_updater, args=(progress_bar,))
    thread.start()

    # Lista de invocadores analizados
    analyzed_summoners = []

    counter = 0
    smurf_list = []
    days_of_week = [0, 0, 0, 0, 0, 0, 0]  # Contador para cada día de la semana
    for match_id in all_matches:
        # Actualizamos la barra de progreso
        progress_bar.update(1)

        match = lol_watcher.match.by_id(my_region, match_id)
        game_date = datetime.fromtimestamp(match['info']['gameStartTimestamp'] / 1000)
        days_of_week[game_date.weekday()] += 1
        smurf_found = False  # Añadimos una bandera para saber si hemos encontrado un smurf en esta partida
        for participant in match['info']['participants']:
            if participant['summonerLevel'] <= 70:
                summoner_name = participant['summonerName']

                if summoner_name in analyzed_summoners:
                    print(f"El invocador {summoner_name} ya fue analizado. Saltando...")
                    continue

                analyzed_summoners.append(summoner_name)

                # Ahora buscamos las últimas 10 partidas de este jugador.
                try:
                    player = lol_watcher.summoner.by_name(my_region, participant['summonerName'])
                except ApiError as e:
                    if e.response.status_code == 404:  # No se encontró el invocador.
                        print(f"El invocador {participant['summonerName']} no se encontró. Saltando...")
                        continue
                    else:
                        raise e  # Si es otro tipo de error, lo lanzamos.
                        
                print(f"Analizando partidas para el jugador: {participant['summonerName']}")
                player_matches = lol_watcher.match.matchlist_by_puuid(my_region, player['puuid'], count=10, queue=queue_type)
                kdas = []
                for player_match_id in player_matches:
                    print(f"Calculando KDA para la partida: {player_match_id}")
                    player_match = lol_watcher.match.by_id(my_region, player_match_id)
                    for player_participant in player_match['info']['participants']:
                        if player_participant['puuid'] == player['puuid']:
                            kdas.append(calculate_kda(player_participant))

                # Calculamos el KDA promedio del jugador en sus últimas 10 partidas.
                avg_kda = sum(kdas) / len(kdas)
                print(f"KDA promedio para el jugador {participant['summonerName']} es: {avg_kda}")
                
                if avg_kda >= 4:
                    smurf_found = True  # Marcamos que hemos encontrado un smurf
                    smurf_list.append(participant['summonerName'])
                    break  # Salimos del bucle ya que ya encontramos un smurf

        # Solo incrementamos el contador una vez por partida si encontramos un smurf
        if smurf_found:
            counter += 1

    global running
    running = False
    thread.join()

    progress_bar.close()

    smurf_percentage = (counter / len(all_matches)) * 100

    week_days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    percentages_days = [ (i / len(all_matches)) * 100 for i in days_of_week]

    # Lista de tuplas con días y porcentajes 
    days_percentages = list(zip(week_days, percentages_days))
    # Ordenamos la lista por porcentaje descendiente
    days_percentages.sort(key=lambda x: x[1], reverse=True)

    return smurf_list, counter, smurf_percentage,days_percentages

queue_id_soloq = 420
queue_id_flex = 440

smurf_list_soloq, counter_soloq, percentage_soloq, worst_days_soloq = analyze_matches(USER, queue_id_soloq)

smurf_list_flex, counter_flex, percentage_flex, worst_days_flex = analyze_matches(USER, queue_id_flex)

print("Estadísticas para el invocador: ", USER)
print("Smurfs encontrados en SoloQ: ", smurf_list_soloq)
print("Número de partidas con smurfs en SoloQ: ", counter_soloq)
print("Porcentaje de partidas con smurfs en SoloQ: ", percentage_soloq)
print("Los peores días para jugar en SoloQ son: ", worst_days_soloq)

print("Smurfs encontrados en Flex: ", smurf_list_flex)
print("Número de partidas con smurfs en Flex: ", counter_flex)
print("Porcentaje de partidas con smurfs en Flex: ", percentage_flex)
print("Los peores días para jugar en Flex son: ", worst_days_flex)