import requests
import fitz  # PyMuPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import re
import os

# ---------------- Busca automática do link PDF ----------------

URL_PAGINA = "https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php?acao=edicao_ver_ultima"

print("Buscando página para extrair link do PDF...")

resp = requests.get(URL_PAGINA)
html = resp.text

# CAPTURA ROBUSTA: procura qualquer href que contenha memoria_arquivo.php
match = re.search(r'href="(.*?memoria_arquivo\.php[^"]*)"', html)

if match:
    PDF_URL = match.group(1)

    # Se o link vier sem domínio, adiciona automaticamente
    if not PDF_URL.startswith("http"):
        PDF_URL = "https://diariooficial.prefeitura.sp.gov.br/" + PDF_URL.lstrip("/")

    print(f"Link do PDF encontrado:\n{PDF_URL}")

else:
    raise Exception("Não foi possível encontrar o link do PDF.")

# ----------------------------------------------------------------

DOWNLOAD_PDF_PATH = "/tmp/do_sp.pdf"
TERMO = "conservação de pavimento"

EMAIL_REMETENTE = os.environ["EMAIL_REMETENTE"]
EMAIL_SENHA = os.environ["EMAIL_SENHA"]
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", EMAIL_REMETENTE)

try:
    print("Baixando PDF...")
    pdf_resp = requests.get(PDF_URL)
    with open(DOWNLOAD_PDF_PATH, "wb") as f:
        f.write(pdf_resp.content)
    print(f"PDF baixado com sucesso!")

    print("Abrindo PDF e procurando pelo termo...")
    doc = fitz.open(DOWNLOAD_PDF_PATH)
    ocorrencias = []

    termo_normalizado = TERMO.lower()
    padrao = re.sub(r'\s+', r'\\s+', termo_normalizado)

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        text_normalizado = re.sub(r'\s+', ' ', text).lower()

        for match in re.finditer(padrao, text_normalizado):
            start, end = match.start(), match.end()
            trecho = text_normalizado[max(start-30, 0):min(end+30, len(text_normalizado))]
            ocorrencias.append({"pagina": i, "trecho": trecho.strip()})

    doc.close()

    if ocorrencias:
        corpo = f"O termo '{TERMO}' foi encontrado nas seguintes páginas:\n\n"
        for occ in ocorrencias:
            corpo += f"- Página {occ['pagina']}: ...{occ['trecho']}...\n\n"
    else:
        corpo = f"O termo '{TERMO}' NÃO foi encontrado no PDF do Diário Oficial."

    print("Preparando e-mail...")
    msg = MIMEMultipart()
    msg["Subject"] = "Alerta Diário Oficial SP"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO

    msg.attach(MIMEText(corpo, "plain"))

    if os.path.exists(DOWNLOAD_PDF_PATH):
        with open(DOWNLOAD_PDF_PATH, "rb") as f:
            part = MIMEApplication(f.read(), Name="diario.pdf")
            part['Content-Disposition'] = 'attachment; filename="diario.pdf"'
            msg.attach(part)

    print("Conectando ao SMTP...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.send_message(msg)
        print("E-mail enviado com sucesso!")

except Exception as e:
    print(f"ERRO: {e}")
