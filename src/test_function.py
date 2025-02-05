import io
import json
from retry_test import handler

# Simular dados de entrada em formato JSON
data = {
    "OCID": "ocid1.loadbalancer.oc1.sa-saopaulo-1.aaaaaaaarxvsfuw7jbsz3xjaqyxiedtp5lgkxvtxucocsthrsr3gw2tco3qq",
    "poolOCID": "ocid1.instancepool.oc1.sa-saopaulo-1.aaaaaaaaoop4lbsjzdcbfpygctsivp3fydg3jyohwsyeihw7qzfpy42f62lq",
    "qtdRequestPerVM": 20,
}

# Criar um `BytesIO` para simular o fluxo de entrada (data)
input_data = io.BytesIO(json.dumps(data).encode('utf-8'))

# Simular o contexto (ctx) - pode ser um dicionário vazio
ctx = {}

# Chamar o handler e capturar a resposta
response = handler(ctx, input_data)

