# Imagem enxuta so com o necessario para servir a API + o frontend ja compilado.
# O frontend e construido no host (npm run build) antes; aqui so copiamos frontend/dist.
FROM python:3.12-slim

WORKDIR /app

# Apenas as dependencias que a API usa em tempo de execucao (nao inclui
# streamlit/pandas, que so o painel antigo em frontend.py precisa).
RUN pip install --no-cache-dir --break-system-packages fastapi "uvicorn[standard]" pypdf python-multipart

COPY analisar_exames.py achados.py mapa_exames.py api.py ./
COPY frontend/dist ./frontend/dist

# Nao publicamos porta para o host (sem -p no docker run): o container so e
# alcancavel de dentro da rede Docker (pelo Caddy), nunca direto da internet.
EXPOSE 8502
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8502"]
