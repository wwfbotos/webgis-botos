import ee
import os
import sys
import json
import pandas as pd
sys.path.insert(0, '.')

# Autentica no GEE via service account
service_account = os.environ['GEE_SERVICE_ACCOUNT']
private_key     = os.environ['GEE_PRIVATE_KEY']

credentials = ee.ServiceAccountCredentials(
    service_account, key_data=private_key)
ee.Initialize(credentials)
print('GEE autenticado!')

from utils.gee_loader import get_daily_temp_all_lakes

# Busca temperaturas diarias de todos os lagos
ASSET = 'projects/ee-researches-457119/assets/wwf_botos/lagos_amazonicos'
print('Buscando dados do MOD11A1...')
df = get_daily_temp_all_lakes(ASSET, 'name')

if df is None or df.empty:
    print('Sem dados disponiveis hoje.')
    sys.exit(0)

print(f'Dados obtidos: {len(df)} lagos')
alertas = df[df['diferenca'] >= 0.5]
print(f'Lagos com aumento >= 0.5C: {len(alertas)}')

if alertas.empty:
    print('Nenhum lago com aumento significativo. Email nao enviado.')
    sys.exit(0)

# Monta secrets a partir das variaveis de ambiente
class EnvSecrets:
    def __getitem__(self, key):
        return os.environ[key]

from utils.alertas import verificar_e_enviar_alerta

df_hoje  = df[['lago','temp_hoje','data_hoje']].rename(
    columns={'temp_hoje':'temperatura','data_hoje':'data'})
df_ontem = df[['lago','temp_ontem','data_ontem']].rename(
    columns={'temp_ontem':'temperatura','data_ontem':'data'})

enviado, msg = verificar_e_enviar_alerta(
    EnvSecrets(), df_hoje, df_ontem, limiar=0.5)
print(f'Email enviado: {enviado} — {msg}')
